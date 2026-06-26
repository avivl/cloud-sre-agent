// Package config loads and validates the agent's typed configuration from a
// YAML file with environment-variable overrides, via koanf.
package config

import (
	"fmt"
	"os"
	"strings"

	"github.com/knadh/koanf/parsers/yaml"
	"github.com/knadh/koanf/providers/confmap"
	"github.com/knadh/koanf/providers/env"
	"github.com/knadh/koanf/providers/file"
	"github.com/knadh/koanf/v2"
)

// EnvPrefix is the prefix for environment overrides, e.g. SRE_LLM__MODEL.
// A double underscore maps to a config-key dot (SRE_LLM__MODEL -> llm.model).
const EnvPrefix = "SRE_"

// Config is the full, typed agent configuration.
type Config struct {
	Sources   []SourceConfig `koanf:"sources"`
	LLM       LLMConfig      `koanf:"llm"`
	Output    OutputConfig   `koanf:"output"`
	Target    string         `koanf:"target"`
	Validator string         `koanf:"validator"`
	GitHub    GitHubConfig   `koanf:"github"`
	GitLab    GitLabConfig   `koanf:"gitlab"`
	Log       LogConfig      `koanf:"log"`
	Tracing   TracingConfig  `koanf:"tracing"`
}

// Source type identifiers.
const (
	SourceTypeFile   = "file"
	SourceTypePubSub = "pubsub"
)

// SourceConfig describes one log source.
type SourceConfig struct {
	// Type selects the adapter ("file" or "pubsub").
	Type string `koanf:"type"`
	// Path is the source location (file path/glob for the filesystem source).
	Path string `koanf:"path"`
	// ProjectID is the GCP project (required for the pubsub source).
	ProjectID string `koanf:"project_id"`
	// SubscriptionID is the Pub/Sub pull subscription (required for pubsub).
	SubscriptionID string `koanf:"subscription_id"`
}

// Trace exporter identifiers.
const (
	TracingExporterNone       = "none"
	TracingExporterStdout     = "stdout"
	TracingExporterCloudTrace = "cloudtrace"
)

// TracingConfig selects the OTel span exporter.
type TracingConfig struct {
	// Exporter is one of "none" (default), "stdout", or "cloudtrace".
	Exporter string `koanf:"exporter"`
	// Project is the GCP project ID, required by the cloudtrace exporter.
	Project string `koanf:"project"`
}

// LLM provider kinds. "gemini" is Google's Gemini (via Vertex AI or the
// Developer API); "openai" and "anthropic" are external third-party services;
// "ollama" is a local/self-hosted model server (no external disclosure).
const (
	KindGemini    = "gemini"
	KindOpenAI    = "openai"
	KindAnthropic = "anthropic"
	KindOllama    = "ollama"
)

// DefaultOllamaHost is the Ollama daemon address used when an ollama provider's
// host is left empty.
const DefaultOllamaHost = "http://localhost:11434"

// LLM backend identifiers (gemini kind only). Vertex AI is the only BAA-eligible
// Google backend and is the default; the consumer Gemini Developer API is not
// covered by Google's BAA and is gated behind an explicit opt-in.
const (
	BackendVertex    = "vertex"
	BackendGeminiAPI = "gemini-api"
)

// AllowNonBAAEnv is the env var that, when set to "1", opts in to the non-BAA
// Gemini Developer API alongside (or instead of) the config bool. Either
// suffices.
const AllowNonBAAEnv = "SRE_ALLOW_NON_BAA"

// AllowExternalLLMEnv is the env var that, when set to "1", opts in to the
// external third-party LLM providers (OpenAI, Anthropic) alongside (or instead
// of) the llm.allow_external config bool. Either suffices.
const AllowExternalLLMEnv = "SRE_ALLOW_EXTERNAL_LLM"

