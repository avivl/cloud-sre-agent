package app

import (
	"context"
	"io"
	"log/slog"
	"strings"
	"testing"

	"github.com/avivl/cloud-sre-agent/internal/config"
)

func testLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

// --- BuildProvider ---

func TestBuildProvider_Stub(t *testing.T) {
	p, err := BuildProvider(context.Background(), config.LLMConfig{Provider: config.KindStub, Model: "ignored"})
	if err != nil {
		t.Fatalf("BuildProvider stub: unexpected error: %v", err)
	}
	if p == nil {
		t.Fatal("BuildProvider stub: nil provider")
	}
	// Single provider wrapped in router: router[stub].
	if got := p.Name(); got != "router[stub]" {
		t.Fatalf("BuildProvider stub: name = %q, want router[stub]", got)
	}
}

func TestBuildProvider_RouterWithFallbacks(t *testing.T) {
	cfg := config.LLMConfig{
		Provider: config.KindStub,
		Model:    "m",
		Fallbacks: []config.ProviderConfig{
			{Kind: config.KindStub, Model: "m2"},
		},
	}
	p, err := BuildProvider(context.Background(), cfg)
	if err != nil {
		t.Fatalf("BuildProvider with fallback: unexpected error: %v", err)
	}
	if got := p.Name(); got != "router[stub->stub]" {
		t.Fatalf("BuildProvider with fallback: name = %q, want router[stub->stub]", got)
	}
}

func TestBuildProvider_OpenAIMissingKey(t *testing.T) {
	t.Setenv(openAIAPIKeyEnv, "")
	_, err := BuildProvider(context.Background(), config.LLMConfig{Provider: config.KindOpenAI, Model: "gpt-4o-mini"})
	if err == nil {
		t.Fatal("BuildProvider openai without key: expected error")
	}
	// Primary failure is wrapped; the underlying message names the env var.
	if !strings.Contains(err.Error(), "primary provider (openai)") ||
		!strings.Contains(err.Error(), "openai api key not set") ||
		!strings.Contains(err.Error(), openAIAPIKeyEnv) {
		t.Fatalf("BuildProvider openai: unexpected error: %v", err)
	}
}

func TestBuildProvider_AnthropicMissingKey(t *testing.T) {
	t.Setenv(anthropicAPIKeyEnv, "")
	_, err := BuildProvider(context.Background(), config.LLMConfig{Provider: config.KindAnthropic, Model: "claude"})
	if err == nil {
		t.Fatal("BuildProvider anthropic without key: expected error")
	}
	if !strings.Contains(err.Error(), "anthropic api key not set") ||
		!strings.Contains(err.Error(), anthropicAPIKeyEnv) {
		t.Fatalf("BuildProvider anthropic: unexpected error: %v", err)
	}
}

func TestBuildProvider_GeminiAPIMissingKey(t *testing.T) {
	const env = "TEST_GEMINI_KEY_UNSET"
	t.Setenv(env, "")
	cfg := config.LLMConfig{
		Provider:  config.KindGemini,
		Model:     "gemini-2.5-flash",
		Backend:   config.BackendGeminiAPI,
		APIKeyEnv: env,
	}
	_, err := BuildProvider(context.Background(), cfg)
	if err == nil {
		t.Fatal("BuildProvider gemini-api without key: expected error")
	}
	if !strings.Contains(err.Error(), "gemini api key not set") ||
		!strings.Contains(err.Error(), env) {
		t.Fatalf("BuildProvider gemini-api: unexpected error: %v", err)
	}
}

