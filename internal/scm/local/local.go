// Package local implements the scm.PRTarget port by writing remediation
// patches to a local output directory instead of opening a real pull request.
// It is the MVP / offline delivery target: each Deliver call writes the patch
// body to a file derived from the change's target path and a small JSON
// metadata sidecar describing the change.
package local

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/avivl/cloud-sre-agent/internal/scm"
)

// name is the adapter identifier reported by Name and used in logs/metrics.
const name = "local"

// dirPerm and filePerm are the permissions for created directories and files.
const (
	dirPerm  os.FileMode = 0o755
	filePerm os.FileMode = 0o644
)

// metadata is the JSON sidecar written alongside each patch file. It records
// the reviewer context for the change so the patch file itself stays a clean
// diff.
type metadata struct {
	FilePath    string    `json:"file_path"`
	Description string    `json:"description"`
	Severity    string    `json:"severity"`
	DeliveredAt time.Time `json:"delivered_at"`
	PatchFile   string    `json:"patch_file"`
}

// LocalPatch writes delivered changes to a directory on the local filesystem.
// It implements scm.PRTarget. The zero value is not usable; construct with New.
//
//nolint:revive // name fixed by the local-patch delivery contract; "Patch" alone would be ambiguous in this package.
type LocalPatch struct {
	dir string
	now func() time.Time
}

// Option configures a LocalPatch.
type Option func(*LocalPatch)

// WithClock overrides the time source used for the delivery timestamp. This
// keeps Deliver deterministic in tests; production callers omit it and get
// time.Now.
func WithClock(now func() time.Time) Option {
	return func(l *LocalPatch) {
		if now != nil {
			l.now = now
		}
	}
}

// New returns a LocalPatch that writes patches under dir. The directory is
// created on first Deliver if it does not exist.
func New(dir string, opts ...Option) *LocalPatch {
	l := &LocalPatch{
		dir: dir,
		now: time.Now,
	}
	for _, opt := range opts {
		opt(l)
	}
	return l
}

// Name identifies the adapter.
func (l *LocalPatch) Name() string { return name }

// Deliver writes change.Patch to a file named from change.FilePath and a JSON
// metadata sidecar beside it, then returns a Ref whose ID and URL point at the
// patch file. An error is returned if the change is invalid or any write fails.
func (l *LocalPatch) Deliver(_ context.Context, change scm.Change) (scm.Ref, error) {
	if strings.TrimSpace(change.FilePath) == "" {
		return scm.Ref{}, fmt.Errorf("%s: change.FilePath is required", name)
	}
	if change.Patch == "" {
		return scm.Ref{}, fmt.Errorf("%s: change.Patch is empty", name)
	}

	if err := os.MkdirAll(l.dir, dirPerm); err != nil {
		return scm.Ref{}, fmt.Errorf("%s: create output dir: %w", name, err)
	}

	base := slugify(change.FilePath)
	patchPath := filepath.Join(l.dir, base+".patch")
	metaPath := filepath.Join(l.dir, base+".meta.json")

	if err := os.WriteFile(patchPath, []byte(change.Patch), filePerm); err != nil {
		return scm.Ref{}, fmt.Errorf("%s: write patch: %w", name, err)
	}

	meta := metadata{
		FilePath:    change.FilePath,
		Description: change.Description,
		Severity:    change.Severity.String(),
		DeliveredAt: l.now(),
		PatchFile:   filepath.Base(patchPath),
	}
	metaBytes, err := json.MarshalIndent(meta, "", "  ")
	if err != nil {
		return scm.Ref{}, fmt.Errorf("%s: marshal metadata: %w", name, err)
	}
	if err := os.WriteFile(metaPath, metaBytes, filePerm); err != nil {
		return scm.Ref{}, fmt.Errorf("%s: write metadata: %w", name, err)
	}

	return scm.Ref{ID: patchPath, URL: "file://" + patchPath}, nil
}

// slugSeparators matches any run of characters that are not safe in a flat
// filename; each run collapses to a single hyphen.
var slugSeparators = regexp.MustCompile(`[^a-zA-Z0-9._-]+`)

// slugify turns an arbitrary file path into a single safe filename component,
// e.g. "src/api/handler.go" -> "src-api-handler.go".
func slugify(path string) string {
	s := slugSeparators.ReplaceAllString(path, "-")
	s = strings.Trim(s, "-")
	if s == "" {
		return "change"
	}
	return s
}
