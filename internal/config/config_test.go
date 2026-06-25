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
			Output: OutputConfig{Dir: "./out"},
			Log:    LogConfig{Format: "json"},
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

func TestValidate(t *testing.T) {
	base := func() Config {
		return Config{
			Sources: []SourceConfig{{Type: "file", Path: "x.log"}},
			LLM: LLMConfig{
				Provider: "gemini", Model: "m",
				Backend: BackendVertex, Project: "p", Location: "us-central1",
			},
			Output: OutputConfig{Dir: "./out"},
			Log:    LogConfig{Format: "json"},
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
