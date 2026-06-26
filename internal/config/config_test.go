package config

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func writeConfig(t *testing.T, body string) string {
	t.Helper()
	dir := t.TempDir()
	p := filepath.Join(dir, "config.yaml")
	require.NoError(t, os.WriteFile(p, []byte(body), 0o600))
	return p
}

func TestLoad_FileWithDefaults(t *testing.T) {
	p := writeConfig(t, `
sources:
  - type: file
    path: ./testdata/sample.log
llm:
  provider: gemini
  model: gemini-2.5-flash
  project: my-gcp-project
output:
  dir: ./out
`)
	cfg, err := Load(p)
	require.NoError(t, err)
	require.Len(t, cfg.Sources, 1)
	assert.Equal(t, "file", cfg.Sources[0].Type)
	assert.Equal(t, "gemini", cfg.LLM.Provider)
	// Defaults applied for unspecified scalars.
	assert.Equal(t, "info", cfg.Log.Level)
	assert.Equal(t, "json", cfg.Log.Format)
	assert.Equal(t, "GEMINI_API_KEY", cfg.LLM.APIKeyEnv)
	// Vertex AI is the BAA-eligible default backend; location defaults too.
	assert.Equal(t, BackendVertex, cfg.LLM.Backend)
	assert.Equal(t, "us-central1", cfg.LLM.Location)
}

func TestLoad_EnvOverride(t *testing.T) {
	p := writeConfig(t, `
sources:
  - type: file
    path: ./x.log
llm:
  project: my-gcp-project
`)
	t.Setenv("SRE_LLM__MODEL", "gemini-2.5-pro")
	t.Setenv("SRE_OUTPUT__DIR", "/tmp/patches")
	cfg, err := Load(p)
	require.NoError(t, err)
	assert.Equal(t, "gemini-2.5-pro", cfg.LLM.Model)
	assert.Equal(t, "/tmp/patches", cfg.Output.Dir)
}

func TestValidate_Backend(t *testing.T) {
	base := func() Config {
		return Config{
			Sources: []SourceConfig{{Type: "file", Path: "x.log"}},
			LLM: LLMConfig{
				Provider: "gemini", Model: "m",
				Backend: BackendVertex, Project: "p", Location: "us-central1",
			},
			Output:    OutputConfig{Dir: "./out"},
			Target:    TargetLocal,
			Validator: ValidatorNone,
			Log:       LogConfig{Format: "json"},
		}
	}

	t.Run("vertex with project+location is valid", func(t *testing.T) {
		require.NoError(t, base().Validate())
	})

	t.Run("vertex missing project fails", func(t *testing.T) {
		c := base()
		c.LLM.Project = ""
		require.Error(t, c.Validate())
	})

	t.Run("vertex missing location fails", func(t *testing.T) {
		c := base()
		c.LLM.Location = ""
		require.Error(t, c.Validate())
	})

	t.Run("gemini-api without opt-in fails closed", func(t *testing.T) {
		c := base()
		c.LLM.Backend = BackendGeminiAPI
		c.LLM.Project, c.LLM.Location = "", ""
		err := c.Validate()
		require.Error(t, err)
		require.Contains(t, err.Error(), "BAA")
	})

	t.Run("gemini-api with config opt-in is allowed", func(t *testing.T) {
		c := base()
		c.LLM.Backend = BackendGeminiAPI
		c.LLM.Project, c.LLM.Location = "", ""
		c.LLM.AllowNonBAA = true
		require.NoError(t, c.Validate())
	})

	t.Run("gemini-api with env opt-in is allowed", func(t *testing.T) {
		t.Setenv(AllowNonBAAEnv, "1")
		c := base()
		c.LLM.Backend = BackendGeminiAPI
		c.LLM.Project, c.LLM.Location = "", ""
		require.NoError(t, c.Validate())
	})

	t.Run("unknown backend fails", func(t *testing.T) {
		c := base()
		c.LLM.Backend = "bogus"
		require.Error(t, c.Validate())
	})

	t.Run("empty backend fails", func(t *testing.T) {
		c := base()
		c.LLM.Backend = ""
		require.Error(t, c.Validate())
	})
}

