// Package pubsub implements a Google Cloud Pub/Sub-backed ingest.LogSource. It
// pulls messages from a pull subscription, decodes each message body as a Cloud
// Logging LogEntry JSON object, maps it to a domain.LogEvent, and streams the
// events on a channel until the context is cancelled or Close is called.
//
// HIPAA: raw message payloads (which may carry PHI) are never logged. Only
// message IDs and counts appear in diagnostics.
package pubsub

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	gpubsub "cloud.google.com/go/pubsub/v2"
	"google.golang.org/api/option"

	"github.com/avivl/cloud-sre-agent/internal/domain"
)

// sourceName is the adapter identifier reported by Name.
const sourceName = "pubsub"

// defaultChannelBuffer sizes the outbound event channel so a slow consumer does
// not immediately stall the receive callbacks.
const defaultChannelBuffer = 64

// Config configures a PubSubSource.
type Config struct {
	// ProjectID is the GCP project that owns the subscription. Required.
	ProjectID string
	// SubscriptionID is the pull subscription to receive from. Required. It may
	// be a bare subscription ID or a fully-qualified
	// "projects/<p>/subscriptions/<s>" name.
	SubscriptionID string
	// Logger receives adapter diagnostics. Nil discards logs. Payloads are
	// never logged regardless of the logger.
	Logger *slog.Logger
	// ClientOptions are passed through to the Pub/Sub client constructor. They
	// exist for tests (e.g. an in-memory pstest connection); production callers
	// normally leave this nil and rely on ambient credentials.
	ClientOptions []option.ClientOption
}

// PubSubSource is an ingest.LogSource that receives Cloud Logging entries from
// a Pub/Sub pull subscription. It is safe to call Close concurrently with
// Stream.
//
//nolint:revive // Name is fixed by the ingest adapter contract; "pubsub.PubSubSource" is intentional.
type PubSubSource struct {
	cfg     Config
	log     *slog.Logger
	client  *gpubsub.Client
	sub     *gpubsub.Subscriber
	closed  chan struct{}
	once    sync.Once
	started atomic.Bool

	errMu    sync.Mutex
	fatalErr error // terminal Receive error; nil on clean shutdown
}

// New constructs a PubSubSource. It dials the Pub/Sub service (or the
// test-supplied connection) and binds a subscriber to the configured
// subscription. It returns an error when the configuration is invalid or the
// client cannot be created.
func New(ctx context.Context, cfg Config) (*PubSubSource, error) {
	if strings.TrimSpace(cfg.ProjectID) == "" {
		return nil, errors.New("pubsub source: project id is required")
	}
	if strings.TrimSpace(cfg.SubscriptionID) == "" {
		return nil, errors.New("pubsub source: subscription id is required")
	}

	logger := cfg.Logger
	if logger == nil {
		logger = slog.New(slog.NewTextHandler(io.Discard, nil))
	}

	client, err := gpubsub.NewClient(ctx, cfg.ProjectID, cfg.ClientOptions...)
	if err != nil {
		return nil, fmt.Errorf("pubsub source: create client: %w", err)
	}

	return &PubSubSource{
		cfg:    cfg,
		log:    logger.With("source", sourceName, "subscription", cfg.SubscriptionID),
		client: client,
		sub:    client.Subscriber(cfg.SubscriptionID),
		closed: make(chan struct{}),
	}, nil
}

// Name identifies the adapter.
func (s *PubSubSource) Name() string { return sourceName }

// setErr records the first terminal Receive error.
func (s *PubSubSource) setErr(err error) {
	s.errMu.Lock()
	defer s.errMu.Unlock()
	if s.fatalErr == nil {
		s.fatalErr = err
	}
}

// Err reports the terminal error that stopped Receive, or nil for a clean
// shutdown (context cancellation / Close). Read it after the event channel has
// closed: a non-nil result means the source died rather than draining, so the
// process should exit non-zero rather than treating it as normal completion.
func (s *PubSubSource) Err() error {
	s.errMu.Lock()
	defer s.errMu.Unlock()
	return s.fatalErr
}

