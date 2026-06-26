// Package anthropic implements the llm.Provider port using Anthropic's official
// github.com/anthropics/anthropic-sdk-go SDK. A single client is created per
// provider and targets the Messages API with API-key auth; an optional BaseURL
// is a test seam for pointing at an httptest server.
//
// Structured output is supported: when an llm.Request carries a JSON schema
// (built via llm.SchemaFor[T] and attached with Request.WithSchema), the
// provider sets output_config.format to a json_schema constraint so the model
// emits JSON valid for that schema, and the caller recovers the typed value
// with llm.Response.Decode. No anthropic SDK types leak across the llm.Provider
// boundary.
//
// Error handling note for callers: errors returned by this adapter are
// content-free. However, errors that originate inside the anthropic-sdk-go SDK
// and are wrapped here (e.g. "anthropic: create message: ...") may embed
// request/response snippets from the wire. Callers MUST sanitize adapter errors
// before logging them under HIPAA, since prompt content can include log data.
package anthropic

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/anthropics/anthropic-sdk-go"
	"github.com/anthropics/anthropic-sdk-go/option"
	"github.com/failsafe-go/failsafe-go"

	"github.com/avivl/cloud-sre-agent/internal/llm"
	"github.com/avivl/cloud-sre-agent/internal/resilience"
)

// providerName is the stable identifier reported by Name and used in logs and
// metrics.
const providerName = "anthropic"

// defaultMaxTokens caps response length when a Request leaves MaxTokens unset.
// The Messages API requires max_tokens, so a sane default is always supplied.
const defaultMaxTokens = 4096

// Config configures a Provider. Model and APIKey are required. BaseURL is an
// optional override of the API host (used by tests to point at an httptest
// server); empty means the SDK default.
type Config struct {
	// Model is the default model name (e.g. "claude-opus-4-8"). A non-empty
	// Request.Model overrides it per call.
	Model string
	// APIKey is the Anthropic API key. Required. Never logged.
	APIKey string
	// BaseURL optionally overrides the API host. Empty uses the SDK default.
	BaseURL string
	// Resilience configures the retry/circuit-breaker/timeout stack wrapping each
	// generate call. The zero value disables every policy; New substitutes
	// resilience.DefaultConfig when it is left zero so callers get sane retries
	// and a breaker by default.
	Resilience resilience.Config
}

// creator is the seam over the SDK used for testability: the real client's
// Messages service satisfies it, and tests inject a mock returning canned
// responses so no network call is made.
type creator interface {
	New(ctx context.Context, params anthropic.MessageNewParams, opts ...option.RequestOption) (*anthropic.Message, error)
}

// Provider is the anthropic-sdk-go-backed implementation of llm.Provider.
type Provider struct {
	gen      creator
	model    string
	policies []failsafe.Policy[*anthropic.Message]
}

// compile-time assurance the port is satisfied.
var _ llm.Provider = (*Provider)(nil)

// New constructs a Provider with a real anthropic client built from cfg. It
// returns an error if the configuration is invalid.
func New(cfg Config) (*Provider, error) {
	if cfg.Model == "" {
		return nil, fmt.Errorf("anthropic: model is required")
	}
	if cfg.APIKey == "" {
		return nil, fmt.Errorf("anthropic: api key is required")
	}

	opts := []option.RequestOption{option.WithAPIKey(cfg.APIKey)}
	if cfg.BaseURL != "" {
		opts = append(opts, option.WithBaseURL(cfg.BaseURL))
	}
	client := anthropic.NewClient(opts...)

	// A zero Resilience config means "unset"; substitute the production-leaning
	// default so callers get retries + a breaker without opting in.
	rc := cfg.Resilience
	if rc == (resilience.Config{}) {
		rc = resilience.DefaultConfig()
	}

	return &Provider{
		gen:      &client.Messages,
		model:    cfg.Model,
		policies: resilience.Policies[*anthropic.Message](rc),
	}, nil
}

// newWithCreator builds a Provider around an arbitrary creator with no
// resilience policies. It exists for tests, which inject a mock to avoid network
// access.
func newWithCreator(gen creator, model string) *Provider {
	return &Provider{gen: gen, model: model}
}

// newWithCreatorAndPolicies builds a Provider around an arbitrary creator
// wrapped by the given resilience policies. It exists for tests that exercise
// the resilience stack (e.g. retry on a flaky mock).
func newWithCreatorAndPolicies(gen creator, model string, cfg resilience.Config) *Provider {
	return &Provider{
		gen:      gen,
		model:    model,
		policies: resilience.Policies[*anthropic.Message](cfg),
	}
}

