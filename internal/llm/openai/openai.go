// Package openai implements the llm.Provider port using OpenAI's official
// github.com/openai/openai-go/v3 SDK. A single client is created per provider
// and targets the Chat Completions endpoint. An optional BaseURL redirects the
// client at an alternate host (e.g. an Azure/compatible gateway, or an
// httptest server in tests), which is the seam hermetic tests use to avoid the
// network.
//
// Structured output is supported: when an llm.Request carries a JSON schema
// (built via llm.SchemaFor[T] and attached with Request.WithSchema), the
// provider sets response_format to a strict json_schema so the model emits
// JSON constrained to that schema, and the caller recovers the typed value with
// llm.Response.Decode. No openai-go types leak across the llm.Provider
// boundary. The API key is never logged.
//
// Error handling note for callers: errors returned by this adapter are
// deliberately content-free (no prompt text, no API key, no model refusal
// text). However, errors that originate inside the openai-go SDK and are
// wrapped here (e.g. "openai: chat completion: ...") may embed request/response
// snippets from the wire. Callers MUST sanitize adapter errors before logging
// them under HIPAA, since prompt content can include log data.
package openai

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"

	oai "github.com/openai/openai-go/v3"
	"github.com/openai/openai-go/v3/option"
	"github.com/openai/openai-go/v3/packages/param"
	"github.com/openai/openai-go/v3/shared"
	"github.com/openai/openai-go/v3/shared/constant"

	"github.com/avivl/cloud-sre-agent/internal/llm"
)

// providerName is the stable identifier reported by Name and used in logs and
// metrics.
const providerName = "openai"

// defaultSchemaName is the json_schema name used when a Request supplies a
// schema but no (or an empty-after-sanitizing) name. It is a safe literal that
// already satisfies OpenAI's name constraint.
const defaultSchemaName = "response"

// finishReasonLength is the OpenAI finish_reason indicating the response was
// cut off by the token limit before completing.
const finishReasonLength = "length"

// schemaNameInvalid matches characters OpenAI disallows in a json_schema name.
// The permitted set is ^[a-zA-Z0-9_-]{1,64}$; invalid runs are replaced with
// '_' and the result is truncated to 64 characters.
var schemaNameInvalid = regexp.MustCompile(`[^a-zA-Z0-9_-]`)

// sanitizeSchemaName coerces an arbitrary schema name into OpenAI's required
// ^[a-zA-Z0-9_-]{1,64}$ form: invalid characters become '_', the result is
// truncated to 64 characters, and an empty name defaults to defaultSchemaName.
func sanitizeSchemaName(name string) string {
	if name == "" {
		return defaultSchemaName
	}
	cleaned := schemaNameInvalid.ReplaceAllString(name, "_")
	if len(cleaned) > 64 {
		cleaned = cleaned[:64]
	}
	if cleaned == "" {
		return defaultSchemaName
	}
	return cleaned
}

// Config configures a Provider. Model and APIKey are required; BaseURL is
// optional.
type Config struct {
	// Model is the default model name (e.g. "gpt-4o-mini"). A non-empty
	// Request.Model overrides it per call.
	Model string
	// APIKey is the OpenAI API key. It is passed to the SDK and never logged.
	APIKey string
	// BaseURL optionally overrides the API host. Empty uses OpenAI's default.
	// Tests point this at an httptest server.
	BaseURL string
}

// chatCompleter is the seam over the openai-go Chat Completions service used
// for testability. The real client's Chat.Completions satisfies it; it is also
// what New builds. Hermetic tests construct a Provider whose client targets an
// httptest server via Config.BaseURL.
type chatCompleter interface {
	New(ctx context.Context, body oai.ChatCompletionNewParams, opts ...option.RequestOption) (*oai.ChatCompletion, error)
}

// Provider is the openai-go-backed implementation of llm.Provider.
type Provider struct {
	chat  chatCompleter
	model string
}

// compile-time assurance the port is satisfied.
var _ llm.Provider = (*Provider)(nil)

// New constructs a Provider with a real openai-go client built from cfg. It
// returns an error if the configuration is invalid.
func New(cfg Config) (*Provider, error) {
	if cfg.Model == "" {
		return nil, fmt.Errorf("openai: model is required")
	}
	if cfg.APIKey == "" {
		return nil, fmt.Errorf("openai: api key is required")
	}

	opts := []option.RequestOption{option.WithAPIKey(cfg.APIKey)}
	if cfg.BaseURL != "" {
		opts = append(opts, option.WithBaseURL(cfg.BaseURL))
	}

	client := oai.NewClient(opts...)
	return &Provider{chat: &client.Chat.Completions, model: cfg.Model}, nil
}

// newWithCompleter builds a Provider around an arbitrary chatCompleter. It
// exists for tests that inject a mock instead of an HTTP-backed client.
func newWithCompleter(chat chatCompleter, model string) *Provider {
	return &Provider{chat: chat, model: model}
}

// Name reports the provider identifier.
func (p *Provider) Name() string { return providerName }

