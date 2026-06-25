// Package validate implements the pipeline.CodeValidator port with a local,
// toolchain-backed validator. It gates LLM-generated patches before delivery:
// for Go it parses the patch for syntax, checks gofmt formatting, and runs a
// best-effort `go vet` inside a throwaway temp module. Unsupported languages
// are skipped (never an error). Patch contents are treated as potentially
// sensitive and are never logged.
package validate

import (
	"context"
	"fmt"
	"go/parser"
	"go/token"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/avivl/cloud-sre-agent/internal/pipeline"
)

// langGo is the language identifier this validator validates (case-insensitive).
const langGo = "go"

// patchFileName is the name the patch is written under inside the temp module.
// It is fixed (not derived from the patch) so nothing patch-controlled reaches
// the filesystem path.
const patchFileName = "patch.go"

// dirPerm and filePerm are the permissions for the temp module and patch file.
const (
	dirPerm  os.FileMode = 0o700
	filePerm os.FileMode = 0o600
)

// LocalValidator validates patches with the local Go toolchain. The zero value
// is usable (it logs to slog.Default); prefer constructing with New.
type LocalValidator struct {
	logger *slog.Logger
}

// Option configures a LocalValidator.
type Option func(*LocalValidator)

// WithLogger sets the structured logger. A nil logger is ignored. The logger
// is used only for non-sensitive diagnostics; patch contents are never logged.
func WithLogger(l *slog.Logger) Option {
	return func(v *LocalValidator) {
		if l != nil {
			v.logger = l
		}
	}
}

// New returns a LocalValidator. Without WithLogger it logs to slog.Default.
func New(opts ...Option) *LocalValidator {
	v := &LocalValidator{logger: slog.Default()}
	for _, opt := range opts {
		opt(v)
	}
	return v
}

// Compile-time assertion that LocalValidator satisfies the port.
var _ pipeline.CodeValidator = (*LocalValidator)(nil)

// Validate checks patch for the given lang. For "go" (case-insensitive) it runs
// a syntax gate, a gofmt formatting gate, and a best-effort go vet, collecting
// human-readable diagnostics. OK is true only if every gate passes. Other
// languages are skipped with OK=true and an informational diagnostic; an
// unsupported language is never an error. Validate never returns the patch body
// in its error or diagnostics beyond the toolchain's own messages.
func (v *LocalValidator) Validate(ctx context.Context, patch string, lang string) (pipeline.ValidationResult, error) {
	if !strings.EqualFold(strings.TrimSpace(lang), langGo) {
		return pipeline.ValidationResult{
			OK:          true,
			Diagnostics: []string{fmt.Sprintf("validation skipped: unsupported language %q", lang)},
		}, nil
	}
	return v.validateGo(ctx, patch)
}

// validateGo runs the Go gates. It returns an error only for environment
// failures (cannot create temp dir / write file); gate failures are reported
// as diagnostics with OK=false.
func (v *LocalValidator) validateGo(ctx context.Context, patch string) (pipeline.ValidationResult, error) {
	var diags []string

	// Syntax gate: parse with go/parser. This is fast, deterministic, and free
	// of any toolchain/network race. A parse error is the primary signal that a
	// patch is broken (e.g. a missing brace).
	fset := token.NewFileSet()
	if _, err := parser.ParseFile(fset, patchFileName, patch, parser.AllErrors); err != nil {
		// err already carries position-prefixed messages; it does not echo the
		// full patch body.
		diags = append(diags, "syntax: "+err.Error())
		// Syntax errors make gofmt/vet output redundant and noisy; stop here.
		v.logger.DebugContext(ctx, "go patch failed syntax gate", "gate", "syntax")
		return pipeline.ValidationResult{OK: false, Diagnostics: diags}, nil
	}

	// Set up a minimal temp module so gofmt and go vet have a real file/package.
	dir, err := os.MkdirTemp("", "sre-validate-*")
	if err != nil {
		return pipeline.ValidationResult{}, fmt.Errorf("validate: create temp dir: %w", err)
	}
	defer func() {
		if rmErr := os.RemoveAll(dir); rmErr != nil {
			v.logger.WarnContext(ctx, "failed to clean up validation temp dir", "dir", dir)
		}
	}()

	patchPath := filepath.Join(dir, patchFileName)
	if err := os.WriteFile(patchPath, []byte(patch), filePerm); err != nil {
		return pipeline.ValidationResult{}, fmt.Errorf("validate: write patch file: %w", err)
	}

	// constrainedEnv sandboxes every go subcommand below; see sandboxEnv.
	env := sandboxEnv(dir)

	// Formatting gate: gofmt -l prints the file name if it is NOT gofmt-formatted.
	// This is a pre-delivery gate: if the gate cannot be INVOKED (PATH/env
	// problem) we fail closed (OK=false), distinguishing it from a clean run.
	if out, gErr := runGofmt(ctx, env, patchPath); gErr != nil {
		diags = append(diags, "gofmt: gate could not run ("+gErr.Error()+")")
		v.logger.WarnContext(ctx, "gofmt invocation failed", "gate", "gofmt")
	} else if strings.TrimSpace(out) != "" {
		diags = append(diags, "format: file is not gofmt-formatted")
	}

	// Build/vet gate: a minimal module lets `go vet` type-check and report
	// suspicious constructs. go vet implies a build, so it doubles as the build
	// gate for a single-file package. Inability to run the gate (e.g. `go mod
	// init` cannot be invoked) fails closed rather than open.
	if vetDiags, vErr := v.runVet(ctx, env, dir); vErr != nil {
		diags = append(diags, "vet: gate could not run ("+vErr.Error()+")")
		v.logger.WarnContext(ctx, "go vet invocation failed", "gate", "vet")
	} else {
		diags = append(diags, vetDiags...)
	}

	ok := len(diags) == 0
	if !ok {
		v.logger.DebugContext(ctx, "go patch failed validation", "diagnostic_count", len(diags))
	}
	return pipeline.ValidationResult{OK: ok, Diagnostics: diags}, nil
}

