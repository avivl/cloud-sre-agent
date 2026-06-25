// Package obs wires the agent's observability: a structured slog logger, OTel
// tracer/meter providers (no-op/stdout for the MVP), flow-id propagation
// through context and logs, and a redaction helper so raw log payloads never
// leak into traces or logs.
package obs

import (
	"context"
	"io"
	"log/slog"
	"strings"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/metric"
	metricnoop "go.opentelemetry.io/otel/metric/noop"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
)

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

// Setup builds a slog logger plus OTel tracer/meter providers. For the MVP the
// tracer uses the SDK with no exporter (spans are recorded but not exported)
// and the meter is a no-op; later phases attach Cloud Trace/OTLP exporters.
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

	tp := sdktrace.NewTracerProvider()
	otel.SetTracerProvider(tp)
	// HIPAA: future span attributes must be sanitized before being recorded —
	// raw log content, prompts, and error strings can carry PHI. The slog handler
	// above redacts sensitive keys, but spans bypass it, so any attribute added
	// here (or in pipeline stages) must run through security.Sanitizer first.
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
