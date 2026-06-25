package gemini

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"google.golang.org/genai"

	"github.com/avivl/cloud-sre-agent/internal/llm"
	"github.com/avivl/cloud-sre-agent/internal/resilience"
)

// mockGenerator is an in-memory generator seam: it records the arguments of
// the last call and returns a canned response, so tests never touch the
// network.
type mockGenerator struct {
	gotModel    string
	gotContents []*genai.Content
	gotConfig   *genai.GenerateContentConfig
	resp        *genai.GenerateContentResponse
	err         error
}

func (m *mockGenerator) GenerateContent(_ context.Context, model string, contents []*genai.Content, config *genai.GenerateContentConfig) (*genai.GenerateContentResponse, error) {
	m.gotModel = model
	m.gotContents = contents
	m.gotConfig = config
	return m.resp, m.err
}

func TestProviderName(t *testing.T) {
	p := newWithGenerator(&mockGenerator{}, "gemini-2.5-flash")
	assert.Equal(t, "gemini", p.Name())
}

func TestGenerate_RequestShaping(t *testing.T) {
	mock := &mockGenerator{resp: buildResp("hi", "gemini-2.5-flash", 11, 7, 18)}
	p := newWithGenerator(mock, "gemini-2.5-flash")

	temp := 0.3
	req := llm.Request{
		Messages: []llm.Message{
			{Role: llm.RoleSystem, Content: "you are an SRE"},
			{Role: llm.RoleUser, Content: "diagnose this"},
			{Role: llm.RoleModel, Content: "prior turn"},
		},
		Temperature: &temp,
		MaxTokens:   256,
	}

	_, err := p.Generate(context.Background(), req)
	require.NoError(t, err)

	// Default model used when Request.Model is empty.
	assert.Equal(t, "gemini-2.5-flash", mock.gotModel)

	// System message extracted into the system instruction, not contents.
	require.NotNil(t, mock.gotConfig.SystemInstruction)
	require.Len(t, mock.gotConfig.SystemInstruction.Parts, 1)
	assert.Equal(t, "you are an SRE", mock.gotConfig.SystemInstruction.Parts[0].Text)

	// User + model turns become contents in order.
	require.Len(t, mock.gotContents, 2)
	assert.Equal(t, string(genai.RoleUser), mock.gotContents[0].Role)
	assert.Equal(t, "diagnose this", mock.gotContents[0].Parts[0].Text)
	assert.Equal(t, string(genai.RoleModel), mock.gotContents[1].Role)
	assert.Equal(t, "prior turn", mock.gotContents[1].Parts[0].Text)

	// Sampling controls mapped.
	require.NotNil(t, mock.gotConfig.Temperature)
	assert.InDelta(t, 0.3, float64(*mock.gotConfig.Temperature), 1e-6)
	assert.Equal(t, int32(256), mock.gotConfig.MaxOutputTokens)

	// No schema -> no JSON constraint.
	assert.Empty(t, mock.gotConfig.ResponseMIMEType)
	assert.Nil(t, mock.gotConfig.ResponseJsonSchema)
}

func TestGenerate_ModelOverride(t *testing.T) {
	mock := &mockGenerator{resp: buildResp("ok", "", 0, 0, 0)}
	p := newWithGenerator(mock, "gemini-2.5-flash")

	_, err := p.Generate(context.Background(), llm.Request{
		Model:    "gemini-2.5-pro",
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.NoError(t, err)
	assert.Equal(t, "gemini-2.5-pro", mock.gotModel)
}

// triage mirrors a structured-output target type.
type triage struct {
	Category   string `json:"category"`
	Confidence int    `json:"confidence"`
}

func TestGenerate_StructuredOutput(t *testing.T) {
	schema, err := llm.SchemaFor[triage]()
	require.NoError(t, err)

	canned := `{"category":"latency","confidence":80}`
	mock := &mockGenerator{resp: buildResp(canned, "gemini-2.5-flash", 5, 4, 9)}
	p := newWithGenerator(mock, "gemini-2.5-flash")

	req := llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "triage"}},
	}.WithSchema(schema, "triage")

	resp, err := p.Generate(context.Background(), req)
	require.NoError(t, err)

	// Schema translated into genai's JSON-constrained output.
	assert.Equal(t, "application/json", mock.gotConfig.ResponseMIMEType)
	require.NotNil(t, mock.gotConfig.ResponseJsonSchema)
	// The schema passed through is structurally the request schema.
	gotSchema, err := json.Marshal(mock.gotConfig.ResponseJsonSchema)
	require.NoError(t, err)
	assert.JSONEq(t, string(schema), string(gotSchema))

	// Caller recovers the typed value from the JSON text.
	assert.Equal(t, canned, resp.Text)
	var got triage
	require.NoError(t, resp.Decode(&got))
	assert.Equal(t, triage{Category: "latency", Confidence: 80}, got)
}

func TestGenerate_ResponseMapping(t *testing.T) {
	mock := &mockGenerator{resp: buildResp("answer", "gemini-2.5-flash-002", 11, 7, 18)}
	p := newWithGenerator(mock, "gemini-2.5-flash")

	resp, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "q"}},
	})
	require.NoError(t, err)

	assert.Equal(t, "answer", resp.Text)
	// ModelVersion from the response wins over the request default.
	assert.Equal(t, "gemini-2.5-flash-002", resp.Model)
	assert.Equal(t, "STOP", resp.FinishReason)
	assert.Equal(t, llm.Usage{PromptTokens: 11, CompletionTokens: 7, TotalTokens: 18}, resp.Usage)
}