// ProviderConfig describes one LLM provider in the chain (primary or a
// fallback). Kind selects the adapter; Model is required. The remaining fields
// are provider-specific: Backend/Project/Location/APIKeyEnv/AllowNonBAA apply to
// the gemini kind, BaseURL applies to openai/anthropic. API keys are never
// stored here — they are read from the environment at wire time.
type ProviderConfig struct {
	// Kind selects the adapter: "gemini", "openai", "anthropic", or "ollama".
	Kind string `koanf:"kind"`
	// Model is the model name (e.g. "gemini-2.5-flash", "gpt-4o-mini",
	// "claude-opus-4-8"). Required.
	Model string `koanf:"model"`

	// --- gemini-kind fields ---

	// Backend selects the Google backend: "vertex" (default, BAA-eligible) or
	// "gemini-api" (consumer Developer API, NOT covered by Google's BAA).
	Backend string `koanf:"backend"`
	// Project is the GCP project ID (required for the vertex backend).
	Project string `koanf:"project"`
	// Location is the GCP region, e.g. "us-central1" (required for vertex).
	Location string `koanf:"location"`
	// APIKeyEnv names the environment variable holding the API key, so the key
	// itself is never written to the config file. Used by the gemini-api backend.
	APIKeyEnv string `koanf:"api_key_env"`
	// AllowNonBAA must be true (or the SRE_ALLOW_NON_BAA=1 env var set) to permit
	// the non-BAA gemini-api backend. It is an explicit, auditable acknowledgement
	// that the consumer API is not HIPAA-covered.
	AllowNonBAA bool `koanf:"allow_non_baa"`

	// --- openai / anthropic fields ---

	// BaseURL optionally overrides the provider API host (e.g. a compatible
	// gateway). Empty uses the SDK default. Applies to openai/anthropic.
	BaseURL string `koanf:"base_url"`

	// --- ollama fields ---

	// Host is the Ollama daemon base URL (e.g. "http://localhost:11434"). Empty
	// defaults to DefaultOllamaHost. Applies to the ollama kind only; Ollama is
	// local/self-hosted and uses no API key.
	Host string `koanf:"host"`
}

// LLMConfig selects the primary LLM provider plus an ordered list of fallbacks.
//
// For backward compatibility the primary provider is expressed through the
// top-level fields (Provider/Model/Backend/Project/Location/APIKeyEnv/
// AllowNonBAA): the primary's "kind" is Provider. Fallbacks are full
// ProviderConfig entries tried in order when the primary fails.
type LLMConfig struct {
	// Provider is the primary provider kind: "gemini" (default), "openai", or
	// "anthropic".
	Provider string `koanf:"provider"`
	Model    string `koanf:"model"`
	// APIKeyEnv names the environment variable holding the API key, so the key
	// itself is never written to the config file. Used by the gemini-api backend.
	APIKeyEnv string `koanf:"api_key_env"`
	// Backend selects the Google backend: "vertex" (default, BAA-eligible) or
	// "gemini-api" (consumer Developer API, NOT covered by Google's BAA).
	Backend string `koanf:"backend"`
	// Project is the GCP project ID (required for the vertex backend).
	Project string `koanf:"project"`
	// Location is the GCP region, e.g. "us-central1" (required for vertex).
	Location string `koanf:"location"`
	// AllowNonBAA must be true (or the SRE_ALLOW_NON_BAA=1 env var set) to permit
	// the non-BAA gemini-api backend. It exists purely as an explicit, auditable
	// acknowledgement that the consumer API is not HIPAA-covered.
	AllowNonBAA bool `koanf:"allow_non_baa"`
	// BaseURL optionally overrides the primary provider API host when Provider is
	// openai/anthropic. Ignored for gemini.
	BaseURL string `koanf:"base_url"`
	// Host is the Ollama daemon base URL when Provider is ollama. Empty defaults
	// to DefaultOllamaHost. Ignored for other kinds.
	Host string `koanf:"host"`

	// Fallbacks is the ordered list of fallback providers, tried in turn when the
	// primary (and preceding fallbacks) fail.
	Fallbacks []ProviderConfig `koanf:"fallbacks"`

	// AllowExternal must be true (or SRE_ALLOW_EXTERNAL_LLM=1) to permit selecting
	// an external third-party provider (openai/anthropic) as primary or fallback.
	// It is an explicit, auditable acknowledgement that prompt content is
	// disclosed to a third party not covered by a Google BAA.
	AllowExternal bool `koanf:"allow_external"`
}

// Primary returns the primary provider as a ProviderConfig, projecting the
// top-level LLMConfig fields onto it.
func (l LLMConfig) Primary() ProviderConfig {
	return ProviderConfig{
		Kind:        l.Provider,
		Model:       l.Model,
		Backend:     l.Backend,
		Project:     l.Project,
		Location:    l.Location,
		APIKeyEnv:   l.APIKeyEnv,
		AllowNonBAA: l.AllowNonBAA,
		BaseURL:     l.BaseURL,
		Host:        l.Host,
	}
}

