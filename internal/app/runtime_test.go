package app

import (
	"context"
	"errors"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/avivl/cloud-sre-agent/internal/config"
	"github.com/avivl/cloud-sre-agent/internal/detect"
	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/ingest"
	"github.com/avivl/cloud-sre-agent/internal/llm"
	"github.com/avivl/cloud-sre-agent/internal/llm/stub"
	"github.com/avivl/cloud-sre-agent/internal/pipeline"
	"github.com/avivl/cloud-sre-agent/internal/scm"
	"github.com/avivl/cloud-sre-agent/internal/security"
)

// notActionableProvider returns a triage that is not actionable, so the pipeline
// stops at triage with ErrNotActionable.
type notActionableProvider struct{}

func (notActionableProvider) Name() string { return "not-actionable" }
func (notActionableProvider) Generate(_ context.Context, _ llm.Request) (llm.Response, error) {
	return llm.Response{
		Text:         `{"category":"noise","severity":"info","confidence":1,"actionable":false,"reasoning":"benign"}`,
		Model:        "not-actionable",
		FinishReason: "stop",
	}, nil
}

// --- test doubles ---

// chanSource is an ingest.LogSource backed by a caller-supplied channel. It
// optionally reports a terminal error via Err() to exercise sourcesErr.
type chanSource struct {
	name string
	ch   <-chan domain.LogEvent
	err  error
}

func (s *chanSource) Name() string { return s.name }
func (s *chanSource) Stream(_ context.Context) (<-chan domain.LogEvent, error) {
	return s.ch, nil
}
func (s *chanSource) Close() error { return nil }
func (s *chanSource) Err() error   { return s.err }

// streamErrSource fails on Stream to exercise merge's error path.
type streamErrSource struct{ name string }

func (s *streamErrSource) Name() string { return s.name }
func (s *streamErrSource) Stream(_ context.Context) (<-chan domain.LogEvent, error) {
	return nil, errors.New("stream boom")
}
func (s *streamErrSource) Close() error { return nil }

// mockTarget records delivered changes; Deliver can be made to fail.
type mockTarget struct {
	mu        sync.Mutex
	delivered []scm.Change
	failErr   error
	gotCh     chan struct{}
}

func newMockTarget() *mockTarget { return &mockTarget{gotCh: make(chan struct{}, 8)} }

// sources packs test doubles into the []ingest.LogSource slice the run loop takes.
func sources(ss ...ingest.LogSource) []ingest.LogSource { return ss }

func (m *mockTarget) Name() string { return "mock" }
func (m *mockTarget) Deliver(_ context.Context, c scm.Change) (scm.Ref, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.failErr != nil {
		return scm.Ref{}, m.failErr
	}
	m.delivered = append(m.delivered, c)
	select {
	case m.gotCh <- struct{}{}:
	default:
	}
	return scm.Ref{ID: "mock-ref", URL: "mock://ref"}, nil
}

func (m *mockTarget) count() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return len(m.delivered)
}

// rejectValidator rejects every patch, to drive handleIncident's error arm.
type rejectValidator struct{}

func (rejectValidator) Validate(_ context.Context, _ string, _ string) (pipeline.ValidationResult, error) {
	return pipeline.ValidationResult{OK: false, Diagnostics: []string{"rejected"}}, nil
}

func newStubPipeline(t *testing.T, target pipeline.Deliverer, validator pipeline.CodeValidator) *pipeline.Pipeline {
	t.Helper()
	opts := []pipeline.Option{pipeline.WithLogger(testLogger())}
	if validator != nil {
		opts = append(opts, pipeline.WithValidator(validator))
	}
	pipe, err := pipeline.New(stub.New(), security.New(), target, opts...)
	if err != nil {
		t.Fatalf("build stub pipeline: %v", err)
	}
	return pipe
}

func validIncident() domain.Incident {
	return domain.Incident{
		ID:            "inc-1",
		Pattern:       "error-burst",
		SeverityScore: 0.9,
		Summary:       "stub incident",
		DetectedAt:    time.Now().UTC(),
	}
}

// --- fanIn ---

func TestFanIn_MergesAndClosesWhenAllClose(t *testing.T) {
	a := make(chan domain.LogEvent, 2)
	b := make(chan domain.LogEvent, 2)
	a <- domain.LogEvent{ID: "a1", Message: "m", Severity: domain.SeverityError}
	b <- domain.LogEvent{ID: "b1", Message: "m", Severity: domain.SeverityError}
	close(a)
	close(b)

	out := fanIn(context.Background(), []<-chan domain.LogEvent{a, b})
	got := map[string]bool{}
	for ev := range out {
		got[ev.ID] = true
	}
	if !got["a1"] || !got["b1"] {
		t.Fatalf("fanIn missing events: %v", got)
	}
	if len(got) != 2 {
		t.Fatalf("fanIn got %d events, want 2", len(got))
	}
}

