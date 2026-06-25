// Package gemini implements the llm.Provider port using Google's unified
// google.golang.org/genai SDK. A single client is created per provider and
// can target either the Gemini API (API-key auth) or Vertex AI (GCP
// project/location) backend, selected by configuration.
//
// Structured output is supported: when an llm.Request carries a JSON schema
// (built via llm.SchemaFor[T] and attached with Request.WithSchema), the
// provider asks the model to emit JSON constrained to that schema and the
// caller recovers the typed value with llm.Response.Decode. No genai types
// leak across the llm.Provider boundary.
package gemini

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/failsafe-go/failsafe-go"
	"google.golang.org/genai"

	"github.com/avivl/cloud-sre-agent/internal/llm"
	"github.com/avivl/cloud-sre-agent/internal/resilience"
)

// providerName is the stable identifier reported by Name and used in logs and
// metrics.
const providerName = "gemini"

// Backend selects which Google backend the underlying genai client targets.
type Backend int

const (
	// BackendGeminiAPI uses the Gemini Developer API with API-key auth.
	BackendGeminiAPI Backend = iota
	// BackendVertexAI uses Vertex AI with GCP project/location auth.
	BackendVertexAI
)

// Config configures a Provider. The model name is required. For
// BackendGeminiAPI, APIKey is required. For BackendVertexAI, Project and
// Location are required and APIKey is ignored.
type Config struct {
	// Model is the default model name (e.g. "gemini-2.5-flash"). A non-empty
	// Request.Model overrides it per call.
	Model string
	// Backend selects Gemini API vs Vertex AI.
	Backend Backend
	// APIKey is the Gemini API key (BackendGeminiAPI only).
	APIKey string
	// Project is the GCP project ID (BackendVertexAI only).
	Project string
	// Location is the GCP region (BackendVertexAI only).
	Location string
	// Resilience configures the retry/circuit-breaker/timeout stack wrapping each
	// generate call. The zero value disables every policy; New substitutes
	// resilience.DefaultConfig when it is left zero so callers get sane retries
	// and a breaker by default.
	Resilience resilience.Config
}

// generator is the seam over genai used for testability: the real client's
// Models service satisfies it, and tests inject a mock returning canned
// responses so no network call is made.
type generator interface {
	GenerateContent(ctx context.Context, model string, contents []*genai.Content, config *genai.GenerateContentConfig) (*genai.GenerateContentResponse, error)
}

// Provider is the genai-backed implementation of llm.Provider.
type Provider struct {
	gen      generator
	model    string
	policies []failsafe.Policy[*genai.GenerateContentResponse]
}

// compile-time assurance the port is satisfied.
var _ llm.Provider = (*Provider)(nil)

// New constructs a Provider with a real genai client built from cfg. It
// returns an error if the configuration is invalid or the client cannot be
// created.
func New(ctx context.Context, cfg Config) (*Provider, error) {
	if cfg.Model == "" {
		return nil, fmt.Errorf("gemini: model is required")
	}

	cc := &genai.ClientConfig{}
	switch cfg.Backend {
	case BackendGeminiAPI:
		if cfg.APIKey == "" {
			return nil, fmt.Errorf("gemini: api key is required for the Gemini API backend")
		}
		cc.Backend = genai.BackendGeminiAPI
		cc.APIKey = cfg.APIKey
	case BackendVertexAI:
		if cfg.Project == "" || cfg.Location == "" {
			return nil, fmt.Errorf("gemini: project and location are required for the Vertex AI backend")
		}
		cc.Backend = genai.BackendVertexAI
		cc.Project = cfg.Project
		cc.Location = cfg.Location
	default:
		return nil, fmt.Errorf("gemini: unknown backend %d", cfg.Backend)
	}

	client, err := genai.NewClient(ctx, cc)
	if err != nil {
		return nil, fmt.Errorf("gemini: create client: %w", err)
	}

	// A zero Resilience config means "unset"; substitute the production-leaning
	// default so callers get retries + a breaker without opting in.
	rc := cfg.Resilience
	if rc == (resilience.Config{}) {
		rc = resilience.DefaultConfig()
	}

	return &Provider{
		gen:      client.Models,
		model:    cfg.Model,
		policies: resilience.Policies[*genai.GenerateContentResponse](rc),
	}, nil
}

// newWithGenerator builds a Provider around an arbitrary generator with no
// resilience policies. It exists for tests, which inject a mock to avoid network
// access.
func newWithGenerator(gen generator, model string) *Provider {
	return &Provider{gen: gen, model: model}
}

