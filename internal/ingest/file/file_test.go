package file

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/ingest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// staticCompile asserts FileSystemSource satisfies the port at compile time.
var _ ingest.LogSource = (*FileSystemSource)(nil)

// collect drains ch until it closes or the deadline elapses.
func collect(t *testing.T, ch <-chan domain.LogEvent, want int, timeout time.Duration) []domain.LogEvent {
	t.Helper()
	var got []domain.LogEvent
	deadline := time.After(timeout)
	for {
		if want > 0 && len(got) >= want {
			return got
		}
		select {
		case ev, ok := <-ch:
			if !ok {
				return got
			}
			got = append(got, ev)
		case <-deadline:
			if want > 0 {
				t.Fatalf("timed out: got %d events, want %d", len(got), want)
			}
			return got
		}
	}
}

func writeFile(t *testing.T, dir, name, content string) string {
	t.Helper()
	p := filepath.Join(dir, name)
	require.NoError(t, os.WriteFile(p, []byte(content), 0o600))
	return p
}

func TestNew(t *testing.T) {
	tests := []struct {
		name    string
		cfg     Config
		wantErr bool
	}{
		{name: "empty path", cfg: Config{}, wantErr: true},
		{name: "whitespace path", cfg: Config{Path: "   "}, wantErr: true},
		{name: "bad encoding", cfg: Config{Path: "x.log", Encoding: "yaml"}, wantErr: true},
		{name: "valid default", cfg: Config{Path: "x.log"}, wantErr: false},
		{name: "valid json", cfg: Config{Path: "x.log", Encoding: EncodingJSON}, wantErr: false},
		{name: "valid text", cfg: Config{Path: "x.log", Encoding: EncodingText}, wantErr: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			s, err := New(tt.cfg)
			if tt.wantErr {
				require.Error(t, err)
				return
			}
			require.NoError(t, err)
			require.NotNil(t, s)
			assert.Equal(t, sourceName, s.Name())
		})
	}
}

func TestNewDefaults(t *testing.T) {
	s, err := New(Config{Path: "x.log"})
	require.NoError(t, err)
	assert.Equal(t, EncodingAuto, s.enc)
	assert.Equal(t, defaultPollInterval, s.poll)
	assert.NotNil(t, s.log)
}

func TestStreamPlainText(t *testing.T) {
	dir := t.TempDir()
	p := writeFile(t, dir, "app.log",
		"INFO starting up\nWARN low memory\nERROR boom\nCRITICAL fatal crash\nDEBUG verbose\njust a message\n")

	s, err := New(Config{Path: p, Encoding: EncodingText})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ch, err := s.Stream(context.Background())
	require.NoError(t, err)

	got := collect(t, ch, 0, 2*time.Second)
	require.Len(t, got, 6)

	wantSev := []domain.Severity{
		domain.SeverityInfo,
		domain.SeverityWarning,
		domain.SeverityError,
		domain.SeverityCritical,
		domain.SeverityDebug,
		domain.SeverityInfo, // no token -> default info
	}
	for i, ev := range got {
		assert.Equal(t, wantSev[i], ev.Severity, "line %d", i)
		require.NoError(t, ev.Validate(), "event %d must be valid", i)
		assert.NotEmpty(t, ev.ID)
		assert.Contains(t, ev.Source, "app.log")
	}
}

func TestStreamJSONLines(t *testing.T) {
	dir := t.TempDir()
	content := `{"timestamp":"2026-01-01T10:00:00Z","severity":"error","message":"db down","labels":{"svc":"api"}}
{"time":"2026-01-01T10:00:01Z","level":"warn","msg":"retrying"}
{"message":"no level here"}
`
	p := writeFile(t, dir, "app.json", content)

	s, err := New(Config{Path: p, Encoding: EncodingJSON})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ch, err := s.Stream(context.Background())
	require.NoError(t, err)
	got := collect(t, ch, 0, 2*time.Second)
	require.Len(t, got, 3)

	assert.Equal(t, domain.SeverityError, got[0].Severity)
	assert.Equal(t, "db down", got[0].Message)
	assert.Equal(t, "api", got[0].Labels["svc"])
	assert.Equal(t, time.Date(2026, 1, 1, 10, 0, 0, 0, time.UTC), got[0].Timestamp)

	assert.Equal(t, domain.SeverityWarning, got[1].Severity)
	assert.Equal(t, "retrying", got[1].Message)

	// No level -> inferred from message (no token) -> info.
	assert.Equal(t, domain.SeverityInfo, got[2].Severity)
	assert.Equal(t, "no level here", got[2].Message)
}