// Providers returns the ordered provider chain: the primary first, then each
// configured fallback.
func (l LLMConfig) Providers() []ProviderConfig {
	out := make([]ProviderConfig, 0, 1+len(l.Fallbacks))
	out = append(out, l.Primary())
	out = append(out, l.Fallbacks...)
	return out
}

// OutputConfig controls where remediation artifacts are written.
type OutputConfig struct {
	Dir string `koanf:"dir"`
}

// Delivery target identifiers. "local" writes patches to the output directory;
// "github" opens a real pull request; "gitlab" opens a real merge request.
const (
	TargetLocal  = "local"
	TargetGitHub = "github"
	TargetGitLab = "gitlab"
)

// Code validator identifiers. "none" accepts every patch (NoopValidator);
// "local" gates patches with the local Go toolchain.
const (
	ValidatorNone  = "none"
	ValidatorLocal = "local"
)

// GitHubTokenEnv is the environment variable the GitHub target reads its access
// token from at wire time. The token is NEVER stored in config and never logged.
const GitHubTokenEnv = "GITHUB_TOKEN"

// GitHubConfig configures the GitHub delivery target. The access token is not
// stored here — it is read from the GitHubTokenEnv environment variable when the
// target is constructed.
type GitHubConfig struct {
	// Owner is the repository owner (user or org). Required for the github target.
	Owner string `koanf:"owner"`
	// Repo is the repository name. Required for the github target.
	Repo string `koanf:"repo"`
	// BaseBranch is the branch PRs target and branch from; defaults to "main".
	BaseBranch string `koanf:"base_branch"`
}

// GitLabTokenEnv is the environment variable the GitLab target reads its access
// token from at wire time. The token is NEVER stored in config and never logged.
const GitLabTokenEnv = "GITLAB_TOKEN"

// GitLabConfig configures the GitLab delivery target. The access token is not
// stored here — it is read from the GitLabTokenEnv environment variable when the
// target is constructed.
type GitLabConfig struct {
	// Project is the project path ("group/repo") or numeric project ID. Required
	// for the gitlab target.
	Project string `koanf:"project"`
	// BaseBranch is the branch MRs target and branch from; defaults to "main".
	BaseBranch string `koanf:"base_branch"`
	// BaseURL overrides the GitLab API base URL for self-managed instances.
	// Empty means public gitlab.com.
	BaseURL string `koanf:"base_url"`
}

// LogConfig controls observability output.
type LogConfig struct {
	// Level is one of debug, info, warn, error.
	Level string `koanf:"level"`
	// Format is "json" or "text".
	Format string `koanf:"format"`
}

// Default returns a Config populated with sensible defaults.
func Default() Config {
	return Config{
		LLM: LLMConfig{
			Provider:  "gemini",
			Model:     "gemini-2.5-flash",
			APIKeyEnv: "GEMINI_API_KEY",
			// Vertex AI is the BAA-eligible default. project/location must be set
			// in config for it to start.
			Backend:  BackendVertex,
			Location: "us-central1",
		},
		Output:    OutputConfig{Dir: "./out"},
		Target:    TargetLocal,
		Validator: ValidatorNone,
		GitHub:    GitHubConfig{BaseBranch: "main"},
		GitLab:    GitLabConfig{BaseBranch: "main"},
		Log:       LogConfig{Level: "info", Format: "json"},
		Tracing:   TracingConfig{Exporter: TracingExporterNone},
	}
}

