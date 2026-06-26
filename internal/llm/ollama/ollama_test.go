package ollama

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/ollama/ollama/api"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/avivl/cloud-sre-agent/internal/llm"
)

// capturedRequest is the decoded JSON body the client sent to /api/chat, used
// to assert request shaping.
type capturedRequest struct {
	Model    string            `json:"model"`
	Messages []capturedMessage `json:"messages"`
	Stream   *bool             `json:"stream"`
	Format   json.RawMessage   `json:"format"`
	Options  map[string]any    `json:"options"`
}

type capturedMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// chatServer spins up an httptest server emulating Ollama's /api/chat endpoint:
// it decodes the request body into got and replies with the supplied status and
// body (ND-JSON, one line). It returns a Provider pointed at the server via
// Config.Host — the hermetic test seam.
func chatServer(t *testing.T, model, respBody string, status int, got *capturedRequest) *Provider {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, http.MethodPost, r.Method)
		assert.Equal(t, "/api/chat", r.URL.Path)

		if got != nil {
			body, err := io.ReadAll(r.Body)
			require.NoError(t, err)
			require.NoError(t, json.Unmarshal(body, got))
		}
		w.Header().Set("Content-Type", "application/x-ndjson")
		w.WriteHeader(status)
		_, _ = io.WriteString(w, respBody)
	}))
	t.Cleanup(srv.Close)

	p, err := New(Config{Model: model, Host: srv.URL})
	require.NoError(t, err)
	return p
}

// chatJSON builds a minimal /api/chat (non-streaming) response body: one
// ND-JSON line with done=true.
func chatJSON(t *testing.T, model, content, doneReason string, promptEval, eval int) string {
	t.Helper()
	b, err := json.Marshal(map[string]any{
		"model":             model,
		"created_at":        "2024-01-01T00:00:00Z",
		"message":           map[string]any{"role": "assistant", "content": content},
		"done":              true,
		"done_reason":       doneReason,
		"prompt_eval_count": promptEval,
		"eval_count":        eval,
	})
	require.NoError(t, err)
	return string(b)
}

func TestProviderName(t *testing.T) {
	p := newWithClient(nil, "llama3.1")
	assert.Equal(t, "ollama", p.Name())
}

func TestGenerate_RequestShaping(t *testing.T) {
	var got capturedRequest
	body := chatJSON(t, "llama3.1", "hi", "stop", 11, 7)
	p := chatServer(t, "llama3.1", body, http.StatusOK, &got)

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
	assert.Equal(t, "llama3.1", got.Model)

	// Streaming is disabled so the response arrives in a single callback.
	require.NotNil(t, got.Stream)
	assert.False(t, *got.Stream)

	// Roles mapped: system -> system, user -> user, model -> assistant, in order.
	require.Len(t, got.Messages, 3)
	assert.Equal(t, capturedMessage{Role: "system", Content: "you are an SRE"}, got.Messages[0])
	assert.Equal(t, capturedMessage{Role: "user", Content: "diagnose this"}, got.Messages[1])
	assert.Equal(t, capturedMessage{Role: "assistant", Content: "prior turn"}, got.Messages[2])

	// Sampling controls mapped into Options.
	require.NotNil(t, got.Options)
	assert.InDelta(t, 0.3, got.Options["temperature"], 1e-6)
	assert.EqualValues(t, 256, got.Options["num_predict"])

	// No schema -> no format.
	assert.Empty(t, got.Format)
}

func TestGenerate_ModelOverride(t *testing.T) {
	var got capturedRequest
	body := chatJSON(t, "llama3.2", "ok", "stop", 0, 0)
	p := chatServer(t, "llama3.1", body, http.StatusOK, &got)

	_, err := p.Generate(context.Background(), llm.Request{
		Model:    "llama3.2",
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.NoError(t, err)
	assert.Equal(t, "llama3.2", got.Model)
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
	var got capturedRequest
	body := chatJSON(t, "llama3.1", canned, "stop", 5, 4)
	p := chatServer(t, "llama3.1", body, http.StatusOK, &got)

	req := llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "triage"}},
	}.WithSchema(schema, "triage")

	resp, err := p.Generate(context.Background(), req)
	require.NoError(t, err)

	// Schema passed through verbatim as the chat request's format.
	require.NotEmpty(t, got.Format)
	assert.JSONEq(t, string(schema), string(got.Format))

	// Caller recovers the typed value from the JSON text.
	assert.Equal(t, canned, resp.Text)
	var out triage
	require.NoError(t, resp.Decode(&out))
	assert.Equal(t, triage{Category: "latency", Confidence: 80}, out)
}