// Close stops streaming and releases the Pub/Sub client. It is idempotent.
func (s *PubSubSource) Close() error {
	s.once.Do(func() { close(s.closed) })
	if s.client != nil {
		return s.client.Close()
	}
	return nil
}

// Stream begins receiving messages and delivering mapped events on the returned
// channel. The channel is closed when Receive returns (context cancelled, Close
// called, or a fatal receive error). An error is returned only when the stream
// cannot be started.
//
// Stream is single-use: a second call returns an error rather than starting a
// second receiver that would race the first.
func (s *PubSubSource) Stream(ctx context.Context) (<-chan domain.LogEvent, error) {
	if !s.started.CompareAndSwap(false, true) {
		return nil, fmt.Errorf("pubsub source: Stream already called; the source is single-use")
	}

	out := make(chan domain.LogEvent, defaultChannelBuffer)

	// runCtx is cancelled either when the caller's context is done or when
	// Close is invoked, so Receive returns promptly in both cases.
	runCtx, cancel := context.WithCancel(ctx)
	go func() {
		select {
		case <-s.closed:
			cancel()
		case <-runCtx.Done():
		}
	}()

	go func() {
		defer close(out)
		defer cancel()
		// Receive blocks, invoking the callback concurrently per message, until
		// runCtx is cancelled or a fatal error occurs.
		err := s.sub.Receive(runCtx, func(cctx context.Context, m *gpubsub.Message) {
			s.handle(cctx, m, out)
		})
		if err != nil && !errors.Is(err, context.Canceled) {
			// A non-context Receive error is terminal (permission revoked,
			// subscription deleted, ...). Record it so consume can exit
			// non-zero instead of mistaking the closed channel for a clean
			// drain. Log under the redacted "error" key, not raw.
			s.setErr(err)
			s.log.ErrorContext(ctx, "pubsub receive stopped", "error", err.Error())
		}
	}()

	return out, nil
}

// handle decodes one message into a domain.LogEvent and enqueues it, acking only
// after the event has been successfully enqueued. A message that cannot be
// decoded is acked and dropped with a counted warning (logging the message ID
// only, never the payload) so a poison message cannot wedge the subscription.
func (s *PubSubSource) handle(ctx context.Context, m *gpubsub.Message, out chan<- domain.LogEvent) {
	ev, err := mapMessage(m)
	if err != nil {
		// Drop-and-ack a malformed message: a Nack would only redeliver the same
		// undecodable payload forever. Never log the payload — only the ID.
		s.log.WarnContext(ctx, "pubsub message decode failed, dropping", "message_id", m.ID, "error", err.Error())
		m.Ack()
		return
	}

	select {
	case out <- ev:
		m.Ack()
	case <-ctx.Done():
		// Shutting down before the event could be enqueued: nack so the message
		// is redelivered to a future run rather than silently lost.
		m.Nack()
	case <-s.closed:
		m.Nack()
	}
}

// logEntry is the subset of the Cloud Logging LogEntry JSON shape we map. Every
// field is optional; unknown fields are ignored.
type logEntry struct {
	Severity    string            `json:"severity"`
	Timestamp   string            `json:"timestamp"`
	TextPayload string            `json:"textPayload"`
	JSONPayload json.RawMessage   `json:"jsonPayload"`
	LogName     string            `json:"logName"`
	InsertID    string            `json:"insertId"`
	Labels      map[string]string `json:"labels"`
	Resource    *struct {
		Type   string            `json:"type"`
		Labels map[string]string `json:"labels"`
	} `json:"resource"`
}

