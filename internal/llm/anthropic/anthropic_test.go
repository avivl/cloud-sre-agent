package anthropic

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	sdk "github.com/anthropics/anthropic-sdk-go"
	"github.com/anthropics/anthropic-sdk-go/option"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/avivl/cloud-sre-agent/internal/llm"
	"github.com/avivl/cloud-sre-agent/internal/resilience"
)

// mockCreator is an in-memory creator seam: it records the params of the last
// call and returns a canned response, so tests never touch the network.
type mockCreator struct {
	gotParams sdk.MessageNewParams
	resp      *sdk.Message
	err       error
}

func (m *mockCreator) New(_ context.Context, params sdk.MessageNewParams, _ ...option.RequestOption) (*sdk.Message, error) {
	m.gotParams = params
	return m.resp, m.err
}

func TestProviderName(t *testing.T) {
	p := newWithCreator(&mockCreator{}, "claude-opus-4-8")
	assert.Equal(t, "anthropic", p.Name())
}

func TestGenerate_RequestShaping(t *testing.T) {
	mock := &mockCreator{resp: buildMsg("hi", "claude-opus-4-8", 11, 7)}
	p := newWithCreator(mock, "claude-opus-4-8")

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
	assert.Equal(t, sdk.Model("claude-opus-4-8"), mock.gotParams.Model)

	// System message extracted into the top-level System field, not messages.
	require.Len(t, mock.gotParams.System, 1)
	assert.Equal(t, "you are an SRE", mock.gotParams.System[0].Text)

	// User + model turns become messages in order with mapped roles.
	require.Len(t, mock.gotParams.Messages, 2)
	assert.Equal(t, sdk.MessageParamRoleUser, mock.gotParams.Messages[0].Role)
	assert.Equal(t, "diagnose this", mock.gotParams.Messages[0].Content[0].OfText.Text)
	assert.Equal(t, sdk.MessageParamRoleAssistant, mock.gotParams.Messages[1].Role)
	assert.Equal(t, "prior turn", mock.gotParams.Messages[1].Content[0].OfText.Text)

	// Sampling controls mapped.
	require.True(t, mock.gotParams.Temperature.Valid())
	assert.InDelta(t, 0.3, mock.gotParams.Temperature.Value, 1e-6)
	assert.Equal(t, int64(256), mock.gotParams.MaxTokens)

	// No schema -> no JSON output constraint.
	assert.Nil(t, mock.gotParams.OutputConfig.Format.Schema)
}

func TestGenerate_DefaultMaxTokens(t *testing.T) {
	mock := &mockCreator{resp: buildMsg("ok", "", 0, 0)}
	p := newWithCreator(mock, "claude-opus-4-8")

	_, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.NoError(t, err)
	// MaxTokens is required by the API, so a default is supplied when unset.
	assert.Equal(t, int64(defaultMaxTokens), mock.gotParams.MaxTokens)
}

func TestGenerate_ModelOverride(t *testing.T) {
	mock := &mockCreator{resp: buildMsg("ok", "", 0, 0)}
	p := newWithCreator(mock, "claude-opus-4-8")

	_, err := p.Generate(context.Background(), llm.Request{
		Model:    "claude-sonnet-4-6",
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.NoError(t, err)
	assert.Equal(t, sdk.Model("claude-sonnet-4-6"), mock.gotParams.Model)
}

func TestGenerate_ResponseMapping(t *testing.T) {
	// Two text blocks are concatenated; thinking/other blocks ignored.
	resp := &sdk.Message{
		Model:        "claude-opus-4-8",
		StopReason:   sdk.StopReasonEndTurn,
		Content:      []sdk.ContentBlockUnion{{Type: "text", Text: "ans"}, {Type: "thinking", Thinking: "hmm"}, {Type: "text", Text: "wer"}},
		Usage:        sdk.Usage{InputTokens: 11, OutputTokens: 7},
		StopSequence: "",
	}
	mock := &mockCreator{resp: resp}
	p := newWithCreator(mock, "default-model")

	out, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "q"}},
	})
	require.NoError(t, err)

	assert.Equal(t, "answer", out.Text)
	// Model from the response wins over the request default.
	assert.Equal(t, "claude-opus-4-8", out.Model)
	assert.Equal(t, "end_turn", out.FinishReason)
	assert.Equal(t, llm.Usage{PromptTokens: 11, CompletionTokens: 7, TotalTokens: 18}, out.Usage)
}

func TestGenerate_Errors(t *testing.T) {
	t.Run("no messages", func(t *testing.T) {
		p := newWithCreator(&mockCreator{}, "m")
		_, err := p.Generate(context.Background(), llm.Request{})
		require.Error(t, err)
	})

	t.Run("unknown role", func(t *testing.T) {
		p := newWithCreator(&mockCreator{}, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: "robot", Content: "x"}},
		})
		require.Error(t, err)
	})

	t.Run("invalid schema", func(t *testing.T) {
		p := newWithCreator(&mockCreator{}, "m")
		req := llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		}.WithSchema(json.RawMessage(`{not json`), "bad")
		_, err := p.Generate(context.Background(), req)
		require.Error(t, err)
	})

	t.Run("creator error", func(t *testing.T) {
		mock := &mockCreator{err: errors.New("boom")}
		p := newWithCreator(mock, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		})
		require.ErrorContains(t, err, "boom")
	})

	t.Run("nil response", func(t *testing.T) {
		mock := &mockCreator{resp: nil}
		p := newWithCreator(mock, "m")
		_, err := p.Generate(context.Background(), llm.Request{
			Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
		})
		require.Error(t, err)
	})
}