// Name reports the provider identifier.
func (p *Provider) Name() string { return providerName }

// Generate sends req to the model and returns the provider-agnostic Response.
// When req.Schema is set the model is constrained to emit JSON matching that
// schema, so Response.Text is valid JSON the caller can Decode into the
// originating Go type.
func (p *Provider) Generate(ctx context.Context, req llm.Request) (llm.Response, error) {
	if len(req.Messages) == 0 {
		return llm.Response{}, fmt.Errorf("anthropic: request has no messages")
	}

	model := req.Model
	if model == "" {
		model = p.model
	}

	params, err := toParams(req, model)
	if err != nil {
		return llm.Response{}, err
	}

	// The underlying create call is wrapped by the resilience stack (retry with
	// backoff, circuit breaker, timeout) so transient provider failures are
	// retried and sustained failures trip the breaker. With no policies this is a
	// single direct call.
	resp, err := resilience.Execute(ctx, p.policies, func(ctx context.Context) (*anthropic.Message, error) {
		return p.gen.New(ctx, params)
	})
	if err != nil {
		return llm.Response{}, fmt.Errorf("anthropic: create message: %w", err)
	}
	if resp == nil {
		return llm.Response{}, fmt.Errorf("anthropic: nil response from model")
	}

	// A structured-output response cut short by the token limit yields invalid
	// (partial) JSON; surface it as a terminal error so the fallback router
	// advances rather than returning unparseable text with a nil error.
	if len(req.Schema) > 0 && resp.StopReason == anthropic.StopReasonMaxTokens {
		return llm.Response{}, fmt.Errorf("anthropic: response truncated (max_tokens) before structured output completed")
	}

	return toResponse(resp, model), nil
}

// toParams builds the SDK request from the llm.Request. A leading or interleaved
// system message is folded into the top-level System field (the Messages API
// has no system role in messages); user and model turns become MessageParams.
// Structured output is wired via output_config.format when a schema is present.
func toParams(req llm.Request, model string) (anthropic.MessageNewParams, error) {
	params := anthropic.MessageNewParams{
		Model:     model,
		MaxTokens: defaultMaxTokens,
	}
	if req.MaxTokens > 0 {
		params.MaxTokens = int64(req.MaxTokens)
	}
	if req.Temperature != nil {
		params.Temperature = anthropic.Float(*req.Temperature)
	}

	for _, m := range req.Messages {
		switch m.Role {
		case llm.RoleSystem:
			params.System = append(params.System, anthropic.TextBlockParam{Text: m.Content})
		case llm.RoleUser:
			params.Messages = append(params.Messages, anthropic.NewUserMessage(anthropic.NewTextBlock(m.Content)))
		case llm.RoleModel:
			params.Messages = append(params.Messages, anthropic.NewAssistantMessage(anthropic.NewTextBlock(m.Content)))
		default:
			return anthropic.MessageNewParams{}, fmt.Errorf("anthropic: unknown message role %q", m.Role)
		}
	}

	if len(req.Schema) > 0 {
		// Constrain output to the provided JSON schema. The SDK accepts a raw
		// JSON schema as a map under output_config.format; pairing it with the
		// json_schema format type makes Response.Text valid JSON for that schema.
		var schema map[string]any
		if err := json.Unmarshal(req.Schema, &schema); err != nil {
			return anthropic.MessageNewParams{}, fmt.Errorf("anthropic: invalid request schema: %w", err)
		}
		params.OutputConfig = anthropic.OutputConfigParam{
			Format: anthropic.JSONOutputFormatParam{Schema: schema},
		}
	}

	return params, nil
}

// toResponse maps an SDK Message to the provider-agnostic llm.Response. Text is
// the concatenation of all text content blocks; thinking and tool-use blocks
// are ignored.
func toResponse(resp *anthropic.Message, model string) llm.Response {
	out := llm.Response{Model: model}
	if resp.Model != "" {
		out.Model = resp.Model
	}

	var text string
	for _, block := range resp.Content {
		if block.Type == "text" {
			text += block.Text
		}
	}
	out.Text = text

	if resp.StopReason != "" {
		out.FinishReason = string(resp.StopReason)
	}

	out.Usage = llm.Usage{
		PromptTokens:     int(resp.Usage.InputTokens),
		CompletionTokens: int(resp.Usage.OutputTokens),
		TotalTokens:      int(resp.Usage.InputTokens + resp.Usage.OutputTokens),
	}

	return out
}
