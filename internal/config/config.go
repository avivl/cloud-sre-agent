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
	Sources []SourceConfig `koanf:"sources"`
	LLM     LLMConfig      `koanf:"llm"`
	Output  OutputConfig   `koanf:"output"`
	Log     LogConfig      `koanf:"log"`
}

// SourceConfig describes one log source.
type SourceConfig struct {
	// Type selects the adapter (e.g. "file").
	Type string `koanf:"type"`
	// Path is the source location (file path for the filesystem source).
	Path string `koanf:"path"`
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
		Output: OutputConfig{Dir: "./out"},
		Log:    LogConfig{Level: "info", Format: "json"},
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
		"llm.provider":    d.LLM.Provider,
		"llm.model":       d.LLM.Model,
		"llm.api_key_env": d.LLM.APIKeyEnv,
		"llm.backend":     d.LLM.Backend,
		"llm.location":    d.LLM.Location,
		"output.dir":      d.Output.Dir,
		"log.level":       d.Log.Level,
		"log.format":      d.Log.Format,
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
		if s.Type == "" {
			return fmt.Errorf("config: sources[%d]: type is required", i)
		}
		if s.Type == "file" && s.Path == "" {
			return fmt.Errorf("config: sources[%d]: file source requires path", i)
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
	switch c.Log.Format {
	case "", "json", "text":
	default:
		return fmt.Errorf("config: log.format %q must be json or text", c.Log.Format)
	}
	return nil
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