// Load reads configuration from the given YAML file (if path is non-empty),
// then applies SRE_-prefixed environment overrides, and validates the result.
func Load(path string) (Config, error) {
	k := koanf.New(".")

	// Seed scalar defaults so unspecified fields keep them. Sources have no
	// default (at least one must be configured).
	d := Default()
	if err := k.Load(confmap.Provider(map[string]any{
		"llm.provider":       d.LLM.Provider,
		"llm.model":          d.LLM.Model,
		"llm.api_key_env":    d.LLM.APIKeyEnv,
		"llm.backend":        d.LLM.Backend,
		"llm.location":       d.LLM.Location,
		"output.dir":         d.Output.Dir,
		"target":             d.Target,
		"validator":          d.Validator,
		"github.base_branch": d.GitHub.BaseBranch,
		"gitlab.base_branch": d.GitLab.BaseBranch,
		"log.level":          d.Log.Level,
		"log.format":         d.Log.Format,
		"tracing.exporter":   d.Tracing.Exporter,
	}, "."), nil); err != nil {
		return Config{}, fmt.Errorf("config: seed defaults: %w", err)
	}

	if path != "" {
		if err := k.Load(file.Provider(path), yaml.Parser()); err != nil {
			return Config{}, fmt.Errorf("config: load file %q: %w", path, err)
		}
	}

	// SRE_LLM__MODEL -> llm.model
	if err := k.Load(env.Provider(EnvPrefix, ".", func(s string) string {
		s = strings.TrimPrefix(s, EnvPrefix)
		s = strings.ReplaceAll(s, "__", ".")
		return strings.ToLower(s)
	}), nil); err != nil {
		return Config{}, fmt.Errorf("config: load env: %w", err)
	}

	var out Config
	if err := k.Unmarshal("", &out); err != nil {
		return Config{}, fmt.Errorf("config: unmarshal: %w", err)
	}
	if err := out.Validate(); err != nil {
		return Config{}, err
	}
	return out, nil
}

// Validate checks the configuration for internal consistency.
func (c Config) Validate() error {
	if len(c.Sources) == 0 {
		return fmt.Errorf("config: at least one source is required")
	}
	for i, s := range c.Sources {
		if err := s.validate(i); err != nil {
			return err
		}
	}
	if err := c.LLM.validate(); err != nil {
		return err
	}
	if c.Output.Dir == "" {
		return fmt.Errorf("config: output.dir is required")
	}
	if err := c.validateTarget(); err != nil {
		return err
	}
	if err := c.validateValidator(); err != nil {
		return err
	}
	switch c.Log.Format {
	case "", "json", "text":
	default:
		return fmt.Errorf("config: log.format %q must be json or text", c.Log.Format)
	}
	if err := c.Tracing.validate(); err != nil {
		return err
	}
	return nil
}

// validateTarget enforces the delivery target selector. "local" is the default
// and needs nothing; "github" requires owner and repo; "gitlab" requires
// project (tokens are read from the environment at wire time, not validated
// here).
func (c Config) validateTarget() error {
	switch c.Target {
	case TargetLocal:
		return nil
	case TargetGitHub:
		if c.GitHub.Owner == "" || c.GitHub.Repo == "" {
			return fmt.Errorf("config: target %q requires github.owner and github.repo", c.Target)
		}
		return nil
	case TargetGitLab:
		if c.GitLab.Project == "" {
			return fmt.Errorf("config: target %q requires gitlab.project", c.Target)
		}
		return nil
	default:
		return fmt.Errorf("config: target %q must be %q, %q, or %q", c.Target, TargetLocal, TargetGitHub, TargetGitLab)
	}
}

// validateValidator enforces the code-validator selector: "none" (default) or
// "local".
func (c Config) validateValidator() error {
	switch c.Validator {
	case ValidatorNone, ValidatorLocal:
		return nil
	default:
		return fmt.Errorf("config: validator %q must be %q or %q", c.Validator, ValidatorNone, ValidatorLocal)
	}
}

// validate checks one source's required fields by type.
func (s SourceConfig) validate(i int) error {
	switch s.Type {
	case "":
		return fmt.Errorf("config: sources[%d]: type is required", i)
	case SourceTypeFile:
		if s.Path == "" {
			return fmt.Errorf("config: sources[%d]: file source requires path", i)
		}
	case SourceTypePubSub:
		if s.ProjectID == "" || s.SubscriptionID == "" {
			return fmt.Errorf("config: sources[%d]: pubsub source requires project_id and subscription_id", i)
		}
	default:
		return fmt.Errorf("config: sources[%d]: unknown type %q", i, s.Type)
	}
	return nil
}

// validate checks the tracing block: the exporter must be one of the allowed
// values, and the empty value is treated as "none".
func (t TracingConfig) validate() error {
	switch t.Exporter {
	case "", TracingExporterNone, TracingExporterStdout, TracingExporterCloudTrace:
		return nil
	default:
		return fmt.Errorf("config: tracing.exporter %q must be one of %q, %q, or %q",
			t.Exporter, TracingExporterNone, TracingExporterStdout, TracingExporterCloudTrace)
	}
}

