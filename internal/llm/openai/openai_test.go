package openai

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	oai "github.com/openai/openai-go/v3"
	"github.com/openai/openai-go/v3/option"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/avivl/cloud-sre-agent/internal/llm"
)

// capturedRequest is the decoded JSON body the SDK sent to the chat
// completions endpoint, used to assert request shaping.
type capturedRequest struct {
	Model               string            `json:"model"`
	Messages            []capturedMessage `json:"messages"`
	Temperature         *float64          `json:"temperature"`
	MaxCompletionTokens *int64            `json:"max_completion_tokens"`
	ResponseFormat      *struct {
		Type       string `json:"type"`
		JSONSchema struct {
			Name   string          `json:"name"`
			Strict bool            `json:"strict"`
			Schema json.RawMessage `json:"schema"`
		} `json:"json_schema"`
	} `json:"response_format"`
}

type capturedMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// chatServer spins up an httptest server that decodes the request body into
// got and replies with the supplied status and body. It returns a Provider
// pointed at the server via Config.BaseURL — the hermetic test seam.
func chatServer(t *testing.T, model string, status int, respBody string, got *capturedRequest) *Provider {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, http.MethodPost, r.Method)
		assert.Equal(t, "/chat/completions", r.URL.Path)
		assert.Equal(t, "Bearer test-key", r.Header.Get("Authorization"))

		if got != nil {
			body, err := io.ReadAll(r.Body)
			require.NoError(t, err)
			require.NoError(t, json.Unmarshal(body, got))
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = io.WriteString(w, respBody)
	}))
	t.Cleanup(srv.Close)

	p, err := New(Config{Model: model, APIKey: "test-key", BaseURL: srv.URL})
	require.NoError(t, err)
	return p
}

// completionJSON builds a minimal chat.completion response body.
func completionJSON(t *testing.T, model, content, finish string, prompt, completion, total int64) string {
	t.Helper()
	b, err := json.Marshal(map[string]any{
		"id":      "chatcmpl-test",
		"object":  "chat.completion",
		"created": 0,
		"model":   model,
		"choices": []map[string]any{{
			"index":         0,
			"finish_reason": finish,
			"message":       map[string]any{"role": "assistant", "content": content},
		}},
		"usage": map[string]any{
			"prompt_tokens":     prompt,
			"completion_tokens": completion,
			"total_tokens":      total,
		},
	})
	require.NoError(t, err)
	return string(b)
}

func TestProviderName(t *testing.T) {
	p := newWithCompleter(nil, "gpt-4o-mini")
	assert.Equal(t, "openai", p.Name())
}

func TestGenerate_RequestShaping(t *testing.T) {
	var got capturedRequest
	body := completionJSON(t, "gpt-4o-mini", "hi", "stop", 11, 7, 18)
	p := chatServer(t, "gpt-4o-mini", http.StatusOK, body, &got)

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
	assert.Equal(t, "gpt-4o-mini", got.Model)

	// Roles mapped: system -> system, user -> user, model -> assistant, in order.
	require.Len(t, got.Messages, 3)
	assert.Equal(t, capturedMessage{Role: "system", Content: "you are an SRE"}, got.Messages[0])
	assert.Equal(t, capturedMessage{Role: "user", Content: "diagnose this"}, got.Messages[1])
	assert.Equal(t, capturedMessage{Role: "assistant", Content: "prior turn"}, got.Messages[2])

	// Sampling controls mapped; MaxTokens -> max_completion_tokens.
	require.NotNil(t, got.Temperature)
	assert.InDelta(t, 0.3, *got.Temperature, 1e-6)
	require.NotNil(t, got.MaxCompletionTokens)
	assert.Equal(t, int64(256), *got.MaxCompletionTokens)

	// No schema -> no response_format.
	assert.Nil(t, got.ResponseFormat)
}

func TestGenerate_ModelOverride(t *testing.T) {
	var got capturedRequest
	body := completionJSON(t, "gpt-4o", "ok", "stop", 0, 0, 0)
	p := chatServer(t, "gpt-4o-mini", http.StatusOK, body, &got)

	_, err := p.Generate(context.Background(), llm.Request{
		Model:    "gpt-4o",
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.NoError(t, err)
	assert.Equal(t, "gpt-4o", got.Model)
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
	body := completionJSON(t, "gpt-4o-mini", canned, "stop", 5, 4, 9)
	p := chatServer(t, "gpt-4o-mini", http.StatusOK, body, &got)

	req := llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "triage"}},
	}.WithSchema(schema, "triage")

	resp, err := p.Generate(context.Background(), req)
	require.NoError(t, err)

	// Schema translated into a strict json_schema response_format.
	require.NotNil(t, got.ResponseFormat)
	assert.Equal(t, "json_schema", got.ResponseFormat.Type)
	assert.Equal(t, "triage", got.ResponseFormat.JSONSchema.Name)
	assert.True(t, got.ResponseFormat.JSONSchema.Strict)
	assert.JSONEq(t, string(schema), string(got.ResponseFormat.JSONSchema.Schema))

	// Strict json_schema mode requires "required" to list every "properties"
	// key. Assert the sent schema satisfies that so OpenAI would accept it.
	var sent map[string]any
	require.NoError(t, json.Unmarshal(got.ResponseFormat.JSONSchema.Schema, &sent))
	sentProps := sent["properties"].(map[string]any)
	sentReq := sent["required"].([]any)
	assert.Len(t, sentReq, len(sentProps), "strict mode: required must cover all properties")

	// Caller recovers the typed value from the JSON text.
	assert.Equal(t, canned, resp.Text)
	var out triage
	require.NoError(t, resp.Decode(&out))
	assert.Equal(t, triage{Category: "latency", Confidence: 80}, out)
}

