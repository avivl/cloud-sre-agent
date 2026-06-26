// Package ollama implements the llm.Provider port using Ollama's official
// github.com/ollama/ollama/api client. A single client is created per provider
// and targets the /api/chat endpoint with streaming disabled, so each Generate
// is one request/response round-trip. The Host (base URL) is the seam hermetic
// tests use to point the client at an httptest server instead of a real Ollama
// daemon.
//
// Ollama is LOCAL / self-hosted: the model runs on infrastructure the operator
// controls (default http://localhost:11434), so prompt content is NOT disclosed
// to an external third party. Unlike the OpenAI/Anthropic adapters it requires
// no API key, and unlike them it is exempt from the external-disclosure (BAA)
// gate in config validation.
//
// Structured output is supported: when an llm.Request carries a JSON schema
// (built via llm.SchemaFor[T] and attached with Request.WithSchema), the
// provider sets the chat request's Format to that schema so the model emits
// JSON constrained to it, and the caller recovers the typed value with
// llm.Response.Decode — parity with the gemini/openai/anthropic adapters. No
// ollama/api types leak across the llm.Provider boundary.
//
// HIPAA: this adapter never logs prompt or response content. Errors it returns
// are content-free, but errors wrapped from the underlying ollama/api client
// may embed server response snippets; callers MUST sanitize adapter errors
// before logging them.
package ollama

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"

	"github.com/ollama/ollama/api"

	"github.com/avivl/cloud-sre-agent/internal/llm"
)

// providerName is the stable identifier reported by Name and used in logs and
// metrics.
const providerName = "ollama"

// defaultHost is the Ollama daemon's default address when Config.Host is empty.
const defaultHost = "http://localhost:11434"

// chatClient is the seam over the ollama/api Chat call used for testability.
// The real *api.Client satisfies it; hermetic tests either build a real client
// pointed at an httptest server (via Config.Host) or inject a mock directly.
type chatClient interface {
	Chat(ctx context.Context, req *api.ChatRequest, fn api.ChatResponseFunc) error
}

// Config configures a Provider. Model is required; Host defaults to
// defaultHost when empty. There is no API key — Ollama is local.
type Config struct {
	// Model is the default model name (e.g. "llama3.1"). A non-empty
	// Request.Model overrides it per call.
	Model string
	// Host is the Ollama daemon base URL. Empty uses defaultHost. Tests point
	// this at an httptest server.
	Host string
}

// Provider is the ollama/api-backed implementation of llm.Provider.
type Provider struct {
	client chatClient
	model  string
}

// compile-time assurance the port is satisfied.
var _ llm.Provider = (*Provider)(nil)

// New constructs a Provider with a real ollama/api client built from cfg. It
// returns an error if the configuration is invalid or the host is unparseable.
func New(cfg Config) (*Provider, error) {
	if cfg.Model == "" {
		return nil, fmt.Errorf("ollama: model is required")
	}
	host := cfg.Host
	if host == "" {
		host = defaultHost
	}
	base, err := url.Parse(host)
	if err != nil {
		return nil, fmt.Errorf("ollama: invalid host %q: %w", host, err)
	}

	client := api.NewClient(base, http.DefaultClient)
	return &Provider{client: client, model: cfg.Model}, nil
}

// newWithClient builds a Provider around an arbitrary chatClient. It exists for
// tests that inject a mock instead of an HTTP-backed client.
func newWithClient(client chatClient, model string) *Provider {
	return &Provider{client: client, model: model}
}

// Name reports the provider identifier.
func (p *Provider) Name() string { return providerName }

