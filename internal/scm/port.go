// Package scm defines the PRTarget port: the seam through which a remediation
// is delivered to a source-control destination. Adapters (local patch file,
// GitHub, GitLab, ...) implement PRTarget; the core depends only on this
// interface and the Change/Ref value types.
package scm

import (
	"context"

	"github.com/avivl/cloud-sre-agent/internal/domain"
)

// Change is a single deliverable code change: a patch against one file plus
// the human-readable context that justifies it.
type Change struct {
	// FilePath is the target file the patch applies to.
	FilePath string `json:"file_path"`
	// Patch is the patch content (e.g. unified diff or full file body,
	// per the adapter's contract).
	Patch string `json:"patch"`
	// Description explains the change for a reviewer (PR body / commit message).
	Description string `json:"description"`
	// Severity is the urgency of the originating incident.
	Severity domain.Severity `json:"severity"`
}

// Ref identifies a delivered change: a local path, a PR URL, a commit SHA, etc.
type Ref struct {
	// ID is a stable identifier for the delivery (PR number, file path, ...).
	ID string `json:"id"`
	// URL locates the delivery when one exists (PR/commit URL); may be empty
	// for local targets.
	URL string `json:"url,omitempty"`
}

// PRTarget delivers a Change to a source-control destination.
type PRTarget interface {
	// Name identifies the adapter (e.g. "local", "github") for logs/metrics.
	Name() string

	// Deliver applies the change to the target and returns a reference to it.
	Deliver(ctx context.Context, change Change) (Ref, error)
}