func TestValidate_ExternalProviders(t *testing.T) {
	base := func() Config {
		return Config{
			Sources: []SourceConfig{{Type: "file", Path: "x.log"}},
			LLM: LLMConfig{
				Provider: "gemini", Model: "m",
				Backend: BackendVertex, Project: "p", Location: "us-central1",
			},
			Output:    OutputConfig{Dir: "./out"},
			Target:    TargetLocal,
			Validator: ValidatorNone,
			Log:       LogConfig{Format: "json"},
		}
	}

	t.Run("openai as primary without opt-in fails closed", func(t *testing.T) {
		c := base()
		c.LLM = LLMConfig{Provider: KindOpenAI, Model: "gpt-4o-mini"}
		err := c.Validate()
		require.Error(t, err)
		require.Contains(t, err.Error(), "external")
		require.Contains(t, err.Error(), "BAA")
	})

	t.Run("anthropic as primary without opt-in fails closed", func(t *testing.T) {
		c := base()
		c.LLM = LLMConfig{Provider: KindAnthropic, Model: "claude-opus-4-8"}
		err := c.Validate()
		require.Error(t, err)
		require.Contains(t, err.Error(), "external")
	})

	t.Run("openai primary with config opt-in is allowed", func(t *testing.T) {
		c := base()
		c.LLM = LLMConfig{Provider: KindOpenAI, Model: "gpt-4o-mini", AllowExternal: true}
		require.NoError(t, c.Validate())
	})

	t.Run("openai primary with env opt-in is allowed", func(t *testing.T) {
		t.Setenv(AllowExternalLLMEnv, "1")
		c := base()
		c.LLM = LLMConfig{Provider: KindOpenAI, Model: "gpt-4o-mini"}
		require.NoError(t, c.Validate())
	})

	t.Run("anthropic fallback without opt-in fails closed", func(t *testing.T) {
		c := base()
		c.LLM.Fallbacks = []ProviderConfig{{Kind: KindAnthropic, Model: "claude-opus-4-8"}}
		err := c.Validate()
		require.Error(t, err)
		require.Contains(t, err.Error(), "fallbacks[0]")
		require.Contains(t, err.Error(), "external")
	})

	t.Run("gemini primary + external fallback with opt-in is allowed", func(t *testing.T) {
		c := base()
		c.LLM.AllowExternal = true
		c.LLM.Fallbacks = []ProviderConfig{
			{Kind: KindOpenAI, Model: "gpt-4o-mini"},
			{Kind: KindAnthropic, Model: "claude-opus-4-8"},
		}
		require.NoError(t, c.Validate())
	})

	t.Run("gemini fallback validates its backend", func(t *testing.T) {
		c := base()
		c.LLM.Fallbacks = []ProviderConfig{{Kind: KindGemini, Model: "gemini-2.5-pro", Backend: BackendVertex}}
		err := c.Validate()
		require.Error(t, err)
		require.Contains(t, err.Error(), "fallbacks[0]")
		require.Contains(t, err.Error(), "Vertex")
	})

	t.Run("gemini fallback with full vertex config is allowed", func(t *testing.T) {
		c := base()
		c.LLM.Fallbacks = []ProviderConfig{
			{Kind: KindGemini, Model: "gemini-2.5-pro", Backend: BackendVertex, Project: "p", Location: "us-central1"},
		}
		require.NoError(t, c.Validate())
	})

	t.Run("fallback with unknown kind fails", func(t *testing.T) {
		c := base()
		c.LLM.AllowExternal = true
		c.LLM.Fallbacks = []ProviderConfig{{Kind: "cohere", Model: "x"}}
		err := c.Validate()
		require.Error(t, err)
		require.Contains(t, err.Error(), "fallbacks[0]")
	})

	t.Run("fallback missing model fails", func(t *testing.T) {
		c := base()
		c.LLM.AllowExternal = true
		c.LLM.Fallbacks = []ProviderConfig{{Kind: KindOpenAI}}
		err := c.Validate()
		require.Error(t, err)
		require.Contains(t, err.Error(), "model is required")
	})
}