// newWithGeneratorAndPolicies builds a Provider around an arbitrary generator
// wrapped by the given resilience policies. It exists for tests that exercise
// the resilience stack (e.g. retry on a flaky mock).
func newWithGeneratorAndPolicies(gen generator, model string, cfg resilience.Config) *Provider {
	return &Provider{
		gen:      gen,
		model:    model,
		policies: resilience.Policies[*genai.GenerateContentResponse](cfg),
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
		return llm.Response{}, fmt.Errorf("gemini: request has no messages")
	}

	model := req.Model
	if model == "" {
		model = p.model
	}

	contents, system, err := toContents(req.Messages)
	if err != nil {
		return llm.Response{}, err
	}

	cfg, err := toConfig(req, system)
	if err != nil {
		return llm.Response{}, err
	}

	// The underlying generate call is wrapped by the resilience stack (retry with
	// backoff, circuit breaker, timeout) so transient provider failures are
	// retried and sustained failures trip the breaker. With no policies this is a
	// single direct call.
	resp, err := resilience.Execute(ctx, p.policies, func(ctx context.Context) (*genai.GenerateContentResponse, error) {
		return p.gen.GenerateContent(ctx, model, contents, cfg)
	})
	if err != nil {
		return llm.Response{}, fmt.Errorf("gemini: generate content: %w", err)
	}
	if resp == nil {
		return llm.Response{}, fmt.Errorf("gemini: nil response from model")
	}

	return toResponse(resp, model), nil
}

// toContents maps llm Messages to genai Contents. A single leading system
// message is extracted into the returned system instruction; user and model
// turns become Contents. An empty system instruction is returned as nil.
func toContents(msgs []llm.Message) (contents []*genai.Content, system *genai.Content, err error) {
	for _, m := range msgs {
		switch m.Role {
		case llm.RoleSystem:
			if system == nil {
				system = genai.NewContentFromText(m.Content, genai.RoleUser)
			} else {
				// Fold additional system messages into the instruction.
				system.Parts = append(system.Parts, genai.NewPartFromText(m.Content))
			}
		case llm.RoleUser:
			contents = append(contents, genai.NewContentFromText(m.Content, genai.RoleUser))
		case llm.RoleModel:
			contents = append(contents, genai.NewContentFromText(m.Content, genai.RoleModel))
		default:
			return nil, nil, fmt.Errorf("gemini: unknown message role %q", m.Role)
		}
	}
	return contents, system, nil
}

// toConfig builds the genai generation config from the request, wiring
// temperature, max tokens, the optional system instruction, and structured
// output when a schema is present.
func toConfig(req llm.Request, system *genai.Content) (*genai.GenerateContentConfig, error) {
	cfg := &genai.GenerateContentConfig{}

	if system != nil {
		cfg.SystemInstruction = system
	}
	if req.Temperature != nil {
		t := float32(*req.Temperature)
		cfg.Temperature = &t
	}
	if req.MaxTokens > 0 {
		cfg.MaxOutputTokens = int32(req.MaxTokens)
	}

	if len(req.Schema) > 0 {
		// Constrain output to the provided JSON schema. genai accepts a raw
		// JSON schema via ResponseJsonSchema; pairing it with a JSON MIME type
		// makes Response.Text valid JSON for that schema.
		var schema any
		if err := json.Unmarshal(req.Schema, &schema); err != nil {
			return nil, fmt.Errorf("gemini: invalid request schema: %w", err)
		}
		cfg.ResponseMIMEType = "application/json"
		cfg.ResponseJsonSchema = schema
	}

	return cfg, nil
}

// toResponse maps a genai response to the provider-agnostic llm.Response.
func toResponse(resp *genai.GenerateContentResponse, model string) llm.Response {
	out := llm.Response{
		Text:  resp.Text(),
		Model: model,
	}
	if resp.ModelVersion != "" {
		out.Model = resp.ModelVersion
	}
	if len(resp.Candidates) > 0 && resp.Candidates[0].FinishReason != "" {
		out.FinishReason = string(resp.Candidates[0].FinishReason)
	}
	if u := resp.UsageMetadata; u != nil {
		out.Usage = llm.Usage{
			PromptTokens:     int(u.PromptTokenCount),
			CompletionTokens: int(u.CandidatesTokenCount),
			TotalTokens:      int(u.TotalTokenCount),
		}
	}
	return out
}