// AllowsNonBAA reports whether the non-BAA Gemini Developer API is explicitly
// opted in, either via the config bool or the SRE_ALLOW_NON_BAA=1 env var.
// Either is sufficient.
func (l LLMConfig) AllowsNonBAA() bool {
	return l.AllowNonBAA || os.Getenv(AllowNonBAAEnv) == "1"
}

// AllowsExternal reports whether external third-party LLM providers (OpenAI,
// Anthropic) are explicitly opted in, either via the llm.allow_external config
// bool or the SRE_ALLOW_EXTERNAL_LLM=1 env var. Either is sufficient.
func (l LLMConfig) AllowsExternal() bool {
	return l.AllowExternal || os.Getenv(AllowExternalLLMEnv) == "1"
}

// validate enforces the LLM configuration: the primary and every fallback must
// name a known kind, carry a model, satisfy their kind-specific requirements,
// and clear the relevant gates (BAA for the gemini-api backend; the external
// opt-in for openai/anthropic).
func (l LLMConfig) validate() error {
	if l.Provider == "" {
		return fmt.Errorf("config: llm.provider is required")
	}
	if l.Model == "" {
		return fmt.Errorf("config: llm.model is required")
	}
	for i, p := range l.Providers() {
		where := "llm (primary)"
		if i > 0 {
			where = fmt.Sprintf("llm.fallbacks[%d]", i-1)
		}
		if err := l.validateProvider(where, p); err != nil {
			return err
		}
	}
	return nil
}

// validateProvider validates a single provider entry by kind, enforcing the
// HIPAA fail-closed posture: external third parties (openai/anthropic) are
// refused unless the external opt-in is set, and the gemini-api backend is
// refused unless the non-BAA opt-in is set.
func (l LLMConfig) validateProvider(where string, p ProviderConfig) error {
	if p.Model == "" {
		return fmt.Errorf("config: %s: model is required", where)
	}
	switch p.Kind {
	case KindGemini:
		return l.validateGeminiBackend(where, p)
	case KindOllama:
		// Ollama is local/self-hosted: prompt content stays on infrastructure
		// the operator controls, so it is EXEMPT from the external-disclosure
		// (BAA) gate. The model is already validated above; host defaults to
		// DefaultOllamaHost when empty, so there is nothing further to check.
		return nil
	case KindOpenAI, KindAnthropic:
		if !l.AllowsExternal() {
			return fmt.Errorf("config: %s: provider %q is an external third-party service; prompt content "+
				"(which may include log data) is disclosed to a provider NOT covered by Google's BAA. "+
				"Opting in PRESUMES you have a signed BAA with the vendor AND zero-data-retention enabled "+
				"on the account (the code cannot verify ZDR). "+
				"Set llm.allow_external: true or %s=1 to opt in explicitly, or use the %q provider via Vertex AI",
				where, p.Kind, AllowExternalLLMEnv, KindGemini)
		}
		return nil
	default:
		return fmt.Errorf("config: %s: provider kind %q must be %q, %q, %q, or %q", where, p.Kind, KindGemini, KindOpenAI, KindAnthropic, KindOllama)
	}
}

// validateGeminiBackend enforces the HIPAA fail-closed posture on a gemini-kind
// provider's backend: Vertex AI (BAA-eligible) requires project+location; the
// consumer Gemini Developer API (not BAA-covered) is refused unless explicitly
// opted in.
func (l LLMConfig) validateGeminiBackend(where string, p ProviderConfig) error {
	switch p.Backend {
	case BackendVertex:
		if p.Project == "" || p.Location == "" {
			return fmt.Errorf("config: %s: backend %q (Vertex AI) requires project and location", where, p.Backend)
		}
		return nil
	case BackendGeminiAPI:
		if !l.AllowsNonBAA() {
			return fmt.Errorf("config: %s: backend %q is the consumer Gemini Developer API, which is NOT covered by Google's BAA; "+
				"set llm.allow_non_baa: true or %s=1 to opt in explicitly, or use the %q backend",
				where, BackendGeminiAPI, AllowNonBAAEnv, BackendVertex)
		}
		return nil
	default:
		return fmt.Errorf("config: %s: backend %q must be %q or %q", where, p.Backend, BackendVertex, BackendGeminiAPI)
	}
}
