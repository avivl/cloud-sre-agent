package pipeline_test

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"

	"github.com/avivl/cloud-sre-agent/internal/detect"
	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/ingest/file"
	"github.com/avivl/cloud-sre-agent/internal/llm"
	"github.com/avivl/cloud-sre-agent/internal/pipeline"
	"github.com/avivl/cloud-sre-agent/internal/scm/local"
	"github.com/avivl/cloud-sre-agent/internal/security"
)

// e2eProvider is a deterministic mock llm.Provider returning canned JSON per
// schema name. No network calls are made.
type e2eProvider struct {
	byName map[string]string
}

func (p *e2eProvider) Name() string { return "e2e-mock" }

func (p *e2eProvider) Generate(_ context.Context, req llm.Request) (llm.Response, error) {
	return llm.Response{Text: p.byName[req.SchemaName], Model: "e2e-mock"}, nil
}

// sampleLog is a small JSON-lines log with an error burst that should trip the
// detector's error-rate threshold. It includes an email so the e2e flow also
// exercises sanitization end to end.
const sampleLog = `{"time":"2026-01-01T00:00:00Z","level":"info","msg":"request ok"}
{"time":"2026-01-01T00:00:01Z","level":"error","msg":"db timeout for ops@example.com"}
{"time":"2026-01-01T00:00:02Z","level":"error","msg":"db timeout"}
{"time":"2026-01-01T00:00:03Z","level":"error","msg":"db timeout"}
{"time":"2026-01-01T00:00:04Z","level":"error","msg":"db timeout"}
`

func TestE2E_LogToRemediationArtifact(t *testing.T) {
	ctx := context.Background()

	// 1. Sample log on disk (TempDir keeps it deterministic and avoids the
	//    *.log .gitignore rule).
	dir := t.TempDir()
	logPath := filepath.Join(dir, "sample.log")
	require.NoError(t, os.WriteFile(logPath, []byte(sampleLog), 0o600))

	// 2. Real filesystem source, non-watch: read to EOF then close.
	src, err := file.New(file.Config{Path: logPath, Encoding: file.EncodingJSON})
	require.NoError(t, err)
	t.Cleanup(func() { _ = src.Close() })

	stream, err := src.Stream(ctx)
	require.NoError(t, err)

	// 3. Detector: low threshold so the error burst trips it.
	detector := detect.New(detect.Config{
		MinEvents:          3,
		ErrorRateThreshold: 0.5,
		Cooldown:           1, // effectively no cooldown for the test
	})

	// 4. Pipeline: mock provider + real local-patch target on a temp out dir.
	outDir := filepath.Join(dir, "out")
	provider := &e2eProvider{byName: map[string]string{
		"TriageResult":    mustMarshal(t, domain.TriageResult{Category: "database", Severity: domain.SeverityError, Confidence: 0.9, Actionable: true, Reasoning: "db timeouts"}),
		"Analysis":        mustMarshal(t, domain.Analysis{RootCause: "pool exhausted", ProposedFix: "raise pool", Confidence: 0.8}),
		"RemediationPlan": mustMarshal(t, domain.RemediationPlan{RootCauseAnalysis: "pool exhausted", ProposedFix: "bump max conns", CodePatch: "--- a/db.go\n+++ b/db.go\n@@\n-max=10\n+max=50\n", TargetFile: "db.go", EstimatedEffort: "1h"}),
	}}
	pipe, err := pipeline.New(provider, security.New(), local.New(outDir))
	require.NoError(t, err)

	// 5. Consume loop: drain the stream into the detector, process incidents.
	var delivered int
	for ev := range stream {
		if inc := detector.Observe(ev); inc != nil {
			res, perr := pipe.Process(ctx, *inc)
			require.NoError(t, perr)
			require.NotEmpty(t, res.Ref.ID)
			delivered++
		}
	}

	// 6. Assert a remediation artifact was written.
	require.GreaterOrEqual(t, delivered, 1, "expected at least one incident remediated")

	patch, err := os.ReadFile(filepath.Join(outDir, "db.go.patch"))
	require.NoError(t, err)
	require.Contains(t, string(patch), "max=50")

	metaBytes, err := os.ReadFile(filepath.Join(outDir, "db.go.meta.json"))
	require.NoError(t, err)
	var meta map[string]any
	require.NoError(t, json.Unmarshal(metaBytes, &meta))
	require.Equal(t, "db.go", meta["file_path"])
}

func mustMarshal(t *testing.T, v any) string {
	t.Helper()
	b, err := json.Marshal(v)
	require.NoError(t, err)
	return string(b)
}
