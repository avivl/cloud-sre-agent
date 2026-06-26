package router

import (
	"context"
	"errors"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/avivl/cloud-sre-agent/internal/llm"
)

// stubProvider is an in-package llm.Provider whose behavior is fully scripted:
// it returns the canned resp/err and records how many times Generate was
// called, so tests can assert which providers in the chain were exercised.
type stubProvider struct {
	name  string
	resp  llm.Response
	err   error
	calls int
}

func (s *stubProvider) Name() string { return s.name }

func (s *stubProvider) Generate(_ context.Context, _ llm.Request) (llm.Response, error) {
	s.calls++
	return s.resp, s.err
}

func TestNew_RequiresPrimary(t *testing.T) {
	_, err := New(nil)
	require.Error(t, err)
}

func TestNew_RejectsNilFallback(t *testing.T) {
	primary := &stubProvider{name: "gemini"}
	_, err := New(primary, nil)
	require.Error(t, err)
}

func TestName_ReportsActiveSet(t *testing.T) {
	r, err := New(
		&stubProvider{name: "gemini"},
		&stubProvider{name: "openai"},
		&stubProvider{name: "anthropic"},
	)
	require.NoError(t, err)
	assert.Equal(t, "router[gemini->openai->anthropic]", r.Name())
}

// (a) primary succeeds -> fallback is never called.
func TestGenerate_PrimarySuccess_FallbackNotCalled(t *testing.T) {
	primary := &stubProvider{name: "gemini", resp: llm.Response{Text: "ok", Model: "gemini-2.5-flash"}}
	fallback := &stubProvider{name: "openai"}

	r, err := New(primary, fallback)
	require.NoError(t, err)

	resp, err := r.Generate(context.Background(), llm.Request{})
	require.NoError(t, err)
	assert.Equal(t, "ok", resp.Text)
	assert.Equal(t, 1, primary.calls)
	assert.Equal(t, 0, fallback.calls, "fallback must not be called when primary succeeds")
}

// (b) primary errors -> fallback is used and its result is returned.
func TestGenerate_PrimaryFails_FallbackUsed(t *testing.T) {
	primary := &stubProvider{name: "gemini", err: errors.New("boom")}
	fallback := &stubProvider{name: "openai", resp: llm.Response{Text: "rescued", Model: "gpt-5"}}

	r, err := New(primary, fallback)
	require.NoError(t, err)

	resp, err := r.Generate(context.Background(), llm.Request{})
	require.NoError(t, err)
	assert.Equal(t, "rescued", resp.Text)
	assert.Equal(t, 1, primary.calls)
	assert.Equal(t, 1, fallback.calls)
}

// (c) all providers error -> aggregated error mentions each provider.
func TestGenerate_AllFail_AggregatedError(t *testing.T) {
	primary := &stubProvider{name: "gemini", err: errors.New("gemini down")}
	fb1 := &stubProvider{name: "openai", err: errors.New("openai 429")}
	fb2 := &stubProvider{name: "anthropic", err: errors.New("anthropic 500")}

	r, err := New(primary, fb1, fb2)
	require.NoError(t, err)

	resp, err := r.Generate(context.Background(), llm.Request{})
	require.Error(t, err)
	assert.Equal(t, llm.Response{}, resp)

	msg := err.Error()
	// Each provider name and its underlying failure must surface.
	assert.Contains(t, msg, "gemini")
	assert.Contains(t, msg, "gemini down")
	assert.Contains(t, msg, "openai")
	assert.Contains(t, msg, "openai 429")
	assert.Contains(t, msg, "anthropic")
	assert.Contains(t, msg, "anthropic 500")

	// The aggregated error must unwrap to each underlying cause (errors.Join).
	assert.True(t, errors.Is(err, primary.err))
	assert.True(t, errors.Is(err, fb1.err))
	assert.True(t, errors.Is(err, fb2.err))

	assert.Equal(t, 1, primary.calls)
	assert.Equal(t, 1, fb1.calls)
	assert.Equal(t, 1, fb2.calls)
}

// A cancelled context short-circuits the chain before invoking any provider.
func TestGenerate_ContextCancelled(t *testing.T) {
	primary := &stubProvider{name: "gemini"}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	r, err := New(primary)
	require.NoError(t, err)

	_, err = r.Generate(ctx, llm.Request{})
	require.Error(t, err)
	assert.True(t, errors.Is(err, context.Canceled))
	assert.Equal(t, 0, primary.calls, "no provider should be called once ctx is done")
}