// Generate sends req to the model and returns the provider-agnostic Response.
// Streaming is disabled, so the underlying client invokes the callback once
// with the complete response. When req.Schema is set the model is constrained
// to emit JSON matching that schema (via the chat request's Format), so
// Response.Text is valid JSON the caller can Decode into the originating Go
// type.
func (p *Provider) Generate(ctx context.Context, req llm.Request) (llm.Response, error) {
	if len(req.Messages) == 0 {
		return llm.Response{}, fmt.Errorf("ollama: request has no messages")
	}

	model := req.Model
	if model == "" {
		model = p.model
	}

	chatReq, err := toChatRequest(req, model)
	if err != nil {
		return llm.Response{}, err
	}

	// Stream is disabled, so fn fires exactly once with the final response; we
	// capture it here.
	var final api.ChatResponse
	var got bool
	fn := func(resp api.ChatResponse) error {
		final = resp
		got = true
		return nil
	}

	if err := p.client.Chat(ctx, chatReq, fn); err != nil {
		return llm.Response{}, fmt.Errorf("ollama: chat: %w", err)
	}
	if !got {
		return llm.Response{}, fmt.Errorf("ollama: no response received")
	}

	// For a structured-output request, a truncated or empty completion yields
	// unparseable JSON. Surface it as a terminal error so the fallback router
	// advances rather than committing to an undecodable success (parity with
	// the openai/anthropic adapters).
	if len(req.Schema) > 0 {
		if final.DoneReason == "length" {
			return llm.Response{}, fmt.Errorf("ollama: response truncated (length) before structured output completed")
		}
		if final.Message.Content == "" {
			return llm.Response{}, fmt.Errorf("ollama: empty response for structured-output request")
		}
	}

	return toResponse(final, model), nil
}

// toChatRequest maps an llm.Request to an ollama/api ChatRequest, wiring
// messages, sampling controls, structured output (Format), and disabling
// streaming so the response arrives in a single callback.
func toChatRequest(req llm.Request, model string) (*api.ChatRequest, error) {
	msgs, err := toMessages(req.Messages)
	if err != nil {
		return nil, err
	}

	stream := false
	chatReq := &api.ChatRequest{
		Model:    model,
		Messages: msgs,
		Stream:   &stream,
	}

	opts := map[string]any{}
	if req.Temperature != nil {
		opts["temperature"] = *req.Temperature
	}
	if req.MaxTokens > 0 {
		opts["num_predict"] = req.MaxTokens
	}
	if len(opts) > 0 {
		chatReq.Options = opts
	}

	if len(req.Schema) > 0 {
		// Constrain output to the provided JSON schema. Ollama accepts a JSON
		// schema as the chat request's Format, so Response.Text is valid JSON
		// for that schema. Validate it is well-formed JSON first.
		if !json.Valid(req.Schema) {
			return nil, fmt.Errorf("ollama: invalid request schema: not valid JSON")
		}
		chatReq.Format = req.Schema
	}

	return chatReq, nil
}

// toMessages maps llm Messages to ollama/api chat messages. System turns become
// system messages; user turns user messages; model turns assistant messages.
func toMessages(msgs []llm.Message) ([]api.Message, error) {
	out := make([]api.Message, 0, len(msgs))
	for _, m := range msgs {
		var role string
		switch m.Role {
		case llm.RoleSystem:
			role = "system"
		case llm.RoleUser:
			role = "user"
		case llm.RoleModel:
			role = "assistant"
		default:
			return nil, fmt.Errorf("ollama: unknown message role %q", m.Role)
		}
		out = append(out, api.Message{Role: role, Content: m.Content})
	}
	return out, nil
}

// toResponse maps an ollama/api ChatResponse to the provider-agnostic
// llm.Response, reading the message content, done reason, and token metrics.
// The returned value is content-free in its non-Text fields.
func toResponse(resp api.ChatResponse, model string) llm.Response {
	out := llm.Response{
		Text:         resp.Message.Content,
		Model:        model,
		FinishReason: resp.DoneReason,
	}
	if resp.Model != "" {
		out.Model = resp.Model
	}
	out.Usage = llm.Usage{
		PromptTokens:     resp.PromptEvalCount,
		CompletionTokens: resp.EvalCount,
		TotalTokens:      resp.PromptEvalCount + resp.EvalCount,
	}
	return out
}