func TestGenerate_Errors(t *testing.T) {
	t.Run("no messages", func(t *testing.T) {
		p := newWithGenerator(&mockGenerator{}, "m")
		_, err := p.Generate(context.Background(), llm.Request{})
		require.Error(t, err)
	})

	t.Run("unknown role", func(t *testing.T) {
		p := newWithGenerator(&mockGenerator{}, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: "robot", Content: "x"}},
		})
		require.Error(t, err)
	})

	t.Run("invalid schema", func(t *testing.T) {
		p := newWithGenerator(&mockGenerator{}, "m")
		req := llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		}.WithSchema(json.RawMessage(`{not json`), "bad")
		_, err := p.Generate(context.Background(), req)
		require.Error(t, err)
	})

	t.Run("generator error", func(t *testing.T) {
		mock := &mockGenerator{err: errors.New("boom")}
		p := newWithGenerator(mock, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		})
		require.ErrorContains(t, err, "boom")
	})

	t.Run("nil response", func(t *testing.T) {
		mock := &mockGenerator{resp: nil}
		p := newWithGenerator(mock, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		})
		require.Error(t, err)
	})
}

// flakyGenerator fails its first failures calls, then returns ok on every
// subsequent call. It counts total invocations.
type flakyGenerator struct {
	failures int
	calls    int
	ok       *genai.GenerateContentResponse
}

func (f *flakyGenerator) GenerateContent(_ context.Context, _ string, _ []*genai.Content, _ *genai.GenerateContentConfig) (*genai.GenerateContentResponse, error) {
	f.calls++
	if f.calls <= f.failures {
		return nil, errors.New("transient")
	}
	return f.ok, nil
}

func TestGenerate_RetriesTransientFailures(t *testing.T) {
	flaky := &flakyGenerator{failures: 2, ok: buildResp("recovered", "gemini-2.5-flash", 1, 1, 2)}
	// 3 retries, tiny delays so the test is fast; no breaker/limiter to keep the
	// assertion about retry alone.
	cfg := resilience.Config{
		Retry: resilience.RetryConfig{
			Enabled:      true,
			MaxRetries:   3,
			InitialDelay: time.Millisecond,
			MaxDelay:     2 * time.Millisecond,
		},
	}
	p := newWithGeneratorAndPolicies(flaky, "gemini-2.5-flash", cfg)

	resp, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.NoError(t, err)
	assert.Equal(t, "recovered", resp.Text)
	// 2 failures + 1 success = 3 calls. Retry actually triggered.
	assert.Equal(t, 3, flaky.calls)
}

func TestGenerate_RetryExhaustedReturnsError(t *testing.T) {
	flaky := &flakyGenerator{failures: 10, ok: buildResp("never", "m", 0, 0, 0)}
	cfg := resilience.Config{
		Retry: resilience.RetryConfig{
			Enabled:      true,
			MaxRetries:   2,
			InitialDelay: time.Millisecond,
			MaxDelay:     2 * time.Millisecond,
		},
	}
	p := newWithGeneratorAndPolicies(flaky, "m", cfg)

	_, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.Error(t, err)
	// initial attempt + 2 retries = 3 calls.
	assert.Equal(t, 3, flaky.calls)
}

func TestNew_DefaultResiliencePolicies(t *testing.T) {
	// New substitutes DefaultConfig when Resilience is zero, so the provider ends
	// up with a non-empty policy stack.
	p, err := New(context.Background(), Config{Model: "m", Backend: BackendGeminiAPI, APIKey: "k"})
	require.NoError(t, err)
	assert.NotEmpty(t, p.policies)
}

func TestNew_Validation(t *testing.T) {
	ctx := context.Background()

	t.Run("missing model", func(t *testing.T) {
		_, err := New(ctx, Config{Backend: BackendGeminiAPI, APIKey: "k"})
		require.Error(t, err)
	})

	t.Run("gemini api missing key", func(t *testing.T) {
		_, err := New(ctx, Config{Model: "m", Backend: BackendGeminiAPI})
		require.Error(t, err)
	})

	t.Run("vertex missing project/location", func(t *testing.T) {
		_, err := New(ctx, Config{Model: "m", Backend: BackendVertexAI})
		require.Error(t, err)
	})

	t.Run("unknown backend", func(t *testing.T) {
		_, err := New(ctx, Config{Model: "m", Backend: Backend(99)})
		require.Error(t, err)
	})

	t.Run("gemini api ok", func(t *testing.T) {
		p, err := New(ctx, Config{Model: "m", Backend: BackendGeminiAPI, APIKey: "k"})
		require.NoError(t, err)
		assert.Equal(t, "gemini", p.Name())
	})

	t.Run("vertex ok", func(t *testing.T) {
		p, err := New(ctx, Config{Model: "m", Backend: BackendVertexAI, Project: "p", Location: "us-central1"})
		require.NoError(t, err)
		assert.Equal(t, "gemini", p.Name())
	})
}

// buildResp constructs a genai response with a single text candidate, a STOP
// finish reason, and usage metadata.
func buildResp(text, modelVersion string, prompt, candidates, total int32) *genai.GenerateContentResponse {
	return &genai.GenerateContentResponse{
		ModelVersion: modelVersion,
		Candidates: []*genai.Candidate{
			{
				Content:      genai.NewContentFromText(text, genai.RoleModel),
				FinishReason: genai.FinishReasonStop,
			},
		},
		UsageMetadata: &genai.GenerateContentResponseUsageMetadata{
			PromptTokenCount:     prompt,
			CandidatesTokenCount: candidates,
			TotalTokenCount:      total,
		},
	}
}