func TestBuildProvider_UnsupportedGeminiBackend(t *testing.T) {
	cfg := config.LLMConfig{Provider: config.KindGemini, Model: "m", Backend: "bogus"}
	_, err := BuildProvider(context.Background(), cfg)
	if err == nil {
		t.Fatal("BuildProvider gemini bogus backend: expected error")
	}
	if !strings.Contains(err.Error(), "unsupported gemini backend") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestBuildProvider_UnknownKind(t *testing.T) {
	_, err := BuildProvider(context.Background(), config.LLMConfig{Provider: "bogus", Model: "m"})
	if err == nil {
		t.Fatal("BuildProvider unknown kind: expected error")
	}
	if !strings.Contains(err.Error(), "unsupported llm provider kind") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestBuildProvider_FallbackError(t *testing.T) {
	t.Setenv(openAIAPIKeyEnv, "")
	cfg := config.LLMConfig{
		Provider: config.KindStub,
		Model:    "m",
		Fallbacks: []config.ProviderConfig{
			{Kind: config.KindOpenAI, Model: "gpt-4o-mini"},
		},
	}
	_, err := BuildProvider(context.Background(), cfg)
	if err == nil {
		t.Fatal("BuildProvider fallback missing key: expected error")
	}
	// Fallback index 0 (the first fallback) named in the wrapped error.
	if !strings.Contains(err.Error(), "fallback provider 0 (openai)") {
		t.Fatalf("unexpected error: %v", err)
	}
}

// --- BuildTarget ---

func TestBuildTarget_Local(t *testing.T) {
	cfg := config.Config{Target: config.TargetLocal, Output: config.OutputConfig{Dir: t.TempDir()}}
	tgt, err := BuildTarget(cfg, testLogger())
	if err != nil {
		t.Fatalf("BuildTarget local: %v", err)
	}
	if tgt == nil || tgt.Name() == "" {
		t.Fatal("BuildTarget local: nil/empty target")
	}
}

func TestBuildTarget_GitHubMissingToken(t *testing.T) {
	t.Setenv(config.GitHubTokenEnv, "")
	cfg := config.Config{Target: config.TargetGitHub}
	cfg.GitHub.Owner = "o"
	cfg.GitHub.Repo = "r"
	_, err := BuildTarget(cfg, testLogger())
	if err == nil {
		t.Fatal("BuildTarget github without token: expected error")
	}
	if !strings.Contains(err.Error(), config.GitHubTokenEnv) {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestBuildTarget_GitHubSelected(t *testing.T) {
	t.Setenv(config.GitHubTokenEnv, "tok")
	cfg := config.Config{Target: config.TargetGitHub}
	cfg.GitHub.Owner = "o"
	cfg.GitHub.Repo = "r"
	cfg.GitHub.BaseBranch = "main"
	tgt, err := BuildTarget(cfg, testLogger())
	if err != nil {
		t.Fatalf("BuildTarget github: %v", err)
	}
	if tgt == nil {
		t.Fatal("BuildTarget github: nil target")
	}
}

func TestBuildTarget_GitLabMissingToken(t *testing.T) {
	t.Setenv(config.GitLabTokenEnv, "")
	cfg := config.Config{Target: config.TargetGitLab}
	cfg.GitLab.Project = "g/p"
	_, err := BuildTarget(cfg, testLogger())
	if err == nil {
		t.Fatal("BuildTarget gitlab without token: expected error")
	}
	if !strings.Contains(err.Error(), config.GitLabTokenEnv) {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestBuildTarget_GitLabSelected(t *testing.T) {
	t.Setenv(config.GitLabTokenEnv, "tok")
	cfg := config.Config{Target: config.TargetGitLab}
	cfg.GitLab.Project = "g/p"
	cfg.GitLab.BaseBranch = "main"
	tgt, err := BuildTarget(cfg, testLogger())
	if err != nil {
		t.Fatalf("BuildTarget gitlab: %v", err)
	}
	if tgt == nil {
		t.Fatal("BuildTarget gitlab: nil target")
	}
}

func TestBuildTarget_Unsupported(t *testing.T) {
	_, err := BuildTarget(config.Config{Target: "bogus"}, testLogger())
	if err == nil {
		t.Fatal("BuildTarget bogus: expected error")
	}
	if !strings.Contains(err.Error(), "unsupported delivery target") {
		t.Fatalf("unexpected error: %v", err)
	}
}

// --- BuildValidator ---

func TestBuildValidator_None(t *testing.T) {
	v := BuildValidator(config.Config{Validator: config.ValidatorNone}, testLogger())
	if v == nil {
		t.Fatal("BuildValidator none: nil")
	}
	res, err := v.Validate(context.Background(), "patch", "go")
	if err != nil {
		t.Fatalf("noop validate err: %v", err)
	}
	if !res.OK {
		t.Fatal("noop validator should accept")
	}
}

func TestBuildValidator_Local(t *testing.T) {
	v := BuildValidator(config.Config{Validator: config.ValidatorLocal}, testLogger())
	if v == nil {
		t.Fatal("BuildValidator local: nil")
	}
}

func TestBuildValidator_DefaultFallsBackToNoop(t *testing.T) {
	v := BuildValidator(config.Config{Validator: "bogus"}, testLogger())
	if v == nil {
		t.Fatal("BuildValidator default: nil")
	}
	res, err := v.Validate(context.Background(), "patch", "go")
	if err != nil || !res.OK {
		t.Fatalf("default validator should behave as noop, got ok=%v err=%v", res.OK, err)
	}
}

// --- BuildSources ---

func TestBuildSources_File(t *testing.T) {
	cfg := config.Config{Sources: []config.SourceConfig{
		{Type: config.SourceTypeFile, Path: "/tmp/does-not-matter.log"},
	}}
	srcs, err := BuildSources(context.Background(), cfg, testLogger())
	if err != nil {
		t.Fatalf("BuildSources file: %v", err)
	}
	if len(srcs) != 1 {
		t.Fatalf("BuildSources file: got %d sources, want 1", len(srcs))
	}
	for _, s := range srcs {
		_ = s.Close()
	}
}

func TestBuildSources_FileMissingPath(t *testing.T) {
	cfg := config.Config{Sources: []config.SourceConfig{
		{Type: config.SourceTypeFile, Path: ""},
	}}
	_, err := BuildSources(context.Background(), cfg, testLogger())
	if err == nil {
		t.Fatal("BuildSources file empty path: expected error")
	}
	if !strings.Contains(err.Error(), "build source[0] (file)") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestBuildSources_UnsupportedType(t *testing.T) {
	cfg := config.Config{Sources: []config.SourceConfig{
		{Type: "bogus"},
	}}
	_, err := BuildSources(context.Background(), cfg, testLogger())
	if err == nil {
		t.Fatal("BuildSources bogus type: expected error")
	}
	if !strings.Contains(err.Error(), "unsupported type") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestBuildSources_PartialFailureClosesBuilt(t *testing.T) {
	// First source builds (file), second fails (unknown type). The already-built
	// file source must be closed; we assert the error references the second index.
	cfg := config.Config{Sources: []config.SourceConfig{
		{Type: config.SourceTypeFile, Path: "/tmp/x.log"},
		{Type: "bogus"},
	}}
	_, err := BuildSources(context.Background(), cfg, testLogger())
	if err == nil {
		t.Fatal("BuildSources partial failure: expected error")
	}
	if !strings.Contains(err.Error(), "build source[1]") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestBuildSources_Empty(t *testing.T) {
	srcs, err := BuildSources(context.Background(), config.Config{}, testLogger())
	if err != nil {
		t.Fatalf("BuildSources empty: %v", err)
	}
	if len(srcs) != 0 {
		t.Fatalf("BuildSources empty: got %d", len(srcs))
	}
}