// sandboxEnv builds the MINIMAL environment for go subcommands run over
// untrusted, LLM-generated code. Compiling such code is an arbitrary-code-
// execution surface (cgo, module fetches, toolchain auto-download), so this is
// the ACE-hardening boundary: the subprocess gets only what the toolchain needs
// and never inherits the parent environment (notably no GITHUB_TOKEN or other
// secrets). dir doubles as a throwaway HOME/GOPATH/GOCACHE so nothing touches
// the real user environment.
//
// The flags pin the toolchain shut: GOPROXY=off (no network module fetches),
// GOTOOLCHAIN=local (no toolchain auto-download), CGO_ENABLED=0 (no C compiler,
// so an `import "C"` patch fails closed instead of invoking cgo), and checksum
// DB lookups disabled.
func sandboxEnv(dir string) []string {
	path := os.Getenv("PATH") // needed to locate the go/gofmt binaries
	return []string{
		"PATH=" + path,
		"HOME=" + dir,
		"GOPATH=" + filepath.Join(dir, "gopath"),
		"GOCACHE=" + filepath.Join(dir, "gocache"),
		"GOFLAGS=-mod=mod",
		"GOPROXY=off",
		"GOTOOLCHAIN=local",
		"CGO_ENABLED=0",
		"GONOSUMCHECK=1",
		"GOSUMDB=off",
	}
}

// runGofmt runs `gofmt -l <file>` under the constrained sandbox env and returns
// its stdout. A non-empty stdout means the file is not gofmt-formatted.
func runGofmt(ctx context.Context, env []string, file string) (string, error) {
	cmd := exec.CommandContext(ctx, "gofmt", "-l", file)
	cmd.Env = env
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return string(out), nil
}

// runVet initializes a throwaway module in dir and runs `go vet` over it, both
// under the constrained sandbox env (the ACE-hardening boundary for untrusted
// LLM-generated code). It returns one diagnostic per problem reported by the
// toolchain. An error is returned only if `go mod init` itself cannot run
// (environmental); vet findings are returned as diagnostics, not errors.
func (v *LocalValidator) runVet(ctx context.Context, env []string, dir string) ([]string, error) {
	initCmd := exec.CommandContext(ctx, "go", "mod", "init", "srevalidate")
	initCmd.Dir = dir
	initCmd.Env = env
	if out, err := initCmd.CombinedOutput(); err != nil {
		return nil, fmt.Errorf("go mod init: %w: %s", err, strings.TrimSpace(string(out)))
	}

	vetCmd := exec.CommandContext(ctx, "go", "vet", "./...")
	vetCmd.Dir = dir
	vetCmd.Env = env
	out, err := vetCmd.CombinedOutput()
	if err == nil {
		return nil, nil
	}
	// go vet writes findings (and build errors) to stderr; CombinedOutput
	// captures them. Each non-empty line is a diagnostic. The output references
	// the fixed patch.go path, not the patch body.
	var diags []string
	for _, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		diags = append(diags, "vet: "+line)
	}
	if len(diags) == 0 {
		// Non-zero exit with no parseable output: report the raw failure.
		diags = append(diags, "vet: failed ("+err.Error()+")")
	}
	return diags, nil
}