func TestGenerate_StructuredOutput_DefaultSchemaName(t *testing.T) {
	schema, err := llm.SchemaFor[triage]()
	require.NoError(t, err)

	var got capturedRequest
	body := completionJSON(t, "gpt-4o-mini", "{}", "stop", 0, 0, 0)
	p := chatServer(t, "gpt-4o-mini", http.StatusOK, body, &got)

	// Schema set without a name -> provider supplies a default name.
	req := llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		Schema:   schema,
	}
	_, err = p.Generate(context.Background(), req)
	require.NoError(t, err)
	require.NotNil(t, got.ResponseFormat)
	assert.Equal(t, "response", got.ResponseFormat.JSONSchema.Name)
}

func TestGenerate_ResponseMapping(t *testing.T) {
	// The response's own model field wins over the request default.
	body := completionJSON(t, "gpt-4o-mini-2024-07-18", "answer", "length", 11, 7, 18)
	p := chatServer(t, "gpt-4o-mini", http.StatusOK, body, nil)

	resp, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "q"}},
	})
	require.NoError(t, err)

	assert.Equal(t, "answer", resp.Text)
	assert.Equal(t, "gpt-4o-mini-2024-07-18", resp.Model)
	assert.Equal(t, "length", resp.FinishReason)
	assert.Equal(t, llm.Usage{PromptTokens: 11, CompletionTokens: 7, TotalTokens: 18}, resp.Usage)
}

func TestGenerate_APIError(t *testing.T) {
	// A 400 is not retried by the SDK, so the error path returns promptly.
	errBody := `{"error":{"message":"bad request","type":"invalid_request_error"}}`
	p := chatServer(t, "gpt-4o-mini", http.StatusBadRequest, errBody, nil)

	_, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.Error(t, err)
	assert.ErrorContains(t, err, "openai: chat completion")
}

// mockCompleter is a minimal in-memory chatCompleter for the cases that do not
// need an HTTP round-trip (input validation, no-choices, generator error).
type mockCompleter struct {
	resp *oai.ChatCompletion
	err  error
}

func (m *mockCompleter) New(_ context.Context, _ oai.ChatCompletionNewParams, _ ...option.RequestOption) (*oai.ChatCompletion, error) {
	return m.resp, m.err
}

func TestGenerate_Errors(t *testing.T) {
	t.Run("no messages", func(t *testing.T) {
		p := newWithCompleter(&mockCompleter{}, "m")
		_, err := p.Generate(context.Background(), llm.Request{})
		require.Error(t, err)
	})

	t.Run("unknown role", func(t *testing.T) {
		p := newWithCompleter(&mockCompleter{}, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: "robot", Content: "x"}},
		})
		require.Error(t, err)
	})

	t.Run("invalid schema", func(t *testing.T) {
		p := newWithCompleter(&mockCompleter{}, "m")
		req := llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		}.WithSchema(json.RawMessage(`{not json`), "bad")
		_, err := p.Generate(context.Background(), req)
		require.Error(t, err)
	})

	t.Run("completer error", func(t *testing.T) {
		p := newWithCompleter(&mockCompleter{err: errors.New("boom")}, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		})
		require.ErrorContains(t, err, "boom")
	})

	t.Run("no choices", func(t *testing.T) {
		p := newWithCompleter(&mockCompleter{resp: &oai.ChatCompletion{}}, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		})
		require.Error(t, err)
	})

	t.Run("nil response", func(t *testing.T) {
		p := newWithCompleter(&mockCompleter{resp: nil}, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		})
		require.Error(t, err)
	})
}

