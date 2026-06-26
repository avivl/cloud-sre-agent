// Package dogfood_test is the hermetic integration test for the fully-local
// dogfooding loop. It drives the same spine `make dogfood` exercises —
// generator -> filesystem ingest -> threshold detector -> pipeline (stub
// provider) -> local-patch delivery — entirely in-process and asserts that a
// remediation artifact is written.
//
// It is deterministic and needs NO credentials and NO network: the generator
// is seeded by index (not time/random) and the stub provider makes no external
// call. It runs as part of `go test ./...`; it is fast (sub-second) so it is
// intentionally NOT build-tagged out of normal unit runs.
package dogfood_test

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"

	generator "github.com/avivl/cloud-sre-agent/dogfood/generator"
	"github.com/avivl/cloud-sre-agent/internal/detect"
	"github.com/avivl/cloud-sre-agent/internal/ingest/file"
	"github.com/avivl/cloud-sre-agent/internal/llm/stub"
	"github.com/avivl/cloud-sre-agent/internal/pipeline"
	"github.com/avivl/cloud-sre-agent/internal/scm/local"
	"github.com/avivl/cloud-sre-agent/internal/security"
)

// TestDogfood_LogToRemediationArtifact runs the dogfood flow offline and asserts
// the stub-driven pipeline writes a local remediation patch + metadata sidecar.
func TestDogfood_LogToRemediationArtifact(t *testing.T) {
	ctx := context.Background()
	dir := t.TempDir()

	// 1. Generate a deterministic ERROR burst and write it to a log file. This
	//    is the exact content the dogfood generator binary appends; we call its
	//    library function directly so the test stays in-process.
	logPath := filepath.Join(dir, "dogfood.log")
	lines := generator.Generate(8)
	require.Len(t, lines, 8)
	body := []byte("")
	for _, l := range lines {
		body = append(body, []byte(l+"\n")...)
	}
	require.NoError(t, os.WriteFile(logPath, body, 0o600))

	// 2. Real filesystem source, non-watch: read to EOF then close. JSON
	//    encoding matches the generator's JSON-lines output.
	src, err := file.New(file.Config{Path: logPath, Encoding: file.EncodingJSON})
	require.NoError(t, err)
	t.Cleanup(func() { _ = src.Close() })

	stream, err := src.Stream(ctx)
	require.NoError(t, err)

	// 3. Detector with default thresholds — the 8-line all-error burst trips
	//    the 5-event / 50%-error-rate defaults inside one window.
	detector := detect.New(detect.Config{})

	// 4. Pipeline: the REAL stub provider + real local-patch target. No mock,
	//    no creds, no network.
	outDir := filepath.Join(dir, "out")
	pipe, err := pipeline.New(stub.New(), security.New(), local.New(outDir))
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

	// 6. Assert a remediation artifact was written. The stub remediation targets
	//    "stub.txt", so the local target writes stub.txt.patch + sidecar.
	require.GreaterOrEqual(t, delivered, 1, "expected at least one incident remediated")

	patch, err := os.ReadFile(filepath.Join(outDir, "stub.txt.patch"))
	require.NoError(t, err)
	require.NotEmpty(t, patch, "patch file must not be empty")

	metaBytes, err := os.ReadFile(filepath.Join(outDir, "stub.txt.meta.json"))
	require.NoError(t, err)
	var meta map[string]any
	require.NoError(t, json.Unmarshal(metaBytes, &meta))
	require.Equal(t, "stub.txt", meta["file_path"])
}