// flakyCreator fails its first failures calls, then returns ok on every
// subsequent call. It counts total invocations.
type flakyCreator struct {
	failures int
	calls    int
	ok       *sdk.Message
}

func (f *flakyCreator) New(_ context.Context, _ sdk.MessageNewParams, _ ...option.RequestOption) (*sdk.Message, error) {
	f.calls++
	if f.calls <= f.failures {
		return nil, errors.New("transient")
	}
	return f.ok, nil
}

func TestGenerate_RetriesTransientFailures(t *testing.T) {
	flaky := &flakyCreator{failures: 2, ok: buildMsg("recovered", "claude-opus-4-8", 1, 1)}
	cfg := resilience.Config{
		Retry: resilience.RetryConfig{
			Enabled:      true,
			MaxRetries:   3,
			InitialDelay: time.Millisecond,
			MaxDelay:     2 * time.Millisecond,
		},
	}
	p := newWithCreatorAndPolicies(flaky, "claude-opus-4-8", cfg)

	out, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.NoError(t, err)
	assert.Equal(t, "recovered", out.Text)
	// 2 failures + 1 success = 3 calls. Retry actually triggered.
	assert.Equal(t, 3, flaky.calls)
}

func TestGenerate_RetryExhaustedReturnsError(t *testing.T) {
	flaky := &flakyCreator{failures: 10, ok: buildMsg("never", "m", 0, 0)}
	cfg := resilience.Config{
		Retry: resilience.RetryConfig{
			Enabled:      true,
			MaxRetries:   2,
			InitialDelay: time.Millisecond,
			MaxDelay:     2 * time.Millisecond,
		},
	}
	p := newWithCreatorAndPolicies(flaky, "m", cfg)

	_, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.Error(t, err)
	// initial attempt + 2 retries = 3 calls.
	assert.Equal(t, 3, flaky.calls)
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
		p, err := New(Config{Model: "claude-opus-4-8", APIKey: "k"})
		require.NoError(t, err)
		assert.Equal(t, "anthropic", p.Name())
		// New substitutes DefaultConfig, so the policy stack is non-empty.
		assert.NotEmpty(t, p.policies)
	})
}

// triage mirrors a structured-output target type.
type triage struct {
	Category   string `json:"category"`
	Confidence int    `json:"confidence"`
}

// --- Hermetic httptest end-to-end tests via BaseURL ---

// TestEndToEnd_RequestShapingAndMapping drives a real SDK client at an httptest
// server, asserting the wire request shape and that the response maps back to
// llm.Response correctly. No network, no mock seam.
func TestEndToEnd_RequestShapingAndMapping(t *testing.T) {
	var gotBody map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/v1/messages", r.URL.Path)
		// API key is sent, but the test never logs it; assert it arrived.
		assert.Equal(t, "test-key", r.Header.Get("x-api-key"))

		body, _ := io.ReadAll(r.Body)
		require.NoError(t, json.Unmarshal(body, &gotBody))

		writeMsg(t, w, `{
			"id": "msg_1",
			"type": "message",
			"role": "assistant",
			"model": "claude-opus-4-8",
			"stop_reason": "end_turn",
			"content": [{"type": "text", "text": "diagnosis complete"}],
			"usage": {"input_tokens": 12, "output_tokens": 5}
		}`)
	}))
	defer srv.Close()

	p, err := New(Config{Model: "claude-opus-4-8", APIKey: "test-key", BaseURL: srv.URL})
	require.NoError(t, err)
	// Disable resilience timeout interference by leaving default; the local
	// server responds instantly.

	out, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{
			{Role: llm.RoleSystem, Content: "be terse"},
			{Role: llm.RoleUser, Content: "what broke"},
		},
		MaxTokens: 100,
	})
	require.NoError(t, err)

	// Wire shape: model, max_tokens, system, messages.
	assert.Equal(t, "claude-opus-4-8", gotBody["model"])
	assert.EqualValues(t, 100, gotBody["max_tokens"])
	system := gotBody["system"].([]any)
	require.Len(t, system, 1)
	assert.Equal(t, "be terse", system[0].(map[string]any)["text"])
	msgs := gotBody["messages"].([]any)
	require.Len(t, msgs, 1)
	assert.Equal(t, "user", msgs[0].(map[string]any)["role"])

	// Response decode.
	assert.Equal(t, "diagnosis complete", out.Text)
	assert.Equal(t, "claude-opus-4-8", out.Model)
	assert.Equal(t, "end_turn", out.FinishReason)
	assert.Equal(t, llm.Usage{PromptTokens: 12, CompletionTokens: 5, TotalTokens: 17}, out.Usage)
}

