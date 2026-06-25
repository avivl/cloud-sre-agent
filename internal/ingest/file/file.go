// Package file implements a filesystem-backed ingest.LogSource. It reads log
// lines from a single file or a glob of files, parses each line into a
// domain.LogEvent (plain text or JSON lines, with inferred severity), and
// streams the events on a channel. In watch mode it tails matching files for
// appended lines until the context is cancelled or Close is called.
package file

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/avivl/cloud-sre-agent/internal/domain"
)

// sourceName is the adapter identifier reported by Name.
const sourceName = "file"

// defaultPollInterval is how often watch mode re-scans tailed files for new
// content when no explicit interval is configured.
const defaultPollInterval = 500 * time.Millisecond

// defaultChannelBuffer sizes the outbound event channel so a slow consumer
// does not immediately stall the reader.
const defaultChannelBuffer = 64

// Encoding selects how a raw log line is decoded into a LogEvent.
type Encoding string

const (
	// EncodingAuto inspects each line: a line that parses as a JSON object is
	// treated as JSON, otherwise it is treated as plain text.
	EncodingAuto Encoding = "auto"
	// EncodingJSON treats every line as a JSON object (JSON Lines).
	EncodingJSON Encoding = "json"
	// EncodingText treats every line as opaque plain text.
	EncodingText Encoding = "text"
)

// Config configures a FileSystemSource.
type Config struct {
	// Path is a file path or a glob pattern (e.g. "/var/log/*.log"). Required.
	Path string
	// Watch, when true, tails matching files for newly appended lines instead
	// of returning after the existing content is consumed.
	Watch bool
	// Encoding selects line decoding. Empty defaults to EncodingAuto.
	Encoding Encoding
	// PollInterval is the watch-mode re-scan cadence. Zero defaults to
	// defaultPollInterval. Ignored when Watch is false.
	PollInterval time.Duration
	// Logger receives adapter diagnostics. Nil discards logs.
	Logger *slog.Logger
}

// FileSystemSource is an ingest.LogSource that reads log events from the
// filesystem. It is safe to call Close concurrently with Stream.
//
//nolint:revive // Name is fixed by the ingest adapter contract; "file.FileSystemSource" is intentional.
type FileSystemSource struct {
	cfg     Config
	log     *slog.Logger
	enc     Encoding
	poll    time.Duration
	closed  chan struct{}
	once    sync.Once
	started atomic.Bool
	seq     uint64
	seqMu   sync.Mutex

	// tracked records per-file read state in watch mode. It is only touched by
	// the single run goroutine, so it needs no synchronization.
	tracked map[string]fileState
}

// New constructs a FileSystemSource from cfg. It returns an error only when the
// configuration is structurally invalid; missing files are reported lazily by
// Stream so that watch mode can wait for a file to appear.
func New(cfg Config) (*FileSystemSource, error) {
	if strings.TrimSpace(cfg.Path) == "" {
		return nil, errors.New("file source: path is required")
	}
	enc := cfg.Encoding
	if enc == "" {
		enc = EncodingAuto
	}
	switch enc {
	case EncodingAuto, EncodingJSON, EncodingText:
	default:
		return nil, fmt.Errorf("file source: unknown encoding %q", cfg.Encoding)
	}
	poll := cfg.PollInterval
	if poll <= 0 {
		poll = defaultPollInterval
	}
	logger := cfg.Logger
	if logger == nil {
		logger = slog.New(slog.NewTextHandler(io.Discard, nil))
	}
	return &FileSystemSource{
		cfg:    cfg,
		log:    logger.With("source", sourceName, "path", cfg.Path),
		enc:    enc,
		poll:   poll,
		closed: make(chan struct{}),
	}, nil
}

// Name identifies the adapter.
func (s *FileSystemSource) Name() string { return sourceName }

// Close stops streaming and releases resources. It is idempotent.
func (s *FileSystemSource) Close() error {
	s.once.Do(func() { close(s.closed) })
	return nil
}

// nextID returns a monotonically increasing per-source event identifier.
func (s *FileSystemSource) nextID() string {
	s.seqMu.Lock()
	s.seq++
	n := s.seq
	s.seqMu.Unlock()
	return fmt.Sprintf("%s-%d", sourceName, n)
}