// TestValidate_Ollama covers the local/self-hosted ollama provider, which is
// EXEMPT from the external-disclosure (BAA) gate: it must be selectable as
// primary and as a fallback WITHOUT allow_external.
func TestValidate_Ollama(t *testing.T) {
	base := func() Config {
		return Config{
			Sources:   []SourceConfig{{Type: "file", Path: "x.log"}},
			Output:    OutputConfig{Dir: "./out"},
			Target:    TargetLocal,
			Validator: ValidatorNone,
			Log:       LogConfig{Format: "json"},
		}
	}

	t.Run("ollama as primary without opt-in is allowed", func(t *testing.T) {
		c := base()
		c.LLM = LLMConfig{Provider: KindOllama, Model: "llama3.1"}
		require.NoError(t, c.Validate())
	})

	t.Run("ollama as primary with explicit host is allowed", func(t *testing.T) {
		c := base()
		c.LLM = LLMConfig{Provider: KindOllama, Model: "llama3.1", Host: "http://ollama.internal:11434"}
		require.NoError(t, c.Validate())
	})

	t.Run("ollama as fallback without opt-in is allowed", func(t *testing.T) {
		c := base()
		c.LLM = LLMConfig{
			Provider: KindGemini, Model: "gemini-2.5-flash",
			Backend: BackendVertex, Project: "p", Location: "us-central1",
			Fallbacks: []ProviderConfig{{Kind: KindOllama, Model: "llama3.1"}},
		}
		// No AllowExternal set: ollama is exempt from the external gate.
		require.False(t, c.LLM.AllowsExternal())
		require.NoError(t, c.Validate())
	})

	t.Run("ollama missing model fails", func(t *testing.T) {
		c := base()
		c.LLM = LLMConfig{Provider: KindOllama, Model: ""}
		err := c.Validate()
		require.Error(t, err)
		require.Contains(t, err.Error(), "model is required")
	})
}

// TestLoad_OllamaProvider loads an ollama config from YAML to confirm the host
// field round-trips and the provider is accepted without allow_external.
func TestLoad_OllamaProvider(t *testing.T) {
	p := writeConfig(t, `
sources:
  - type: file
    path: ./x.log
llm:
  provider: ollama
  model: llama3.1
  host: http://localhost:11434
  fallbacks:
    - kind: ollama
      model: llama3.2
      host: http://ollama.internal:11434
`)
	cfg, err := Load(p)
	require.NoError(t, err)
	assert.Equal(t, KindOllama, cfg.LLM.Provider)
	assert.Equal(t, "http://localhost:11434", cfg.LLM.Host)
	require.Len(t, cfg.LLM.Fallbacks, 1)
	assert.Equal(t, KindOllama, cfg.LLM.Fallbacks[0].Kind)
	assert.Equal(t, "http://ollama.internal:11434", cfg.LLM.Fallbacks[0].Host)

	// Primary projection carries the host through.
	assert.Equal(t, "http://localhost:11434", cfg.LLM.Primary().Host)
}

func TestLoad_PrimaryAndFallbacks(t *testing.T) {
	p := writeConfig(t, `
sources:
  - type: file
    path: ./x.log
llm:
  provider: gemini
  model: gemini-2.5-flash
  backend: vertex
  project: my-gcp-project
  location: us-central1
  allow_external: true
  fallbacks:
    - kind: openai
      model: gpt-4o-mini
      base_url: https://gw.example.com
    - kind: anthropic
      model: claude-opus-4-8
`)
	cfg, err := Load(p)
	require.NoError(t, err)
	require.Len(t, cfg.LLM.Fallbacks, 2)
	assert.Equal(t, KindOpenAI, cfg.LLM.Fallbacks[0].Kind)
	assert.Equal(t, "gpt-4o-mini", cfg.LLM.Fallbacks[0].Model)
	assert.Equal(t, "https://gw.example.com", cfg.LLM.Fallbacks[0].BaseURL)
	assert.Equal(t, KindAnthropic, cfg.LLM.Fallbacks[1].Kind)

	chain := cfg.LLM.Providers()
	require.Len(t, chain, 3)
	assert.Equal(t, KindGemini, chain[0].Kind)
	assert.Equal(t, BackendVertex, chain[0].Backend)
	assert.Equal(t, KindOpenAI, chain[1].Kind)
	assert.Equal(t, KindAnthropic, chain[2].Kind)
}

func TestValidate(t *testing.T) {
	base := func() Config {
		return Config{
			Sources: []SourceConfig{{Type: "file", Path: "x.log"}},
			LLM: LLMConfig{
				Provider: "gemini", Model: "m",
				Backend: BackendVertex, Project: "p", Location: "us-central1",
			},
			Output:    OutputConfig{Dir: "./out"},
			Target:    TargetLocal,
			Validator: ValidatorNone,
			Log:       LogConfig{Format: "json"},
		}
	}
	require.NoError(t, base().Validate())

	c := base()
	c.Sources = nil
	assert.Error(t, c.Validate())

	c = base()
	c.Sources[0].Path = ""
	assert.Error(t, c.Validate())

	c = base()
	c.LLM.Provider = ""
	assert.Error(t, c.Validate())

	c = base()
	c.LLM.Model = ""
	assert.Error(t, c.Validate())

	c = base()
	c.Output.Dir = ""
	assert.Error(t, c.Validate())

	c = base()
	c.Log.Format = "xml"
	assert.Error(t, c.Validate())
}