// TestEndToEnd_StructuredOutput verifies the schema is sent as
// output_config.format and that the JSON response decodes into the target type.
func TestEndToEnd_StructuredOutput(t *testing.T) {
	schema, err := llm.SchemaFor[triage]()
	require.NoError(t, err)

	var gotBody map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		require.NoError(t, json.Unmarshal(body, &gotBody))
		writeMsg(t, w, `{
			"id": "msg_2",
			"type": "message",
			"role": "assistant",
			"model": "claude-opus-4-8",
			"stop_reason": "end_turn",
			"content": [{"type": "text", "text": "{\"category\":\"latency\",\"confidence\":80}"}],
			"usage": {"input_tokens": 5, "output_tokens": 4}
		}`)
	}))
	defer srv.Close()

	p, err := New(Config{Model: "claude-opus-4-8", APIKey: "test-key", BaseURL: srv.URL})
	require.NoError(t, err)

	req := llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "triage"}},
	}.WithSchema(schema, "triage")

	out, err := p.Generate(context.Background(), req)
	require.NoError(t, err)

	// output_config.format carries the json_schema constraint with the request
	// schema.
	oc := gotBody["output_config"].(map[string]any)
	format := oc["format"].(map[string]any)
	assert.Equal(t, "json_schema", format["type"])
	gotSchema, err := json.Marshal(format["schema"])
	require.NoError(t, err)
	assert.JSONEq(t, string(schema), string(gotSchema))

	// Caller recovers the typed value from the JSON text.
	var got triage
	require.NoError(t, out.Decode(&got))
	assert.Equal(t, triage{Category: "latency", Confidence: 80}, got)
}

// TestGenerate_TruncatedStructuredOutput is the FIX 3 regression: a
// structured-output request whose response stopped on max_tokens yields partial
// JSON, so Generate must return a terminal error to let the router fall back.
func TestGenerate_TruncatedStructuredOutput(t *testing.T) {
	schema, err := llm.SchemaFor[triage]()
	require.NoError(t, err)

	resp := &sdk.Message{
		Model:      "claude-opus-4-8",
		StopReason: sdk.StopReasonMaxTokens,
		Content:    []sdk.ContentBlockUnion{{Type: "text", Text: `{"category":"lat`}},
		Usage:      sdk.Usage{InputTokens: 5, OutputTokens: 4},
	}
	p := newWithCreator(&mockCreator{resp: resp}, "claude-opus-4-8")

	req := llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "triage"}},
	}.WithSchema(schema, "triage")

	_, err = p.Generate(context.Background(), req)
	require.Error(t, err)
	assert.ErrorContains(t, err, "truncated")
}

// TestGenerate_TruncatedNoSchema verifies the truncation guard is scoped to
// structured-output requests: a plain request that stopped on max_tokens still
// returns its (partial) text without error.
func TestGenerate_TruncatedNoSchema(t *testing.T) {
	resp := &sdk.Message{
		Model:      "claude-opus-4-8",
		StopReason: sdk.StopReasonMaxTokens,
		Content:    []sdk.ContentBlockUnion{{Type: "text", Text: "partial text"}},
		Usage:      sdk.Usage{InputTokens: 5, OutputTokens: 4},
	}
	p := newWithCreator(&mockCreator{resp: resp}, "claude-opus-4-8")

	out, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.NoError(t, err)
	assert.Equal(t, "partial text", out.Text)
	assert.Equal(t, "max_tokens", out.FinishReason)
}

// TestEndToEnd_ErrorPath verifies a non-2xx API response surfaces as an error
// from Generate. A 400 is non-retryable, so the SDK does not loop.
func TestEndToEnd_ErrorPath(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("content-type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_, _ = io.WriteString(w, `{"type":"error","error":{"type":"invalid_request_error","message":"bad model"}}`)
	}))
	defer srv.Close()

	// Construct directly against the SDK client with no resilience policies so a
	// 400 is returned immediately without retry/backoff.
	client := sdk.NewClient(option.WithAPIKey("test-key"), option.WithBaseURL(srv.URL), option.WithMaxRetries(0))
	p := newWithCreator(&client.Messages, "claude-opus-4-8")

	_, err := p.Generate(context.Background(), llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}},
	})
	require.Error(t, err)
	assert.ErrorContains(t, err, "anthropic: create message")
}

// buildMsg constructs an SDK Message with a single text content block, an
// end_turn stop reason, and usage metadata.
func buildMsg(text, model string, in, out int64) *sdk.Message {
	return &sdk.Message{
		Model:      model,
		StopReason: sdk.StopReasonEndTurn,
		Content:    []sdk.ContentBlockUnion{{Type: "text", Text: text}},
		Usage:      sdk.Usage{InputTokens: in, OutputTokens: out},
	}
}

// writeMsg writes a canned Messages API JSON response.
func writeMsg(t *testing.T, w http.ResponseWriter, body string) {
	t.Helper()
	w.Header().Set("content-type", "application/json")
	_, err := io.WriteString(w, body)
	require.NoError(t, err)
}