// refusalJSON builds a chat.completion whose single choice carries an empty
// content and a non-empty refusal.
func refusalJSON(t *testing.T, model, refusal string) string {
	t.Helper()
	b, err := json.Marshal(map[string]any{
		"id":      "chatcmpl-test",
		"object":  "chat.completion",
		"created": 0,
		"model":   model,
		"choices": []map[string]any{{
			"index":         0,
			"finish_reason": "stop",
			"message":       map[string]any{"role": "assistant", "content": "", "refusal": refusal},
		}},
		"usage": map[string]any{"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1},
	})
	require.NoError(t, err)
	return string(b)
}

// TestGenerate_Refusal is the FIX 2 regression: an empty-content response with a
// refusal must surface as an error (with no refusal text echoed) so the router
// can fall back.
func TestGenerate_Refusal(t *testing.T) {
	body := refusalJSON(t, "gpt-4o-mini", "I cannot help with that")
	p := chatServer(t, "gpt-4o-mini", http.StatusOK, body, nil)

	_, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.Error(t, err)
	assert.ErrorContains(t, err, "refused")
	// The refusal text itself must never leak into the error.
	assert.NotContains(t, err.Error(), "I cannot help with that")
}

// TestGenerate_TruncatedStructuredOutput is the FIX 3 regression: a
// structured-output request truncated by the token limit (finish_reason
// "length") must surface as a terminal error so the router advances.
func TestGenerate_TruncatedStructuredOutput(t *testing.T) {
	schema, err := llm.SchemaFor[triage]()
	require.NoError(t, err)

	// Partial JSON + length finish reason: the response is unusable.
	body := completionJSON(t, "gpt-4o-mini", `{"category":"lat`, "length", 5, 4, 9)
	p := chatServer(t, "gpt-4o-mini", http.StatusOK, body, nil)

	req := llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "triage"}},
	}.WithSchema(schema, "triage")

	_, err = p.Generate(context.Background(), req)
	require.Error(t, err)
	assert.ErrorContains(t, err, "truncated")
}

// TestGenerate_TruncatedNoSchema verifies the truncation guard is scoped to
// structured-output requests: a plain (no-schema) request that finishes with
// "length" still returns its (possibly partial) text, not an error.
func TestGenerate_TruncatedNoSchema(t *testing.T) {
	body := completionJSON(t, "gpt-4o-mini", "partial text", "length", 5, 4, 9)
	p := chatServer(t, "gpt-4o-mini", http.StatusOK, body, nil)

	resp, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.NoError(t, err)
	assert.Equal(t, "partial text", resp.Text)
	assert.Equal(t, "length", resp.FinishReason)
}

// TestGenerate_StructuredOutput_SanitizesSchemaName is the FIX 4 regression: a
// caller-supplied name with characters outside ^[a-zA-Z0-9_-]{1,64}$ is
// coerced into a valid name before being sent, so strict mode would accept it.
func TestGenerate_StructuredOutput_SanitizesSchemaName(t *testing.T) {
	schema, err := llm.SchemaFor[triage]()
	require.NoError(t, err)

	var got capturedRequest
	body := completionJSON(t, "gpt-4o-mini", "{}", "stop", 0, 0, 0)
	p := chatServer(t, "gpt-4o-mini", http.StatusOK, body, &got)

	req := llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	}.WithSchema(schema, "triage/result v1!")

	_, err = p.Generate(context.Background(), req)
	require.NoError(t, err)
	require.NotNil(t, got.ResponseFormat)
	assert.Equal(t, "triage_result_v1_", got.ResponseFormat.JSONSchema.Name)
	assert.Regexp(t, `^[a-zA-Z0-9_-]{1,64}$`, got.ResponseFormat.JSONSchema.Name)
}

// TestSanitizeSchemaName covers the helper's edge cases directly.
func TestSanitizeSchemaName(t *testing.T) {
	assert.Equal(t, "response", sanitizeSchemaName(""))
	assert.Equal(t, "ok-name_1", sanitizeSchemaName("ok-name_1"))
	assert.Equal(t, "a_b_c", sanitizeSchemaName("a.b c"))
	// All-invalid collapses to underscores, never empty.
	assert.Equal(t, "___", sanitizeSchemaName("!@#"))
	// Truncated to 64 characters.
	long := sanitizeSchemaName(strings.Repeat("x", 100))
	assert.Len(t, long, 64)
}

func TestNew_Validation(t *testing.T) {
	t.Run("missing model", func(t *testing.T) {
		_, err := New(Config{APIKey: "k"})
		require.Error(t, err)
	})

	t.Run("missing api key", func(t *testing.T) {
		_, err := New(Config{Model: "m"})
		require.Error(t, err)
	})

	t.Run("ok", func(t *testing.T) {
		p, err := New(Config{Model: "m", APIKey: "k"})
		require.NoError(t, err)
		assert.Equal(t, "openai", p.Name())
	})

	t.Run("ok with base url", func(t *testing.T) {
		p, err := New(Config{Model: "m", APIKey: "k", BaseURL: "https://example.test/v1"})
		require.NoError(t, err)
		assert.Equal(t, "openai", p.Name())
	})
}
