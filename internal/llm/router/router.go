// Package router implements an llm.Provider that fans a generation request
// across an ordered list of backing providers: the primary first, then
// fallbacks. Generate tries each provider in turn and returns the first
// success; if every provider fails it returns an aggregated error naming each
// failure. The router depends only on the llm.Provider port and the standard
// library, so it composes any mix of adapters (Gemini, OpenAI, Anthropic, ...)
// without coupling to their SDKs.
package router

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/avivl/cloud-sre-agent/internal/llm"
)

// Router is an llm.Provider that delegates to an ordered set of providers,
// advancing to the next on a terminal error from the current one.
type Router struct {
	providers []llm.Provider
}

// compile-time assurance the port is satisfied.
var _ llm.Provider = (*Router)(nil)

// New builds a Router from an ordered list of providers: primary first,
// followed by fallbacks tried in order. It returns an error if no providers
// are supplied or any provider is nil.
func New(primary llm.Provider, fallbacks ...llm.Provider) (*Router, error) {
	if primary == nil {
		return nil, fmt.Errorf("router: primary provider is required")
	}
	providers := make([]llm.Provider, 0, 1+len(fallbacks))
	providers = append(providers, primary)
	for i, fb := range fallbacks {
		if fb == nil {
			return nil, fmt.Errorf("router: fallback provider %d is nil", i)
		}
		providers = append(providers, fb)
	}
	return &Router{providers: providers}, nil
}

// Name reports the active provider set, e.g. "router[gemini->openai]".
func (r *Router) Name() string {
	names := make([]string, len(r.providers))
	for i, p := range r.providers {
		names[i] = p.Name()
	}
	return "router[" + strings.Join(names, "->") + "]"
}

// Generate tries each provider in order, returning the first successful
// Response. If a provider errors, the router advances to the next. When every
// provider fails, it returns an aggregated error (via errors.Join) naming each
// provider's failure. Context cancellation is honored between attempts so a
// cancelled caller does not keep retrying down the chain.
func (r *Router) Generate(ctx context.Context, req llm.Request) (llm.Response, error) {
	var errs []error
	for _, p := range r.providers {
		if err := ctx.Err(); err != nil {
			errs = append(errs, fmt.Errorf("router: context done before %s: %w", p.Name(), err))
			return llm.Response{}, errors.Join(errs...)
		}
		resp, err := p.Generate(ctx, req)
		if err == nil {
			return resp, nil
		}
		errs = append(errs, fmt.Errorf("%s: %w", p.Name(), err))
	}
	return llm.Response{}, fmt.Errorf("router: all providers failed: %w", errors.Join(errs...))
}
