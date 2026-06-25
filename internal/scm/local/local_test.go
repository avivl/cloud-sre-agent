package local

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/scm"
)

// fixedClock returns a deterministic time for reproducible metadata.
func fixedClock() time.Time {
	return time.Date(2026, 6, 25, 12, 0, 0, 0, time.UTC)
}

func TestLocalPatch_Name(t *testing.T) {
	assert.Equal(t, "local", New(t.TempDir()).Name())
}

// Compile-time assertion that LocalPatch satisfies the port.
var _ scm.PRTarget = (*LocalPatch)(nil)

func TestLocalPatch_Deliver(t *testing.T) {
	cases := []struct {
		name     string
		change   scm.Change
		wantErr  bool
		wantBase string // expected slug base (without extension)
		wantSev  string
	}{
		{
			name: "nested path is slugified",
			change: scm.Change{
				FilePath:    "src/api/handler.go",
				Patch:       "--- a\n+++ b\n@@ fix @@\n",
				Description: "fix the handler",
				Severity:    domain.SeverityError,
			},
			wantBase: "src-api-handler.go",
			wantSev:  "error",
		},
		{
			name: "simple filename",
			change: scm.Change{
				FilePath:    "main.go",
				Patch:       "patch body",
				Description: "tweak main",
				Severity:    domain.SeverityCritical,
			},
			wantBase: "main.go",
			wantSev:  "critical",
		},
		{
			name: "unknown severity defaults to label",
			change: scm.Change{
				FilePath: "x.go",
				Patch:    "p",
				Severity: domain.Severity(99),
			},
			wantBase: "x.go",
			wantSev:  "unknown",
		},
		{
			name:    "empty file path errors",
			change:  scm.Change{FilePath: "  ", Patch: "p"},
			wantErr: true,
		},
		{
			name:    "empty patch errors",
			change:  scm.Change{FilePath: "f.go", Patch: ""},
			wantErr: true,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			dir := t.TempDir()
			lp := New(dir, WithClock(fixedClock))

			ref, err := lp.Deliver(context.Background(), tc.change)
			if tc.wantErr {
				require.Error(t, err)
				assert.Equal(t, scm.Ref{}, ref)
				entries, _ := os.ReadDir(dir)
				assert.Empty(t, entries, "no files should be written on error")
				return
			}
			require.NoError(t, err)

			patchPath := filepath.Join(dir, tc.wantBase+".patch")
			metaPath := filepath.Join(dir, tc.wantBase+".meta.json")

			assert.Equal(t, patchPath, ref.ID)
			assert.Equal(t, "file://"+patchPath, ref.URL)

			gotPatch, err := os.ReadFile(patchPath)
			require.NoError(t, err)
			assert.Equal(t, tc.change.Patch, string(gotPatch))

			gotMeta, err := os.ReadFile(metaPath)
			require.NoError(t, err)

			var meta metadata
			require.NoError(t, json.Unmarshal(gotMeta, &meta))
			assert.Equal(t, tc.change.FilePath, meta.FilePath)
			assert.Equal(t, tc.change.Description, meta.Description)
			assert.Equal(t, tc.wantSev, meta.Severity)
			assert.Equal(t, tc.wantBase+".patch", meta.PatchFile)
			assert.True(t, meta.DeliveredAt.Equal(fixedClock()), "timestamp from injected clock")
		})
	}
}

func TestLocalPatch_DeliverCreatesMissingDir(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "nested", "out")
	lp := New(dir, WithClock(fixedClock))

	ref, err := lp.Deliver(context.Background(), scm.Change{
		FilePath: "a.go",
		Patch:    "p",
		Severity: domain.SeverityInfo,
	})
	require.NoError(t, err)
	assert.FileExists(t, ref.ID)
}

func TestLocalPatch_DeliverOverwrites(t *testing.T) {
	dir := t.TempDir()
	lp := New(dir, WithClock(fixedClock))
	change := scm.Change{FilePath: "a.go", Patch: "v1", Severity: domain.SeverityInfo}

	_, err := lp.Deliver(context.Background(), change)
	require.NoError(t, err)

	change.Patch = "v2"
	ref, err := lp.Deliver(context.Background(), change)
	require.NoError(t, err)

	got, err := os.ReadFile(ref.ID)
	require.NoError(t, err)
	assert.Equal(t, "v2", string(got))
}

func TestNew_DefaultClock(t *testing.T) {
	lp := New(t.TempDir())
	require.NotNil(t, lp.now)

	before := time.Now()
	ref, err := lp.Deliver(context.Background(), scm.Change{
		FilePath: "a.go",
		Patch:    "p",
		Severity: domain.SeverityInfo,
	})
	require.NoError(t, err)

	raw, err := os.ReadFile(filepath.Join(filepath.Dir(ref.ID), "a.go.meta.json"))
	require.NoError(t, err)
	var meta metadata
	require.NoError(t, json.Unmarshal(raw, &meta))
	assert.False(t, meta.DeliveredAt.Before(before), "default clock uses time.Now")
}

func TestWithClock_NilIgnored(t *testing.T) {
	lp := New(t.TempDir(), WithClock(nil))
	assert.NotNil(t, lp.now, "nil clock option must not clobber the default")
}

func TestSlugify(t *testing.T) {
	cases := map[string]string{
		"src/api/handler.go": "src-api-handler.go",
		"main.go":            "main.go",
		"a//b":               "a-b",
		"":                   "change",
		"/leading/slash":     "leading-slash",
		"weird name!.go":     "weird-name-.go",
	}
	for in, want := range cases {
		assert.Equal(t, want, slugify(in), "input %q", in)
	}
}