func TestLoad_MissingSourcesFails(t *testing.T) {
	p := writeConfig(t, `llm: {provider: gemini, model: m}`)
	_, err := Load(p)
	assert.Error(t, err)
}

func TestLoad_PubSubSource(t *testing.T) {
	p := writeConfig(t, `
sources:
  - type: pubsub
    project_id: my-gcp-project
    subscription_id: logs-sub
llm:
  project: my-gcp-project
`)
	cfg, err := Load(p)
	require.NoError(t, err)
	require.Len(t, cfg.Sources, 1)
	assert.Equal(t, SourceTypePubSub, cfg.Sources[0].Type)
	assert.Equal(t, "my-gcp-project", cfg.Sources[0].ProjectID)
	assert.Equal(t, "logs-sub", cfg.Sources[0].SubscriptionID)
	// Tracing defaults to none.
	assert.Equal(t, TracingExporterNone, cfg.Tracing.Exporter)
}

func TestLoad_TracingBlock(t *testing.T) {
	p := writeConfig(t, `
sources:
  - type: file
    path: ./x.log
llm:
  project: my-gcp-project
tracing:
  exporter: cloudtrace
  project: trace-project
`)
	cfg, err := Load(p)
	require.NoError(t, err)
	assert.Equal(t, TracingExporterCloudTrace, cfg.Tracing.Exporter)
	assert.Equal(t, "trace-project", cfg.Tracing.Project)
}

func TestValidate_PubSubSource(t *testing.T) {
	base := func() Config {
		return Config{
			Sources: []SourceConfig{{Type: SourceTypePubSub, ProjectID: "p", SubscriptionID: "s"}},
			LLM: LLMConfig{
				Provider: "gemini", Model: "m",
				Backend: BackendVertex, Project: "p", Location: "us-central1",
			},
			Output:    OutputConfig{Dir: "./out"},
			Target:    TargetLocal,
			Validator: ValidatorNone,
			Log:       LogConfig{Format: "json"},
		}
	}

	require.NoError(t, base().Validate())

	c := base()
	c.Sources[0].ProjectID = ""
	require.Error(t, c.Validate())

	c = base()
	c.Sources[0].SubscriptionID = ""
	require.Error(t, c.Validate())
}

func TestValidate_UnknownSourceType(t *testing.T) {
	c := Config{
		Sources: []SourceConfig{{Type: "kafka"}},
		LLM: LLMConfig{
			Provider: "gemini", Model: "m",
			Backend: BackendVertex, Project: "p", Location: "us-central1",
		},
		Output:    OutputConfig{Dir: "./out"},
		Target:    TargetLocal,
		Validator: ValidatorNone,
		Log:       LogConfig{Format: "json"},
	}
	require.Error(t, c.Validate())
}

func TestLoad_TargetValidatorDefaults(t *testing.T) {
	p := writeConfig(t, `
sources:
  - type: file
    path: ./x.log
llm:
  project: my-gcp-project
`)
	cfg, err := Load(p)
	require.NoError(t, err)
	assert.Equal(t, TargetLocal, cfg.Target)
	assert.Equal(t, ValidatorNone, cfg.Validator)
	assert.Equal(t, "main", cfg.GitHub.BaseBranch)
	assert.Equal(t, "main", cfg.GitLab.BaseBranch)
}

func TestLoad_GitHubTargetBlock(t *testing.T) {
	p := writeConfig(t, `
sources:
  - type: file
    path: ./x.log
llm:
  project: my-gcp-project
target: github
validator: local
github:
  owner: my-org
  repo: my-repo
  base_branch: develop
`)
	cfg, err := Load(p)
	require.NoError(t, err)
	assert.Equal(t, TargetGitHub, cfg.Target)
	assert.Equal(t, ValidatorLocal, cfg.Validator)
	assert.Equal(t, "my-org", cfg.GitHub.Owner)
	assert.Equal(t, "my-repo", cfg.GitHub.Repo)
	assert.Equal(t, "develop", cfg.GitHub.BaseBranch)
}