// Generate sends req to the model and returns the provider-agnostic Response.
// When req.Schema is set the model is constrained to emit JSON matching that
// schema (strict json_schema response_format), so Response.Text is valid JSON
// the caller can Decode into the originating Go type.
func (p *Provider) Generate(ctx context.Context, req llm.Request) (llm.Response, error) {
	if len(req.Messages) == 0 {
		return llm.Response{}, fmt.Errorf("openai: request has no messages")
	}

	model := req.Model
	if model == "" {
		model = p.model
	}

	params, err := toParams(req, model)
	if err != nil {
		return llm.Response{}, err
	}

	resp, err := p.chat.New(ctx, params)
	if err != nil {
		return llm.Response{}, fmt.Errorf("openai: chat completion: %w", err)
	}
	if resp == nil || len(resp.Choices) == 0 {
		return llm.Response{}, fmt.Errorf("openai: response has no choices")
	}

	return toResponse(resp, model, len(req.Schema) > 0)
}

// toParams maps an llm.Request to openai-go Chat Completions params, wiring
// messages, sampling controls, and structured output when a schema is present.
func toParams(req llm.Request, model string) (oai.ChatCompletionNewParams, error) {
	msgs, err := toMessages(req.Messages)
	if err != nil {
		return oai.ChatCompletionNewParams{}, err
	}

	params := oai.ChatCompletionNewParams{
		Model:    model,
		Messages: msgs,
	}
	if req.Temperature != nil {
		params.Temperature = param.NewOpt(*req.Temperature)
	}
	if req.MaxTokens > 0 {
		params.MaxCompletionTokens = param.NewOpt(int64(req.MaxTokens))
	}

	if len(req.Schema) > 0 {
		// Constrain output to the provided JSON schema via a strict json_schema
		// response_format, so Response.Text is valid JSON for that schema.
		var schema any
		if err := json.Unmarshal(req.Schema, &schema); err != nil {
			return oai.ChatCompletionNewParams{}, fmt.Errorf("openai: invalid request schema: %w", err)
		}
		// OpenAI requires the json_schema name to match ^[a-zA-Z0-9_-]{1,64}$;
		// sanitize so an arbitrary caller-supplied name never causes a 400.
		name := sanitizeSchemaName(req.SchemaName)
		params.ResponseFormat = oai.ChatCompletionNewParamsResponseFormatUnion{
			OfJSONSchema: &shared.ResponseFormatJSONSchemaParam{
				Type: constant.JSONSchema("json_schema"),
				JSONSchema: shared.ResponseFormatJSONSchemaJSONSchemaParam{
					Name:   name,
					Strict: param.NewOpt(true),
					Schema: schema,
				},
			},
		}
	}

	return params, nil
}

// toMessages maps llm Messages to openai-go chat messages. System turns become
// system messages; user turns user messages; model turns assistant messages.
func toMessages(msgs []llm.Message) ([]oai.ChatCompletionMessageParamUnion, error) {
	out := make([]oai.ChatCompletionMessageParamUnion, 0, len(msgs))
	for _, m := range msgs {
		switch m.Role {
		case llm.RoleSystem:
			out = append(out, oai.SystemMessage(m.Content))
		case llm.RoleUser:
			out = append(out, oai.UserMessage(m.Content))
		case llm.RoleModel:
			out = append(out, oai.AssistantMessage(m.Content))
		default:
			return nil, fmt.Errorf("openai: unknown message role %q", m.Role)
		}
	}
	return out, nil
}

// toResponse maps an openai-go ChatCompletion to the provider-agnostic
// llm.Response, reading the first choice's text, finish reason, and usage. It
// returns a terminal error (so the fallback router can advance) when the model
// refused the request, or when a structured-output request (hasSchema) was
// truncated by the token limit before the JSON could complete. The returned
// errors are content-free: no prompt, no key, no refusal text.
func toResponse(resp *oai.ChatCompletion, model string, hasSchema bool) (llm.Response, error) {
	choice := resp.Choices[0]
	msg := choice.Message

	// A refusal carries no usable content; surface it as an error (without
	// echoing the refusal text) so the router can fall back.
	if msg.Content == "" && msg.Refusal != "" {
		return llm.Response{}, fmt.Errorf("openai: model refused the request")
	}

	// A structured-output response cut short by the token limit yields invalid
	// (partial) JSON; surface it as a terminal error so the router advances
	// rather than returning unparseable text with a nil error.
	if hasSchema && choice.FinishReason == finishReasonLength {
		return llm.Response{}, fmt.Errorf("openai: response truncated (length) before structured output completed")
	}

	out := llm.Response{
		Text:  msg.Content,
		Model: model,
	}
	if resp.Model != "" {
		out.Model = resp.Model
	}
	out.FinishReason = choice.FinishReason
	out.Usage = llm.Usage{
		PromptTokens:     int(resp.Usage.PromptTokens),
		CompletionTokens: int(resp.Usage.CompletionTokens),
		TotalTokens:      int(resp.Usage.TotalTokens),
	}
	return out, nil
}
