// Package ingest defines the LogSource port: the seam through which log
// events enter the agent. Adapters (filesystem, Pub/Sub, Cloud Logging, ...)
// implement this interface; the core never imports a concrete source.
package ingest

import (
	"context"

	"github.com/avivl/cloud-sre-agent/internal/domain"
)

// LogSource is a producer of normalized log events. Implementations stream
// events on a channel until the context is cancelled or the source is closed.
type LogSource interface {
	// Name identifies the adapter (e.g. "file", "pubsub") for logs and metrics.
	Name() string

	// Stream begins delivering events on the returned channel. The channel is
	// closed by the implementation when the source is exhausted, the context
	// is cancelled, or Close is called. An error is returned only if the
	// stream cannot be started.
	//
	// Stream is single-use: it must be called at most once per source.
	// Implementations must reject a second call with an error rather than
	// starting a second, racing reader.
	Stream(ctx context.Context) (<-chan domain.LogEvent, error)

	// Close releases any resources held by the source and stops streaming.
	Close() error
}