func TestFanIn_RespectsContextCancel(t *testing.T) {
	a := make(chan domain.LogEvent) // never closed, never sends
	ctx, cancel := context.WithCancel(context.Background())
	out := fanIn(ctx, []<-chan domain.LogEvent{a})
	cancel()

	select {
	case _, ok := <-out:
		if ok {
			t.Fatal("fanIn delivered unexpected event after cancel")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("fanIn did not close after context cancel")
	}
}

func TestFanIn_Empty(t *testing.T) {
	out := fanIn(context.Background(), nil)
	select {
	case _, ok := <-out:
		if ok {
			t.Fatal("empty fanIn should not deliver")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("empty fanIn never closed")
	}
}

// --- sourcesErr ---

func TestSourcesErr_ReturnsTerminalError(t *testing.T) {
	boom := errors.New("source died")
	srcs := sources(
		&chanSource{name: "ok"},
		&chanSource{name: "bad", err: boom},
	)
	if got := sourcesErr(srcs); !errors.Is(got, boom) {
		t.Fatalf("sourcesErr = %v, want %v", got, boom)
	}
}

func TestSourcesErr_NilWhenClean(t *testing.T) {
	srcs := sources(&chanSource{name: "ok"}, &streamErrSource{name: "no-err-method"})
	if got := sourcesErr(srcs); got != nil {
		t.Fatalf("sourcesErr = %v, want nil", got)
	}
}

// --- handleIncident ---

func TestHandleIncident_ActionableDelivers(t *testing.T) {
	target := newMockTarget()
	pipe := newStubPipeline(t, target, nil) // noop validator default
	handleIncident(context.Background(), pipe, validIncident(), security.New(), testLogger())
	if target.count() != 1 {
		t.Fatalf("handleIncident actionable: delivered %d, want 1", target.count())
	}
}

func TestHandleIncident_ErrorSanitizedNoPanic(t *testing.T) {
	target := newMockTarget()
	// Reject validator forces a pipeline error before delivery.
	pipe := newStubPipeline(t, target, rejectValidator{})
	// Must not panic and must not deliver.
	handleIncident(context.Background(), pipe, validIncident(), security.New(), testLogger())
	if target.count() != 0 {
		t.Fatalf("handleIncident error path delivered %d, want 0", target.count())
	}
}

func TestHandleIncident_NotActionableSkips(t *testing.T) {
	target := newMockTarget()
	// A not-actionable triage short-circuits the pipeline before delivery.
	pipe, err := pipeline.New(notActionableProvider{}, security.New(), target, pipeline.WithLogger(testLogger()))
	if err != nil {
		t.Fatalf("build pipeline: %v", err)
	}
	handleIncident(context.Background(), pipe, validIncident(), security.New(), testLogger())
	if target.count() != 0 {
		t.Fatalf("handleIncident not-actionable delivered %d, want 0", target.count())
	}
}

func TestHandleIncident_InvalidIncidentLoggedNoPanic(t *testing.T) {
	target := newMockTarget()
	pipe := newStubPipeline(t, target, nil)
	bad := domain.Incident{ID: "", Pattern: ""}
	handleIncident(context.Background(), pipe, bad, security.New(), testLogger())
	if target.count() != 0 {
		t.Fatalf("handleIncident invalid incident delivered %d, want 0", target.count())
	}
}

// --- consume end-to-end ---

func TestConsume_DeliversRemediation(t *testing.T) {
	ch := make(chan domain.LogEvent)
	src := &chanSource{name: "test", ch: ch}
	target := newMockTarget()
	pipe := newStubPipeline(t, target, nil)
	// Detector tuned to fire quickly: 3 events, 50% error rate, no cooldown gap
	// needed for a single incident.
	detector := detect.New(detect.Config{MinEvents: 3, ErrorRateThreshold: 0.5})

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	done := make(chan error, 1)
	go func() {
		done <- consume(ctx, sources(src), detector, pipe, security.New(), testLogger())
	}()

	// Emit an error burst to trip the detector.
	base := time.Now().UTC()
	for i := 0; i < 5; i++ {
		ch <- domain.LogEvent{
			ID:        "e" + string(rune('0'+i)),
			Message:   "boom",
			Severity:  domain.SeverityError,
			Timestamp: base.Add(time.Duration(i) * time.Millisecond),
		}
	}

	select {
	case <-target.gotCh:
		// delivered
	case <-time.After(3 * time.Second):
		t.Fatal("consume did not deliver a remediation in time")
	}

	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("consume returned error on cancel: %v", err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("consume did not return after cancel")
	}
	if target.count() < 1 {
		t.Fatalf("consume delivered %d remediations, want >=1", target.count())
	}
}

func TestConsume_ReturnsCleanlyOnSourcesExhausted(t *testing.T) {
	ch := make(chan domain.LogEvent)
	close(ch) // immediately exhausted, no error
	src := &chanSource{name: "test", ch: ch}
	target := newMockTarget()
	pipe := newStubPipeline(t, target, nil)
	detector := detect.New(detect.Config{})

	err := consume(context.Background(), sources(src), detector, pipe, security.New(), testLogger())
	if err != nil {
		t.Fatalf("consume on clean drain: %v", err)
	}
}

func TestConsume_ReturnsErrorWhenSourceFailed(t *testing.T) {
	ch := make(chan domain.LogEvent)
	close(ch)
	boom := errors.New("pubsub revoked")
	src := &chanSource{name: "test", ch: ch, err: boom}
	target := newMockTarget()
	pipe := newStubPipeline(t, target, nil)
	detector := detect.New(detect.Config{})

	err := consume(context.Background(), sources(src), detector, pipe, security.New(), testLogger())
	if err == nil || !errors.Is(err, boom) {
		t.Fatalf("consume on source failure = %v, want wrap of %v", err, boom)
	}
}

func TestConsume_MergeStreamError(t *testing.T) {
	src := &streamErrSource{name: "bad"}
	pipe := newStubPipeline(t, newMockTarget(), nil)
	detector := detect.New(detect.Config{})
	err := consume(context.Background(), sources(src), detector, pipe, security.New(), testLogger())
	if err == nil {
		t.Fatal("consume with failing Stream: expected error")
	}
}

func TestConsume_ReturnsCleanlyOnContextCancel(t *testing.T) {
	ch := make(chan domain.LogEvent) // never sends, never closes
	src := &chanSource{name: "test", ch: ch}
	pipe := newStubPipeline(t, newMockTarget(), nil)
	detector := detect.New(detect.Config{})

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() {
		done <- consume(ctx, sources(src), detector, pipe, security.New(), testLogger())
	}()
	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("consume on cancel: %v", err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("consume did not return on cancel")
	}
}

// --- Run (composition root happy path) ---

func TestRun_WiresAndReturnsOnCancel(t *testing.T) {
	dir := t.TempDir()
	logPath := dir + "/in.log"
	if err := os.WriteFile(logPath, []byte(""), 0o600); err != nil {
		t.Fatalf("seed log: %v", err)
	}
	cfg := config.Config{
		Sources:   []config.SourceConfig{{Type: config.SourceTypeFile, Path: logPath}},
		LLM:       config.LLMConfig{Provider: config.KindStub, Model: "stub"},
		Output:    config.OutputConfig{Dir: dir + "/out"},
		Target:    config.TargetLocal,
		Validator: config.ValidatorNone,
	}

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- Run(ctx, cfg, testLogger()) }()

	// Give Run a beat to wire up and start streaming, then cancel.
	time.Sleep(100 * time.Millisecond)
	cancel()

	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("Run returned error on cancel: %v", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("Run did not return after cancel")
	}
}

func TestRun_BuildProviderError(t *testing.T) {
	t.Setenv(openAIAPIKeyEnv, "")
	cfg := config.Config{
		LLM:    config.LLMConfig{Provider: config.KindOpenAI, Model: "gpt-4o-mini"},
		Target: config.TargetLocal,
	}
	if err := Run(context.Background(), cfg, testLogger()); err == nil {
		t.Fatal("Run with bad provider: expected error")
	}
}

func TestRun_BuildTargetError(t *testing.T) {
	t.Setenv(config.GitHubTokenEnv, "")
	cfg := config.Config{
		LLM:    config.LLMConfig{Provider: config.KindStub, Model: "stub"},
		Target: config.TargetGitHub,
	}
	cfg.GitHub.Owner = "o"
	cfg.GitHub.Repo = "r"
	if err := Run(context.Background(), cfg, testLogger()); err == nil {
		t.Fatal("Run with bad target: expected error")
	}
}

func TestRun_BuildSourcesError(t *testing.T) {
	cfg := config.Config{
		Sources:   []config.SourceConfig{{Type: "bogus"}},
		LLM:       config.LLMConfig{Provider: config.KindStub, Model: "stub"},
		Output:    config.OutputConfig{Dir: t.TempDir()},
		Target:    config.TargetLocal,
		Validator: config.ValidatorNone,
	}
	if err := Run(context.Background(), cfg, testLogger()); err == nil {
		t.Fatal("Run with bad source: expected error")
	}
}

func TestRun_NilContext(t *testing.T) {
	// nil context is normalized to Background; with no sources the loop drains
	// immediately and returns nil.
	cfg := config.Config{
		LLM:       config.LLMConfig{Provider: config.KindStub, Model: "stub"},
		Output:    config.OutputConfig{Dir: t.TempDir()},
		Target:    config.TargetLocal,
		Validator: config.ValidatorNone,
	}
	if err := Run(nil, cfg, testLogger()); err != nil { //nolint:staticcheck // intentionally testing nil ctx normalization
		t.Fatalf("Run nil ctx: %v", err)
	}
}