func TestGenerate_TruncatedStructuredOutput(t *testing.T) {
	schema, err := llm.SchemaFor[triage]()
	require.NoError(t, err)

	// done_reason "length" on a schema request = truncated JSON. Must be a
	// terminal error so the router falls back (parity with openai/anthropic).
	body := chatJSON(t, "llama3.1", `{"category":"laten`, "length", 5, 4)
	p := chatServer(t, "llama3.1", body, http.StatusOK, nil)

	req := llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "triage"}},
	}.WithSchema(schema, "triage")

	_, err = p.Generate(context.Background(), req)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "truncated")
}

func TestGenerate_EmptyStructuredOutput(t *testing.T) {
	schema, err := llm.SchemaFor[triage]()
	require.NoError(t, err)

	// Empty content on a schema request can't decode -> terminal error.
	body := chatJSON(t, "llama3.1", "", "stop", 5, 0)
	p := chatServer(t, "llama3.1", body, http.StatusOK, nil)

	req := llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "triage"}},
	}.WithSchema(schema, "triage")

	_, err = p.Generate(context.Background(), req)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "empty")
}

// A truncated NON-schema response is still a valid (partial) completion, not an
// error — the structured-output guard must not fire here.
func TestGenerate_TruncatedNoSchema(t *testing.T) {
	body := chatJSON(t, "llama3.1", "partial answer", "length", 5, 4)
	p := chatServer(t, "llama3.1", body, http.StatusOK, nil)

	resp, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "q"}},
	})
	require.NoError(t, err)
	assert.Equal(t, "partial answer", resp.Text)
}

func TestGenerate_ResponseMapping(t *testing.T) {
	// The response's own model field wins over the request default.
	body := chatJSON(t, "llama3.1:8b", "answer", "stop", 11, 7)
	p := chatServer(t, "llama3.1", body, http.StatusOK, nil)

	resp, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "q"}},
	})
	require.NoError(t, err)

	assert.Equal(t, "answer", resp.Text)
	assert.Equal(t, "llama3.1:8b", resp.Model)
	assert.Equal(t, "stop", resp.FinishReason)
	assert.Equal(t, llm.Usage{PromptTokens: 11, CompletionTokens: 7, TotalTokens: 18}, resp.Usage)
}

func TestGenerate_APIError(t *testing.T) {
	errBody := `{"error":"model not found"}`
	p := chatServer(t, "llama3.1", errBody, http.StatusNotFound, nil)

	_, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.Error(t, err)
	assert.ErrorContains(t, err, "ollama: chat")
}

// mockClient is a minimal in-memory chatClient for cases that do not need an
// HTTP round-trip (input validation, client error, response capture).
type mockClient struct {
	resp api.ChatResponse
	err  error
}

func (m *mockClient) Chat(_ context.Context, _ *api.ChatRequest, fn api.ChatResponseFunc) error {
	if m.err != nil {
		return m.err
	}
	return fn(m.resp)
}

func TestGenerate_Errors(t *testing.T) {
	t.Run("no messages", func(t *testing.T) {
		p := newWithClient(&mockClient{}, "m")
		_, err := p.Generate(context.Background(), llm.Request{})
		require.Error(t, err)
	})

	t.Run("unknown role", func(t *testing.T) {
		p := newWithClient(&mockClient{}, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: "robot", Content: "x"}},
		})
		require.Error(t, err)
	})

	t.Run("invalid schema", func(t *testing.T) {
		p := newWithClient(&mockClient{}, "m")
		req := llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		}.WithSchema(json.RawMessage(`{not json`), "bad")
		_, err := p.Generate(context.Background(), req)
		require.Error(t, err)
	})

	t.Run("client error", func(t *testing.T) {
		p := newWithClient(&mockClient{err: errors.New("boom")}, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		})
		require.ErrorContains(t, err, "boom")
	})
}

func TestNew_Validation(t *testing.T) {
	t.Run("missing model", func(t *testing.T) {
		_, err := New(Config{})
		require.Error(t, err)
	})

	t.Run("ok with default host", func(t *testing.T) {
		p, err := New(Config{Model: "llama3.1"})
		require.NoError(t, err)
		assert.Equal(t, "ollama", p.Name())
	})

	t.Run("ok with explicit host", func(t *testing.T) {
		p, err := New(Config{Model: "llama3.1", Host: "http://ollama.internal:11434"})
		require.NoError(t, err)
		assert.Equal(t, "ollama", p.Name())
	})

	t.Run("invalid host", func(t *testing.T) {
		_, err := New(Config{Model: "llama3.1", Host: "://bad"})
		require.Error(t, err)
	})
}