func TestStreamAutoMixed(t *testing.T) {
	dir := t.TempDir()
	content := `plain ERROR line
{"severity":"critical","message":"json crit"}
{not valid json but has ERROR}
`
	p := writeFile(t, dir, "mixed.log", content)

	s, err := New(Config{Path: p}) // default auto
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ch, err := s.Stream(context.Background())
	require.NoError(t, err)
	got := collect(t, ch, 0, 2*time.Second)
	require.Len(t, got, 3)

	assert.Equal(t, domain.SeverityError, got[0].Severity)
	assert.Equal(t, "plain ERROR line", got[0].Message)

	assert.Equal(t, domain.SeverityCritical, got[1].Severity)
	assert.Equal(t, "json crit", got[1].Message)

	// Invalid JSON under auto falls back to text; inferred ERROR from token.
	assert.Equal(t, domain.SeverityError, got[2].Severity)
	assert.Equal(t, "{not valid json but has ERROR}", got[2].Message)
}

func TestStreamSkipsBlankLines(t *testing.T) {
	dir := t.TempDir()
	p := writeFile(t, dir, "blanks.log", "INFO one\n\n\nINFO two\n")
	s, err := New(Config{Path: p})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ch, err := s.Stream(context.Background())
	require.NoError(t, err)
	got := collect(t, ch, 0, 2*time.Second)
	require.Len(t, got, 2)
}

func TestStreamGlob(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a.log", "INFO from a\n")
	writeFile(t, dir, "b.log", "INFO from b\n")
	writeFile(t, dir, "c.txt", "INFO ignored\n")

	s, err := New(Config{Path: filepath.Join(dir, "*.log")})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ch, err := s.Stream(context.Background())
	require.NoError(t, err)
	got := collect(t, ch, 0, 2*time.Second)
	require.Len(t, got, 2)
}

func TestStreamNoMatchNonWatchErrors(t *testing.T) {
	dir := t.TempDir()
	s, err := New(Config{Path: filepath.Join(dir, "missing-*.log")})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	_, err = s.Stream(context.Background())
	require.Error(t, err)
}

func TestStreamSingleUse(t *testing.T) {
	dir := t.TempDir()
	p := writeFile(t, dir, "app.log", "INFO one\nINFO two\n")

	s, err := New(Config{Path: p, Encoding: EncodingText})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ch, err := s.Stream(context.Background())
	require.NoError(t, err)
	require.NotNil(t, ch)

	// A second Stream call is rejected rather than starting a racing reader.
	_, err = s.Stream(context.Background())
	require.Error(t, err)
	require.Contains(t, err.Error(), "single-use")
}

func TestStreamBadGlob(t *testing.T) {
	s, err := New(Config{Path: "[bad"})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })
	_, err = s.Stream(context.Background())
	require.Error(t, err)
}

func TestStreamStaticFixture(t *testing.T) {
	s, err := New(Config{Path: filepath.Join("testdata", "sample.log")})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ch, err := s.Stream(context.Background())
	require.NoError(t, err)
	got := collect(t, ch, 0, 2*time.Second)
	require.Len(t, got, 5)

	assert.Equal(t, domain.SeverityInfo, got[0].Severity)
	assert.Equal(t, domain.SeverityWarning, got[1].Severity)
	assert.Equal(t, domain.SeverityError, got[2].Severity)
	assert.Equal(t, domain.SeverityCritical, got[3].Severity) // JSON line
	assert.Equal(t, "out of memory", got[3].Message)
	assert.Equal(t, "api", got[3].Labels["svc"])
	assert.Equal(t, domain.SeverityInfo, got[4].Severity) // plain, no token
}

func TestWatchTailsAppendedLines(t *testing.T) {
	dir := t.TempDir()
	p := writeFile(t, dir, "tail.log", "INFO initial\n")

	s, err := New(Config{
		Path:         p,
		Watch:        true,
		Encoding:     EncodingText,
		PollInterval: 20 * time.Millisecond,
	})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)

	ch, err := s.Stream(ctx)
	require.NoError(t, err)

	// First event: existing content.
	first := collect(t, ch, 1, 2*time.Second)
	require.Len(t, first, 1)
	assert.Equal(t, "INFO initial", first[0].Message)

	// Append more lines; watch loop should pick them up.
	f, err := os.OpenFile(p, os.O_APPEND|os.O_WRONLY, 0o600)
	require.NoError(t, err)
	_, err = f.WriteString("ERROR appended one\nWARN appended two\n")
	require.NoError(t, err)
	require.NoError(t, f.Close())

	more := collect(t, ch, 2, 2*time.Second)
	require.Len(t, more, 2)
	assert.Equal(t, "ERROR appended one", more[0].Message)
	assert.Equal(t, domain.SeverityError, more[0].Severity)
	assert.Equal(t, "WARN appended two", more[1].Message)
}