// Stream resolves the configured path/glob and begins delivering events. The
// returned channel is closed when all files are exhausted (non-watch mode), the
// context is cancelled, or Close is called. An error is returned only when the
// stream cannot be started (no matching files in non-watch mode).
//
// Stream is single-use: a second call returns an error rather than starting a
// second reader goroutine that would race the first over the per-file read
// state.
func (s *FileSystemSource) Stream(ctx context.Context) (<-chan domain.LogEvent, error) {
	if !s.started.CompareAndSwap(false, true) {
		return nil, fmt.Errorf("file source: Stream already called; the source is single-use")
	}

	matches, err := filepath.Glob(s.cfg.Path)
	if err != nil {
		return nil, fmt.Errorf("file source: bad glob %q: %w", s.cfg.Path, err)
	}
	if len(matches) == 0 && !s.cfg.Watch {
		return nil, fmt.Errorf("file source: no files match %q", s.cfg.Path)
	}

	out := make(chan domain.LogEvent, defaultChannelBuffer)
	go s.run(ctx, matches, out)
	return out, nil
}

// fileState records what has been consumed from a watched file so that
// re-scans emit only newly appended content and can detect rotation.
type fileState struct {
	offset int64
	info   os.FileInfo
}

// run drives reading and (optionally) tailing until done, then closes out.
func (s *FileSystemSource) run(ctx context.Context, initial []string, out chan<- domain.LogEvent) {
	defer close(out)

	if !s.cfg.Watch {
		for _, path := range initial {
			if s.stopped(ctx) {
				return
			}
			if _, err := s.drainFile(ctx, path, 0, out); err != nil {
				s.log.WarnContext(ctx, "read file failed", "file", path, "err", err.Error())
			}
		}
		return
	}

	// Watch mode: poll for matching files and append-only growth.
	s.tracked = make(map[string]fileState)
	ticker := time.NewTicker(s.poll)
	defer ticker.Stop()

	// The first scan emits existing content once, then subsequent ticks emit
	// only newly appended lines.
	s.scan(ctx, out)
	for {
		select {
		case <-ctx.Done():
			return
		case <-s.closed:
			return
		case <-ticker.C:
			s.scan(ctx, out)
		}
	}
}

// scan re-globs the pattern and drains any new bytes from each match.
func (s *FileSystemSource) scan(ctx context.Context, out chan<- domain.LogEvent) {
	matches, err := filepath.Glob(s.cfg.Path)
	if err != nil {
		s.log.WarnContext(ctx, "glob failed", "err", err.Error())
		return
	}
	for _, path := range matches {
		if s.stopped(ctx) {
			return
		}
		st := s.tracked[path]
		info, statErr := os.Stat(path)
		if statErr != nil {
			continue
		}
		start := st.offset
		// Detect rotation/truncation. A shrunk file was truncated in place; a
		// file whose identity changed (new inode behind the same name) was
		// rotated. In both cases restart from the beginning.
		if info.Size() < start || (st.info != nil && !os.SameFile(st.info, info)) {
			start = 0
		}
		end, err := s.drainFile(ctx, path, start, out)
		if err != nil {
			s.log.WarnContext(ctx, "tail file failed", "file", path, "err", err.Error())
			continue
		}
		s.tracked[path] = fileState{offset: end, info: info}
	}
}

// drainFile reads path starting at byte offset start, emits one event per
// complete line, and returns the byte offset after the last complete line read.
// A trailing partial line (no newline yet) is not consumed so a later pass can
// read it once it is completed.
func (s *FileSystemSource) drainFile(ctx context.Context, path string, start int64, out chan<- domain.LogEvent) (int64, error) {
	f, err := os.Open(path) //nolint:gosec // path is operator-configured, not user input.
	if err != nil {
		return start, err
	}
	defer func() { _ = f.Close() }()

	if start > 0 {
		if _, err := f.Seek(start, io.SeekStart); err != nil {
			return start, err
		}
	}

	offset := start
	reader := bufio.NewReader(f)
	for {
		if s.stopped(ctx) {
			return offset, nil
		}
		line, err := reader.ReadString('\n')
		if len(line) > 0 && strings.HasSuffix(line, "\n") {
			offset += int64(len(line))
			trimmed := strings.TrimRight(line, "\r\n")
			if trimmed == "" {
				continue
			}
			ev := s.parseLine(path, trimmed)
			if !s.emit(ctx, out, ev) {
				return offset, nil
			}
			continue
		}
		// No newline: either EOF or a partial trailing line. Stop and leave the
		// partial bytes unconsumed for the next pass.
		if err != nil {
			return offset, nil //nolint:nilerr // EOF/partial line is not an error.
		}
	}
}

// emit sends ev on out, honoring context and Close. It reports whether the
// event was delivered (false means the source is shutting down).
func (s *FileSystemSource) emit(ctx context.Context, out chan<- domain.LogEvent, ev domain.LogEvent) bool {
	select {
	case out <- ev:
		return true
	case <-ctx.Done():
		return false
	case <-s.closed:
		return false
	}
}

// stopped reports whether the source should stop (context cancelled or closed).
func (s *FileSystemSource) stopped(ctx context.Context) bool {
	select {
	case <-ctx.Done():
		return true
	case <-s.closed:
		return true
	default:
		return false
	}
}

