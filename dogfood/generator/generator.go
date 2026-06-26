// Package generator produces realistic, varied ERROR-level log lines for the
// fully-local dogfooding loop. The output is JSON Lines matching the shape the
// filesystem ingest source parses into domain.LogEvent (timestamp/severity/
// message/labels), so the threshold detector trips on the resulting error
// burst.
//
// Generation is intentionally DETERMINISTIC: there is no randomness and no
// wall-clock dependence. Every line is derived from its index, so repeated runs
// produce byte-identical output. This keeps `make dogfood` and the integration
// test reproducible offline with no credentials. The library is consumed both
// by the generator binary (dogfood/cmd/generator) and the integration test.
package generator

import (
	"fmt"
	"os"
	"strings"
	"time"
)

// errorTemplates are rotated by line index to give the burst some variety
// without any randomness. Every entry is ERROR or higher so the detector's
// error-rate threshold trips quickly.
var errorTemplates = []struct {
	severity string
	service  string
	message  string
}{
	{"error", "api", "failed to connect to database: connection refused"},
	{"error", "worker", "job processing failed: context deadline exceeded"},
	{"critical", "api", "out of memory: cannot allocate request buffer"},
	{"error", "gateway", "upstream returned 503 service unavailable"},
	{"error", "api", "panic recovered in request handler: nil map write"},
	{"critical", "scheduler", "leader election lost: etcd unreachable"},
	{"error", "worker", "failed to publish event: broker connection reset"},
	{"error", "gateway", "TLS handshake timeout to backend"},
}

// baseTime is a fixed anchor for generated timestamps. Using a constant instead
// of time.Now keeps the output deterministic and keeps every line inside the
// detector's sliding window (lines are one second apart).
var baseTime = time.Date(2026, 1, 1, 12, 0, 0, 0, time.UTC)

// Generate returns count deterministic JSON-lines ERROR/CRITICAL log records.
// Line i is derived solely from i (template rotation + a +1s timestamp step),
// so the result is reproducible and the timestamps stay within one detector
// window.
func Generate(count int) []string {
	lines := make([]string, 0, count)
	for i := 0; i < count; i++ {
		tpl := errorTemplates[i%len(errorTemplates)]
		ts := baseTime.Add(time.Duration(i) * time.Second).Format(time.RFC3339)
		// Hand-rendered JSON: the fields are fixed and free of characters that
		// need escaping, so this avoids pulling in encoding/json for trivially
		// safe content while still emitting valid JSON Lines.
		line := fmt.Sprintf(
			`{"timestamp":%q,"severity":%q,"message":%q,"labels":{"svc":%q,"seq":"%d"}}`,
			ts, tpl.severity, tpl.message, tpl.service, i,
		)
		lines = append(lines, line)
	}
	return lines
}

// AppendToFile generates count lines and appends them to the file at path,
// creating it if it does not exist. It is the one side-effecting helper the
// generator binary needs.
func AppendToFile(path string, count int) error {
	if strings.TrimSpace(path) == "" {
		return fmt.Errorf("generator: path is required")
	}
	if count <= 0 {
		return fmt.Errorf("generator: count must be positive, got %d", count)
	}

	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644) //nolint:gosec // operator-supplied path
	if err != nil {
		return fmt.Errorf("generator: open %q: %w", path, err)
	}
	defer func() { _ = f.Close() }()

	if _, err := f.WriteString(strings.Join(Generate(count), "\n") + "\n"); err != nil {
		return fmt.Errorf("generator: write %q: %w", path, err)
	}
	return nil
}
