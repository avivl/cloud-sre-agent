// Package pipeline owns the triage -> analysis -> remediation orchestration
// and the CodeValidator port that gates LLM-generated patches before delivery.
package pipeline

import "context"

// ValidationResult reports whether a generated patch is structurally sound.
// Diagnostics carries human-readable findings (compile errors, lint warnings).
type ValidationResult struct {
	OK          bool     `json:"ok"`
	Diagnostics []string `json:"diagnostics,omitempty"`
}

// CodeValidator validates an LLM-generated patch for a given language before
// it is delivered. The MVP ships a no-op local validator; later adapters can
// compile/test patches in a sandbox (behind this same port).
type CodeValidator interface {
	// Validate checks the patch for the given language (e.g. "go", "python").
	Validate(ctx context.Context, patch string, lang string) (ValidationResult, error)
}

// NoopValidator accepts every patch. It is the MVP default and a safe fallback
// when no real validation backend is configured.
type NoopValidator struct{}

// Validate always reports OK.
func (NoopValidator) Validate(_ context.Context, _ string, _ string) (ValidationResult, error) {
	return ValidationResult{OK: true}, nil
}