func TestWatchWaitsForFileToAppear(t *testing.T) {
	dir := t.TempDir()
	pattern := filepath.Join(dir, "later-*.log")

	s, err := New(Config{Path: pattern, Watch: true, PollInterval: 20 * time.Millisecond})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)

	// No match yet, but watch mode must not error.
	ch, err := s.Stream(ctx)
	require.NoError(t, err)

	writeFile(t, dir, "later-1.log", "CRITICAL appeared\n")

	got := collect(t, ch, 1, 2*time.Second)
	require.Len(t, got, 1)
	assert.Equal(t, "CRITICAL appeared", got[0].Message)
	assert.Equal(t, domain.SeverityCritical, got[0].Severity)
}

func TestCloseStopsStreamAndCloses(t *testing.T) {
	dir := t.TempDir()
	p := writeFile(t, dir, "c.log", "INFO one\n")
	s, err := New(Config{Path: p, Watch: true, PollInterval: 20 * time.Millisecond})
	require.NoError(t, err)

	ch, err := s.Stream(context.Background())
	require.NoError(t, err)
	_ = collect(t, ch, 1, 2*time.Second)

	require.NoError(t, s.Close())
	require.NoError(t, s.Close()) // idempotent

	// Channel must eventually close.
	select {
	case _, ok := <-ch:
		for ok {
			_, ok = <-ch
		}
	case <-time.After(2 * time.Second):
		t.Fatal("channel did not close after Close")
	}
}

func TestContextCancelStopsStream(t *testing.T) {
	dir := t.TempDir()
	p := writeFile(t, dir, "ctx.log", "INFO one\n")
	s, err := New(Config{Path: p, Watch: true, PollInterval: 20 * time.Millisecond})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ctx, cancel := context.WithCancel(context.Background())
	ch, err := s.Stream(ctx)
	require.NoError(t, err)
	_ = collect(t, ch, 1, 2*time.Second)

	cancel()
	select {
	case _, ok := <-ch:
		for ok {
			_, ok = <-ch
		}
	case <-time.After(2 * time.Second):
		t.Fatal("channel did not close after context cancel")
	}
}

func TestWatchHandlesTruncation(t *testing.T) {
	dir := t.TempDir()
	p := writeFile(t, dir, "rot.log", "INFO first long initial batch line\n")
	s, err := New(Config{Path: p, Watch: true, Encoding: EncodingText, PollInterval: 20 * time.Millisecond})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	ch, err := s.Stream(ctx)
	require.NoError(t, err)

	_ = collect(t, ch, 1, 2*time.Second)

	// Truncate and rewrite (simulating log rotation in place).
	require.NoError(t, os.WriteFile(p, []byte("ERROR after rotate\n"), 0o600))

	got := collect(t, ch, 1, 2*time.Second)
	require.Len(t, got, 1)
	assert.Equal(t, "ERROR after rotate", got[0].Message)
}

func TestParseTimestampFallbacks(t *testing.T) {
	tests := []struct {
		name  string
		input string
		zero  bool // expect "now" fallback (non-zero, recent)
	}{
		{name: "rfc3339", input: "2026-01-01T10:00:00Z"},
		{name: "space layout", input: "2026-01-01 10:00:00"},
		{name: "empty falls back", input: "", zero: true},
		{name: "garbage falls back", input: "not-a-time", zero: true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := parseTimestamp(tt.input)
			require.False(t, got.IsZero())
			if tt.zero {
				assert.WithinDuration(t, time.Now().UTC(), got, 5*time.Second)
			}
		})
	}
}

func TestInferSeverity(t *testing.T) {
	tests := []struct {
		text string
		want domain.Severity
	}{
		{"system PANIC now", domain.SeverityCritical},
		{"got an EXCEPTION", domain.SeverityError},
		{"WARN: slow", domain.SeverityWarning},
		{"TRACE detail", domain.SeverityDebug},
		{"NOTICE this", domain.SeverityInfo},
		{"nothing notable", domain.SeverityInfo},
	}
	for _, tt := range tests {
		t.Run(tt.text, func(t *testing.T) {
			assert.Equal(t, tt.want, inferSeverity(tt.text))
		})
	}
}

func TestUniqueIDs(t *testing.T) {
	dir := t.TempDir()
	p := writeFile(t, dir, "ids.log", "INFO a\nINFO b\nINFO c\n")
	s, err := New(Config{Path: p})
	require.NoError(t, err)
	t.Cleanup(func() { _ = s.Close() })

	ch, err := s.Stream(context.Background())
	require.NoError(t, err)
	got := collect(t, ch, 0, 2*time.Second)
	require.Len(t, got, 3)

	seen := map[string]bool{}
	for _, ev := range got {
		assert.False(t, seen[ev.ID], "duplicate id %s", ev.ID)
		seen[ev.ID] = true
	}
}
