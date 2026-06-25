package obs

import (
	"bytes"
	"context"
	"encoding/json"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestFlowIDRoundTrip(t *testing.T) {
	ctx := context.Background()
	assert.Equal(t, "", FlowID(ctx))
	ctx = WithFlowID(ctx, "flow-123")
	assert.Equal(t, "flow-123", FlowID(ctx))
}

func TestLoggerFrom_AddsFlowID(t *testing.T) {
	var buf bytes.Buffer
	p := Setup(Options{Format: "json", Level: "info", Writer: &buf})
	require.NotNil(t, p.Logger)

	ctx := WithFlowID(context.Background(), "flow-abc")
	LoggerFrom(ctx, p.Logger).Info("hello")

	var rec map[string]any
	require.NoError(t, json.Unmarshal(bytes.TrimSpace(buf.Bytes()), &rec))
	assert.Equal(t, "flow-abc", rec["flow_id"])
	assert.Equal(t, "hello", rec["msg"])
}

func TestSetup_RedactsSensitiveFields(t *testing.T) {
	var buf bytes.Buffer
	p := Setup(Options{Format: "json", Writer: &buf})
	p.Logger.Info("ingest",
		"raw", "patient SSN 123-45-6789",
		"source", "file:/var/log/patient-jane-doe.log",
		"error", "failed for patient 123-45-6789",
		"region", "us-central1",
	)

	out := buf.String()
	assert.Contains(t, out, RedactedPlaceholder)
	assert.NotContains(t, out, "123-45-6789")
	// error and source can echo raw content / PHI, so their values are masked.
	assert.NotContains(t, out, "patient-jane-doe")
	assert.Contains(t, out, "us-central1") // non-sensitive field preserved
}

func TestRedacted(t *testing.T) {
	assert.Equal(t, RedactedPlaceholder, Redacted("prompt", "leak me").Value.String())
	// source and error are now sensitive keys.
	assert.Equal(t, RedactedPlaceholder, Redacted("source", "file").Value.String())
	assert.Equal(t, RedactedPlaceholder, Redacted("error", "boom for bob@x.com").Value.String())
	// A non-sensitive key passes through.
	assert.Equal(t, "us-central1", Redacted("region", "us-central1").Value.String())
}

func TestSetup_Shutdown(t *testing.T) {
	p := Setup(Options{Writer: &bytes.Buffer{}})
	require.NoError(t, p.Shutdown(context.Background()))
}

func TestSetup_TextFormat(t *testing.T) {
	var buf bytes.Buffer
	p := Setup(Options{Format: "text", Writer: &buf})
	p.Logger.Warn("watch out", "secret", "hunter2")
	assert.True(t, strings.Contains(buf.String(), RedactedPlaceholder))
	assert.NotContains(t, buf.String(), "hunter2")
}

func TestBuildTracerProvider_None(t *testing.T) {
	tp, err := buildTracerProvider(TracingOptions{Exporter: TraceExporterNone}, &bytes.Buffer{})
	require.NoError(t, err)
	require.NotNil(t, tp)
	require.NoError(t, tp.Shutdown(context.Background()))
}

func TestBuildTracerProvider_EmptyDefaultsToNone(t *testing.T) {
	tp, err := buildTracerProvider(TracingOptions{}, &bytes.Buffer{})
	require.NoError(t, err)
	require.NotNil(t, tp)
	require.NoError(t, tp.Shutdown(context.Background()))
}

func TestBuildTracerProvider_Stdout(t *testing.T) {
	tp, err := buildTracerProvider(TracingOptions{Exporter: TraceExporterStdout}, &bytes.Buffer{})
	require.NoError(t, err)
	require.NotNil(t, tp)
	require.NoError(t, tp.Shutdown(context.Background()))
}

func TestBuildTracerProvider_CloudTraceConstructsWithProject(t *testing.T) {
	// With a project set, buildTracerProvider reaches the cloudtrace exporter
	// branch. With ambient credentials it fully constructs; without them (e.g.
	// CI) the exporter fails to initialize. Either way this pins that the
	// cloudtrace exporter itself was attempted (the "cloudtrace exporter:" wrap,
	// not the project-required guard) — the GCP runtime supplies credentials.
	tp, err := buildTracerProvider(TracingOptions{Exporter: TraceExporterCloudTrace, Project: "test-project"}, &bytes.Buffer{})
	if err != nil {
		require.Contains(t, err.Error(), "cloudtrace exporter:")
		return
	}
	require.NotNil(t, tp)
	require.NoError(t, tp.Shutdown(context.Background()))
}

func TestBuildTracerProvider_CloudTraceRequiresProject(t *testing.T) {
	_, err := buildTracerProvider(TracingOptions{Exporter: TraceExporterCloudTrace}, &bytes.Buffer{})
	require.Error(t, err)
}

func TestBuildTracerProvider_UnknownExporter(t *testing.T) {
	_, err := buildTracerProvider(TracingOptions{Exporter: TraceExporter("bogus")}, &bytes.Buffer{})
	require.Error(t, err)
}

func TestBuildTracerProvider_CaseInsensitive(t *testing.T) {
	tp, err := buildTracerProvider(TracingOptions{Exporter: TraceExporter("STDOUT")}, &bytes.Buffer{})
	require.NoError(t, err)
	require.NoError(t, tp.Shutdown(context.Background()))
}

func TestValidTraceExporter(t *testing.T) {
	for _, e := range []TraceExporter{"none", "stdout", "cloudtrace", "", "NONE", "CloudTrace"} {
		assert.Truef(t, ValidTraceExporter(e), "exporter %q should be valid", e)
	}
	assert.False(t, ValidTraceExporter("otlp"))
	assert.False(t, ValidTraceExporter("bogus"))
}

func TestSetup_CloudTraceFallsBackOnFailure(t *testing.T) {
	// cloudtrace without a project fails to construct; Setup must fall back to a
	// working no-op provider rather than returning a nil tracer.
	var buf bytes.Buffer
	p := Setup(Options{Writer: &buf, Tracing: TracingOptions{Exporter: TraceExporterCloudTrace}})
	require.NotNil(t, p.Tracer)
	assert.Contains(t, buf.String(), "trace exporter setup failed")
	require.NoError(t, p.Shutdown(context.Background()))
}