// mapMessage decodes a Pub/Sub message body as a Cloud Logging LogEntry and maps
// it to a domain.LogEvent. The event ID prefers the message ID, then the
// LogEntry insertId.
func mapMessage(m *gpubsub.Message) (domain.LogEvent, error) {
	var le logEntry
	if err := json.Unmarshal(m.Data, &le); err != nil {
		return domain.LogEvent{}, fmt.Errorf("decode log entry: %w", err)
	}

	id := firstNonEmpty(m.ID, le.InsertID)
	if id == "" {
		return domain.LogEvent{}, errors.New("log entry: no message id or insertId")
	}

	ev := domain.LogEvent{
		ID:        id,
		Timestamp: entryTimestamp(le.Timestamp, m.PublishTime),
		Severity:  mapSeverity(le.Severity),
		Message:   entryMessage(le),
		Source:    entrySource(le),
		Labels:    mergeLabels(le),
	}
	return ev, nil
}

// mapSeverity maps a Cloud Logging severity string to a domain.Severity.
// Cloud Logging uses uppercase names; DEFAULT and NOTICE map to info,
// ALERT/EMERGENCY map to critical. Unknown values default to info so an event
// is never dropped purely for an unrecognized severity.
func mapSeverity(s string) domain.Severity {
	switch strings.ToUpper(strings.TrimSpace(s)) {
	case "DEBUG":
		return domain.SeverityDebug
	case "", "DEFAULT", "INFO", "NOTICE":
		return domain.SeverityInfo
	case "WARNING":
		return domain.SeverityWarning
	case "ERROR":
		return domain.SeverityError
	case "CRITICAL", "ALERT", "EMERGENCY":
		return domain.SeverityCritical
	default:
		return domain.SeverityInfo
	}
}

// entryMessage extracts the human-readable message: textPayload, then
// jsonPayload.message, then the raw jsonPayload JSON if neither is present.
func entryMessage(le logEntry) string {
	if le.TextPayload != "" {
		return le.TextPayload
	}
	if len(le.JSONPayload) > 0 {
		var jp struct {
			Message string `json:"message"`
			Msg     string `json:"msg"`
		}
		if err := json.Unmarshal(le.JSONPayload, &jp); err == nil {
			if msg := firstNonEmpty(jp.Message, jp.Msg); msg != "" {
				return msg
			}
		}
		return string(le.JSONPayload)
	}
	return ""
}

// entrySource composes a source identifier from the monitored resource type and
// the log name, e.g. "gce_instance:projects/p/logs/syslog".
func entrySource(le logEntry) string {
	resType := ""
	if le.Resource != nil {
		resType = le.Resource.Type
	}
	switch {
	case resType != "" && le.LogName != "":
		return fmt.Sprintf("%s:%s", resType, le.LogName)
	case resType != "":
		return resType
	case le.LogName != "":
		return le.LogName
	default:
		return sourceName
	}
}

// mergeLabels merges the monitored resource labels with the entry-level labels.
// Entry labels win on key collision. Returns nil when there are no labels.
func mergeLabels(le logEntry) map[string]string {
	var resLabels map[string]string
	if le.Resource != nil {
		resLabels = le.Resource.Labels
	}
	if len(resLabels) == 0 && len(le.Labels) == 0 {
		return nil
	}
	merged := make(map[string]string, len(resLabels)+len(le.Labels))
	for k, v := range resLabels {
		merged[k] = v
	}
	for k, v := range le.Labels {
		merged[k] = v
	}
	return merged
}

// entryTimestamp parses the LogEntry timestamp, falling back to the message
// publish time and finally to the current UTC time.
func entryTimestamp(v string, publish time.Time) time.Time {
	if v != "" {
		if t, err := time.Parse(time.RFC3339Nano, v); err == nil {
			return t.UTC()
		}
		if t, err := time.Parse(time.RFC3339, v); err == nil {
			return t.UTC()
		}
	}
	if !publish.IsZero() {
		return publish.UTC()
	}
	return time.Now().UTC()
}

// firstNonEmpty returns the first non-empty string among its arguments.
func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if v != "" {
			return v
		}
	}
	return ""
}