func TestLoad_GitLabTargetBlock(t *testing.T) {
	p := writeConfig(t, `
sources:
  - type: file
    path: ./x.log
llm:
  project: my-gcp-project
target: gitlab
gitlab:
  project: my-group/my-repo
  base_branch: develop
  base_url: https://gitlab.example.com
`)
	cfg, err := Load(p)
	require.NoError(t, err)
	assert.Equal(t, TargetGitLab, cfg.Target)
	assert.Equal(t, "my-group/my-repo", cfg.GitLab.Project)
	assert.Equal(t, "develop", cfg.GitLab.BaseBranch)
	assert.Equal(t, "https://gitlab.example.com", cfg.GitLab.BaseURL)
}

func TestValidate_Target(t *testing.T) {
	base := func() Config {
		return Config{
			Sources: []SourceConfig{{Type: "file", Path: "x.log"}},
			LLM: LLMConfig{
				Provider: "gemini", Model: "m",
				Backend: BackendVertex, Project: "p", Location: "us-central1",
			},
			Output:    OutputConfig{Dir: "./out"},
			Target:    TargetLocal,
			Validator: ValidatorNone,
			Log:       LogConfig{Format: "json"},
		}
	}

	t.Run("local needs no github fields", func(t *testing.T) {
		require.NoError(t, base().Validate())
	})

	t.Run("github with owner+repo is valid", func(t *testing.T) {
		c := base()
		c.Target = TargetGitHub
		c.GitHub = GitHubConfig{Owner: "o", Repo: "r"}
		require.NoError(t, c.Validate())
	})

	t.Run("github missing owner fails", func(t *testing.T) {
		c := base()
		c.Target = TargetGitHub
		c.GitHub = GitHubConfig{Repo: "r"}
		require.Error(t, c.Validate())
	})

	t.Run("github missing repo fails", func(t *testing.T) {
		c := base()
		c.Target = TargetGitHub
		c.GitHub = GitHubConfig{Owner: "o"}
		require.Error(t, c.Validate())
	})

	t.Run("gitlab with project is valid", func(t *testing.T) {
		c := base()
		c.Target = TargetGitLab
		c.GitLab = GitLabConfig{Project: "group/repo"}
		require.NoError(t, c.Validate())
	})

	t.Run("gitlab missing project fails", func(t *testing.T) {
		c := base()
		c.Target = TargetGitLab
		c.GitLab = GitLabConfig{}
		require.Error(t, c.Validate())
	})

	t.Run("unknown target fails", func(t *testing.T) {
		c := base()
		c.Target = "bitbucket"
		require.Error(t, c.Validate())
	})

	t.Run("empty target fails", func(t *testing.T) {
		c := base()
		c.Target = ""
		require.Error(t, c.Validate())
	})
}

func TestValidate_Validator(t *testing.T) {
	base := func() Config {
		return Config{
			Sources: []SourceConfig{{Type: "file", Path: "x.log"}},
			LLM: LLMConfig{
				Provider: "gemini", Model: "m",
				Backend: BackendVertex, Project: "p", Location: "us-central1",
			},
			Output:    OutputConfig{Dir: "./out"},
			Target:    TargetLocal,
			Validator: ValidatorNone,
			Log:       LogConfig{Format: "json"},
		}
	}

	for _, v := range []string{ValidatorNone, ValidatorLocal} {
		c := base()
		c.Validator = v
		require.NoErrorf(t, c.Validate(), "validator %q should be valid", v)
	}

	c := base()
	c.Validator = "sandbox"
	require.Error(t, c.Validate())

	c = base()
	c.Validator = ""
	require.Error(t, c.Validate())
}

func TestValidate_Tracing(t *testing.T) {
	base := func() Config {
		return Config{
			Sources: []SourceConfig{{Type: "file", Path: "x.log"}},
			LLM: LLMConfig{
				Provider: "gemini", Model: "m",
				Backend: BackendVertex, Project: "p", Location: "us-central1",
			},
			Output:    OutputConfig{Dir: "./out"},
			Target:    TargetLocal,
			Validator: ValidatorNone,
			Log:       LogConfig{Format: "json"},
		}
	}

	for _, exp := range []string{"", TracingExporterNone, TracingExporterStdout, TracingExporterCloudTrace} {
		c := base()
		c.Tracing.Exporter = exp
		require.NoErrorf(t, c.Validate(), "exporter %q should be valid", exp)
	}

	c := base()
	c.Tracing.Exporter = "otlp"
	require.Error(t, c.Validate())
}
