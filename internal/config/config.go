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

// LLM backend identifiers. Vertex AI is the only BAA-eligible Google backend
// and is the default; the consumer Gemini Developer API is not covered by
// Google's BAA and is gated behind an explicit opt-in.
const (
	BackendVertex    = "vertex"
	BackendGeminiAPI = "gemini-api"
)

// AllowNonBAAEnv is the env var that, when set to "1", opts in to the non-BAA
// Gemini Developer API alongside (or instead of) the config bool. Either
// suffices.
const AllowNonBAAEnv = "SRE_ALLOW_NON_BAA"

// LLMConfig selects the LLM provider, model, and Google backend.
type LLMConfig struct {
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
}

// OutputConfig controls where remediation artifacts are written.
type OutputConfig struct {
	Dir string `koanf:"dir"`
}

// Delivery target identifiers. "local" writes patches to the output directory;
// "github" opens a real pull request.
const (
	TargetLocal  = "local"
	TargetGitHub = "github"
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
	if c.LLM.Provider == "" {
		return fmt.Errorf("config: llm.provider is required")
	}
	if c.LLM.Model == "" {
		return fmt.Errorf("config: llm.model is required")
	}
	if err := c.LLM.validateBackend(); err != nil {
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
// and needs nothing; "github" requires owner and repo (the token is read from
// the environment at wire time, not validated here).
func (c Config) validateTarget() error {
	switch c.Target {
	case TargetLocal:
		return nil
	case TargetGitHub:
		if c.GitHub.Owner == "" || c.GitHub.Repo == "" {
			return fmt.Errorf("config: target %q requires github.owner and github.repo", c.Target)
		}
		return nil
	default:
		return fmt.Errorf("config: target %q must be %q or %q", c.Target, TargetLocal, TargetGitHub)
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

// validateBackend enforces the HIPAA fail-closed posture on the LLM backend:
// Vertex AI (BAA-eligible) requires project+location; the consumer Gemini
// Developer API (not BAA-covered) is refused unless explicitly opted in.
func (l LLMConfig) validateBackend() error {
	switch l.Backend {
	case BackendVertex:
		if l.Project == "" || l.Location == "" {
			return fmt.Errorf("config: llm.backend %q (Vertex AI) requires llm.project and llm.location", l.Backend)
		}
		return nil
	case BackendGeminiAPI:
		if !l.AllowsNonBAA() {
			return fmt.Errorf("config: llm.backend %q is the consumer Gemini Developer API, which is NOT covered by Google's BAA; "+
				"set llm.allow_non_baa: true or %s=1 to opt in explicitly, or use the %q backend",
				BackendGeminiAPI, AllowNonBAAEnv, BackendVertex)
		}
		return nil
	default:
		return fmt.Errorf("config: llm.backend %q must be %q or %q", l.Backend, BackendVertex, BackendGeminiAPI)
	}
}
