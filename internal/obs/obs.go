// Package obs wires the agent's observability: a structured slog logger, OTel
// tracer/meter providers (no-op/stdout for the MVP), flow-id propagation
// through context and logs, and a redaction helper so raw log payloads never
// leak into traces or logs.
package obs

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"strings"

	cloudtrace "github.com/GoogleCloudPlatform/opentelemetry-operations-go/exporter/trace"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/stdout/stdouttrace"
	"go.opentelemetry.io/otel/metric"
	metricnoop "go.opentelemetry.io/otel/metric/noop"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
)

// TraceExporter selects how spans are exported.
type TraceExporter string

const (
	// TraceExporterNone records spans in the SDK but exports nothing. This is
	// the default and keeps the MVP's no-op/explicit behavior.
	TraceExporterNone TraceExporter = "none"
	// TraceExporterStdout writes spans to the configured writer for local
	// debugging.
	TraceExporterStdout TraceExporter = "stdout"
	// TraceExporterCloudTrace exports spans to Google Cloud Trace for the
	// configured project.
	TraceExporterCloudTrace TraceExporter = "cloudtrace"
)

// AllowedTraceExporters lists the valid TraceExporter values, for validation.
var AllowedTraceExporters = []TraceExporter{TraceExporterNone, TraceExporterStdout, TraceExporterCloudTrace}

// TracingOptions configures the trace exporter selector.
type TracingOptions struct {
	// Exporter is one of "none" (default), "stdout", or "cloudtrace".
	Exporter TraceExporter
	// Project is the GCP project ID, required by the cloudtrace exporter.
	Project string
}

// flowIDKey is the unexported context key for the flow id.
type flowIDKey struct{}

// flowIDLogKey is the structured-log attribute name for the flow id.
const flowIDLogKey = "flow_id"

// Options configures observability setup.
type Options struct {
	// Level is the minimum log level (debug, info, warn, error).
	Level string
	// Format is "json" (default) or "text".
	Format string
	// Writer is where logs are written; defaults to os.Stderr via the caller.
	Writer io.Writer
	// Tracing configures the span exporter. The zero value (empty exporter)
	// is treated as "none".
	Tracing TracingOptions
}

// Providers bundles the configured observability components.
type Providers struct {
	Logger *slog.Logger
	Tracer trace.Tracer
	Meter  metric.Meter
	// shutdown flushes/stops the tracer provider.
	shutdown func(context.Context) error
}

// Shutdown flushes and stops the providers. Safe to call once at exit.
func (p Providers) Shutdown(ctx context.Context) error {
	if p.shutdown == nil {
		return nil
	}
	return p.shutdown(ctx)
}

// Setup builds a slog logger plus OTel tracer/meter providers. The tracer's
// span export is selected by opts.Tracing: "none" (default) records spans in
// the SDK but exports nothing, "stdout" writes them to opts.Writer, and
// "cloudtrace" exports to Google Cloud Trace. The meter is a no-op.
//
// If the configured exporter fails to construct (e.g. cloudtrace without
// credentials), Setup logs the failure and falls back to the no-op exporter so
// the agent still starts; it never returns an error.
func Setup(opts Options) Providers {
	w := opts.Writer
	if w == nil {
		// Caller-supplied writer is preferred; nil is a programming choice
		// surfaced as a discard sink rather than a panic.
		w = io.Discard
	}

	handlerOpts := &slog.HandlerOptions{
		Level:       parseLevel(opts.Level),
		ReplaceAttr: redactAttr,
	}
	var handler slog.Handler
	if strings.EqualFold(opts.Format, "text") {
		handler = slog.NewTextHandler(w, handlerOpts)
	} else {
		handler = slog.NewJSONHandler(w, handlerOpts)
	}
	logger := slog.New(handler)

	tp, err := buildTracerProvider(opts.Tracing, w)
	if err != nil {
		logger.Warn("trace exporter setup failed, falling back to no-op",
			"exporter", string(opts.Tracing.Exporter), "err", err.Error())
		tp = sdktrace.NewTracerProvider()
	}
	otel.SetTracerProvider(tp)
	// HIPAA: span attributes must be sanitized before being recorded — raw log
	// content, prompts, and error strings can carry PHI. The slog handler above
	// redacts sensitive keys, but spans bypass it, so any attribute added here
	// (or in pipeline stages) must run through security.Sanitizer first.
	tracer := tp.Tracer("github.com/avivl/cloud-sre-agent")

	mp := metricnoop.NewMeterProvider()
	otel.SetMeterProvider(mp)
	meter := mp.Meter("github.com/avivl/cloud-sre-agent")

	return Providers{
		Logger:   logger,
		Tracer:   tracer,
		Meter:    meter,
		shutdown: tp.Shutdown,
	}
}

// buildTracerProvider constructs an SDK TracerProvider for the selected
// exporter. "none" (and the empty value) attaches no exporter; "stdout" and
// "cloudtrace" attach a batch span processor over their respective exporter.
func buildTracerProvider(opts TracingOptions, w io.Writer) (*sdktrace.TracerProvider, error) {
	switch normalizeExporter(opts.Exporter) {
	case TraceExporterNone:
		return sdktrace.NewTracerProvider(), nil
	case TraceExporterStdout:
		exp, err := stdouttrace.New(stdouttrace.WithWriter(w))
		if err != nil {
			return nil, fmt.Errorf("stdout trace exporter: %w", err)
		}
		return sdktrace.NewTracerProvider(sdktrace.WithBatcher(exp)), nil
	case TraceExporterCloudTrace:
		if strings.TrimSpace(opts.Project) == "" {
			return nil, fmt.Errorf("cloudtrace exporter requires a project id")
		}
		exp, err := cloudtrace.New(cloudtrace.WithProjectID(opts.Project))
		if err != nil {
			return nil, fmt.Errorf("cloudtrace exporter: %w", err)
		}
		return sdktrace.NewTracerProvider(sdktrace.WithBatcher(exp)), nil
	default:
		return nil, fmt.Errorf("unknown trace exporter %q", opts.Exporter)
	}
}

// normalizeExporter lower-cases and defaults an exporter selector. The empty
// value maps to "none".
func normalizeExporter(e TraceExporter) TraceExporter {
	if e == "" {
		return TraceExporterNone
	}
	return TraceExporter(strings.ToLower(string(e)))
}

// ValidTraceExporter reports whether e is one of the allowed exporter values
// (case-insensitive; the empty value is valid and means "none").
func ValidTraceExporter(e TraceExporter) bool {
	n := normalizeExporter(e)
	for _, a := range AllowedTraceExporters {
		if n == a {
			return true
		}
	}
	return false
}

func parseLevel(s string) slog.Level {
	switch strings.ToLower(s) {
	case "debug":
		return slog.LevelDebug
	case "warn", "warning":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}

// WithFlowID returns a context carrying the given flow id, used to correlate
// all logs and spans for a single incident's journey through the pipeline.
func WithFlowID(ctx context.Context, flowID string) context.Context {
	return context.WithValue(ctx, flowIDKey{}, flowID)
}

// FlowID extracts the flow id from ctx, or "" if none is set.
func FlowID(ctx context.Context) string {
	if v, ok := ctx.Value(flowIDKey{}).(string); ok {
		return v
	}
	return ""
}

// LoggerFrom returns a logger annotated with the context's flow id when one is
// present, so every line is correlatable without manual threading.
func LoggerFrom(ctx context.Context, base *slog.Logger) *slog.Logger {
	if base == nil {
		base = slog.Default()
	}
	if id := FlowID(ctx); id != "" {
		return base.With(flowIDLogKey, id)
	}
	return base
}
