// Package llm defines the Provider port: the provider-agnostic seam for
// generating completions from a large language model. Adapters (Gemini,
// OpenAI, Anthropic, Ollama, ...) implement Provider; the core depends only
// on this interface and the Request/Response value types.
package llm

import (
	"context"
	"encoding/json"
	"fmt"
)

// Role identifies the author of a Message.
type Role string

// Conversation roles.
const (
	RoleSystem Role = "system"
	RoleUser   Role = "user"
	RoleModel  Role = "model"
)

// Message is one turn in a prompt.
type Message struct {
	Role    Role   `json:"role"`
	Content string `json:"content"`
}

// Request is a provider-agnostic generation request. When Schema is non-nil
// the provider must constrain output to that JSON schema (structured output);
// the resulting Response.Text is then valid JSON for that schema.
type Request struct {
	// Model optionally overrides the adapter's default model.
	Model string `json:"model,omitempty"`
	// Messages is the ordered prompt. A single system message may precede
	// user/model turns.
	Messages []Message `json:"messages"`
	// Temperature controls sampling randomness; nil uses the provider default.
	Temperature *float64 `json:"temperature,omitempty"`
	// MaxTokens caps the response length; 0 uses the provider default.
	MaxTokens int `json:"max_tokens,omitempty"`
	// Schema, when set, requests JSON-schema-constrained structured output.
	// Build it with NewSchemaFor[T]. SchemaName labels the schema for
	// providers that require a name.
	Schema     json.RawMessage `json:"schema,omitempty"`
	SchemaName string          `json:"schema_name,omitempty"`
}

// WithSchema sets a JSON schema and name on the request and returns it, for
// fluent construction.
func (r Request) WithSchema(schema json.RawMessage, name string) Request {
	r.Schema = schema
	r.SchemaName = name
	return r
}

// Usage reports token accounting for a generation, when the provider supplies
// it.
type Usage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// Response is the provider-agnostic generation result. Text is the raw model
// output (valid JSON when the Request carried a Schema). Decode unmarshals it
// into a target struct.
type Response struct {
	Text         string `json:"text"`
	Model        string `json:"model"`
	FinishReason string `json:"finish_reason,omitempty"`
	Usage        Usage  `json:"usage"`
}

// Decode unmarshals the response text into v. Use it with structured-output
// requests to recover a typed result.
func (r Response) Decode(v any) error {
	if r.Text == "" {
		return fmt.Errorf("llm: empty response text, cannot decode")
	}
	if err := json.Unmarshal([]byte(r.Text), v); err != nil {
		return fmt.Errorf("llm: decode response into %T: %w", v, err)
	}
	return nil
}

// Provider generates completions from an LLM. Implementations must honor
// ctx cancellation and return a non-nil error on failure.
type Provider interface {
	// Name identifies the provider (e.g. "gemini") for logs and metrics.
	Name() string

	// Generate produces a Response for the given Request.
	Generate(ctx context.Context, req Request) (Response, error)
}