// jsonLine is the recognized shape of a JSON log line. Every field is optional;
// unknown fields are folded into Labels by the caller via the raw map.
type jsonLine struct {
	Timestamp string            `json:"timestamp"`
	Time      string            `json:"time"`
	Severity  string            `json:"severity"`
	Level     string            `json:"level"`
	Message   string            `json:"message"`
	Msg       string            `json:"msg"`
	Labels    map[string]string `json:"labels"`
}

// parseLine converts a single raw log line into a LogEvent according to the
// configured encoding. It never fails: an unparseable JSON line under auto
// encoding falls back to plain text, and severity defaults to info.
func (s *FileSystemSource) parseLine(path, line string) domain.LogEvent {
	switch s.enc {
	case EncodingJSON:
		if ev, ok := s.parseJSON(path, line); ok {
			return ev
		}
		return s.parseText(path, line)
	case EncodingText:
		return s.parseText(path, line)
	case EncodingAuto:
		if looksJSON(line) {
			if ev, ok := s.parseJSON(path, line); ok {
				return ev
			}
		}
		return s.parseText(path, line)
	default:
		return s.parseText(path, line)
	}
}

// looksJSON reports whether line is plausibly a JSON object.
func looksJSON(line string) bool {
	t := strings.TrimSpace(line)
	return strings.HasPrefix(t, "{") && strings.HasSuffix(t, "}")
}

// parseJSON decodes a JSON log line. The bool result is false when the line is
// not a valid JSON object, letting the caller fall back to text.
func (s *FileSystemSource) parseJSON(path, line string) (domain.LogEvent, bool) {
	var jl jsonLine
	if err := json.Unmarshal([]byte(line), &jl); err != nil {
		return domain.LogEvent{}, false
	}

	msg := firstNonEmpty(jl.Message, jl.Msg)
	if msg == "" {
		// A JSON object with no recognizable message is more useful as its raw
		// text than as an empty event; fall back to text.
		return domain.LogEvent{}, false
	}

	sevLabel := firstNonEmpty(jl.Severity, jl.Level)
	sev := domain.ParseSeverity(sevLabel)
	if sev == domain.SeverityUnknown {
		sev = inferSeverity(msg)
	}

	ts := parseTimestamp(firstNonEmpty(jl.Timestamp, jl.Time))

	return domain.LogEvent{
		ID:        s.nextID(),
		Timestamp: ts,
		Severity:  sev,
		Message:   msg,
		Source:    fmt.Sprintf("%s:%s", sourceName, filepath.Base(path)),
		Labels:    jl.Labels,
	}, true
}

// parseText builds a LogEvent from an opaque text line, inferring severity from
// the message content and stamping the current time.
func (s *FileSystemSource) parseText(path, line string) domain.LogEvent {
	return domain.LogEvent{
		ID:        s.nextID(),
		Timestamp: time.Now().UTC(),
		Severity:  inferSeverity(line),
		Message:   line,
		Source:    fmt.Sprintf("%s:%s", sourceName, filepath.Base(path)),
	}
}

// inferSeverity guesses a severity from free-text content by scanning for
// common level tokens. It defaults to info when nothing matches.
func inferSeverity(text string) domain.Severity {
	u := strings.ToUpper(text)
	switch {
	case containsToken(u, "CRITICAL", "FATAL", "EMERG", "PANIC"):
		return domain.SeverityCritical
	case containsToken(u, "ERROR", "ERR", "EXCEPTION", "FAIL"):
		return domain.SeverityError
	case containsToken(u, "WARNING", "WARN"):
		return domain.SeverityWarning
	case containsToken(u, "DEBUG", "TRACE"):
		return domain.SeverityDebug
	case containsToken(u, "INFO", "NOTICE"):
		return domain.SeverityInfo
	default:
		return domain.SeverityInfo
	}
}

// containsToken reports whether s contains any of the given uppercase tokens.
func containsToken(s string, tokens ...string) bool {
	for _, t := range tokens {
		if strings.Contains(s, t) {
			return true
		}
	}
	return false
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

// timestampLayouts are the formats parseTimestamp tries, in order.
var timestampLayouts = []string{
	time.RFC3339Nano,
	time.RFC3339,
	"2006-01-02T15:04:05",
	"2006-01-02 15:04:05",
}

// parseTimestamp parses a timestamp string using a small set of common layouts,
// falling back to the current UTC time when the value is empty or unparseable.
func parseTimestamp(v string) time.Time {
	if v == "" {
		return time.Now().UTC()
	}
	for _, layout := range timestampLayouts {
		if t, err := time.Parse(layout, v); err == nil {
			return t.UTC()
		}
	}
	return time.Now().UTC()
}
