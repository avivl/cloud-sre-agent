// Package resilience provides composable, config-driven failsafe-go policy
// builders (retry, circuit breaker, rate limiter, timeout) and a typed
// Execute helper so callers — notably the Gemini LLM provider — can wrap a
// fallible operation with a layered resilience stack without touching
// failsafe-go directly.
//
// Policies compose outermost-first: Policies(cfg) returns them in the order
// [rate limiter, circuit breaker, retry, timeout], which failsafe-go applies
// as RateLimiter(CircuitBreaker(Retry(Timeout(fn)))). The timeout is innermost
// so it bounds each attempt, retry wraps it so each retry gets a fresh timeout,
// the breaker observes the aggregate (post-retry) outcome, and the rate limiter
// throttles entry.
package resilience

import (
	"context"
	"time"

	"github.com/failsafe-go/failsafe-go"
	"github.com/failsafe-go/failsafe-go/circuitbreaker"
	"github.com/failsafe-go/failsafe-go/ratelimiter"
	"github.com/failsafe-go/failsafe-go/retrypolicy"
	"github.com/failsafe-go/failsafe-go/timeout"
)

// Config holds tunable thresholds for the resilience stack. The zero value
// disables every policy; set a sub-config's Enabled field (or call
// DefaultConfig) to activate it. Durations are wall-clock.
type Config struct {
	Retry          RetryConfig          `json:"retry"`
	CircuitBreaker CircuitBreakerConfig `json:"circuit_breaker"`
	RateLimiter    RateLimiterConfig    `json:"rate_limiter"`
	Timeout        TimeoutConfig        `json:"timeout"`
}

// RetryConfig configures exponential backoff with jitter.
type RetryConfig struct {
	Enabled bool `json:"enabled"`
	// MaxRetries is the number of retries after the initial attempt. -1 means
	// no limit.
	MaxRetries int `json:"max_retries"`
	// InitialDelay is the first backoff delay; it grows by BackoffFactor up to
	// MaxDelay.
	InitialDelay time.Duration `json:"initial_delay"`
	MaxDelay     time.Duration `json:"max_delay"`
	// BackoffFactor multiplies consecutive delays. Defaults to 2 when <= 1.
	BackoffFactor float64 `json:"backoff_factor"`
	// JitterFactor randomly varies each delay by +/- this fraction (0..1).
	JitterFactor float64 `json:"jitter_factor"`
	// MaxDuration caps the total time spent retrying. Zero means no cap.
	MaxDuration time.Duration `json:"max_duration"`
}

// CircuitBreakerConfig configures count-based failure/success thresholds.
type CircuitBreakerConfig struct {
	Enabled bool `json:"enabled"`
	// FailureThreshold is the number of consecutive failures that opens the
	// breaker.
	FailureThreshold uint `json:"failure_threshold"`
	// SuccessThreshold is the number of consecutive successes in half-open
	// state that closes the breaker. Defaults to 1 when zero.
	SuccessThreshold uint `json:"success_threshold"`
	// Delay is how long the breaker stays open before transitioning to
	// half-open.
	Delay time.Duration `json:"delay"`
}

// RateLimiterConfig configures a smooth (evenly-spaced) rate limiter.
type RateLimiterConfig struct {
	Enabled bool `json:"enabled"`
	// MaxExecutions permitted per Period.
	MaxExecutions uint          `json:"max_executions"`
	Period        time.Duration `json:"period"`
	// MaxWaitTime is how long an execution waits for a permit before failing
	// with ratelimiter.ErrExceeded. Zero means do not wait (fail fast).
	MaxWaitTime time.Duration `json:"max_wait_time"`
}

// TimeoutConfig bounds the duration of a single execution attempt.
type TimeoutConfig struct {
	Enabled bool          `json:"enabled"`
	Timeout time.Duration `json:"timeout"`
}

// DefaultConfig returns a sensible production-leaning stack: 3 retries with
// 100ms→2s exponential backoff and 20% jitter, a breaker that opens after 5
// consecutive failures for 30s, a 60 req/min smooth rate limiter, and a 30s
// per-attempt timeout.
func DefaultConfig() Config {
	return Config{
		Retry: RetryConfig{
			Enabled:       true,
			MaxRetries:    3,
			InitialDelay:  100 * time.Millisecond,
			MaxDelay:      2 * time.Second,
			BackoffFactor: 2,
			JitterFactor:  0.2,
		},
		CircuitBreaker: CircuitBreakerConfig{
			Enabled:          true,
			FailureThreshold: 5,
			SuccessThreshold: 1,
			Delay:            30 * time.Second,
		},
		RateLimiter: RateLimiterConfig{
			Enabled:       true,
			MaxExecutions: 60,
			Period:        time.Minute,
			MaxWaitTime:   5 * time.Second,
		},
		Timeout: TimeoutConfig{
			Enabled: true,
			Timeout: 30 * time.Second,
		},
	}
}

// NewRetry builds a retry policy with exponential backoff and jitter for
// result type R. Returns nil when disabled.
func NewRetry[R any](c RetryConfig) failsafe.Policy[R] {
	if !c.Enabled {
		return nil
	}
	b := retrypolicy.NewBuilder[R]().WithMaxRetries(c.MaxRetries)

	if c.InitialDelay > 0 && c.MaxDelay >= c.InitialDelay {
		factor := c.BackoffFactor
		if factor <= 1 {
			factor = 2
		}
		b.WithBackoffFactor(c.InitialDelay, c.MaxDelay, factor)
	} else if c.InitialDelay > 0 {
		b.WithDelay(c.InitialDelay)
	}
	if c.JitterFactor > 0 {
		b.WithJitterFactor(c.JitterFactor)
	}
	if c.MaxDuration > 0 {
		b.WithMaxDuration(c.MaxDuration)
	}
	return b.Build()
}

// NewCircuitBreaker builds a count-based circuit breaker for result type R.
// Returns nil when disabled.
func NewCircuitBreaker[R any](c CircuitBreakerConfig) failsafe.Policy[R] {
	if !c.Enabled {
		return nil
	}
	b := circuitbreaker.NewBuilder[R]()
	if c.FailureThreshold > 0 {
		b.WithFailureThreshold(c.FailureThreshold)
	}
	success := c.SuccessThreshold
	if success == 0 {
		success = 1
	}
	b.WithSuccessThreshold(success)
	if c.Delay > 0 {
		b.WithDelay(c.Delay)
	}
	return b.Build()
}

// NewRateLimiter builds a smooth rate limiter for result type R. Returns nil
// when disabled or misconfigured (non-positive executions/period).
func NewRateLimiter[R any](c RateLimiterConfig) failsafe.Policy[R] {
	if !c.Enabled || c.MaxExecutions == 0 || c.Period <= 0 {
		return nil
	}
	b := ratelimiter.NewSmoothBuilder[R](c.MaxExecutions, c.Period)
	if c.MaxWaitTime > 0 {
		b.WithMaxWaitTime(c.MaxWaitTime)
	}
	return b.Build()
}

// NewTimeout builds a per-attempt timeout policy for result type R. Returns
// nil when disabled or non-positive.
func NewTimeout[R any](c TimeoutConfig) failsafe.Policy[R] {
	if !c.Enabled || c.Timeout <= 0 {
		return nil
	}
	return timeout.NewBuilder[R](c.Timeout).Build()
}

// Policies builds the ordered, non-nil policy slice for result type R from cfg.
// Order is outermost-first: rate limiter, circuit breaker, retry, timeout.
// Disabled policies are omitted. The result may be empty (no resilience).
func Policies[R any](cfg Config) []failsafe.Policy[R] {
	candidates := []failsafe.Policy[R]{
		NewRateLimiter[R](cfg.RateLimiter),
		NewCircuitBreaker[R](cfg.CircuitBreaker),
		NewRetry[R](cfg.Retry),
		NewTimeout[R](cfg.Timeout),
	}
	policies := make([]failsafe.Policy[R], 0, len(candidates))
	for _, p := range candidates {
		if p != nil {
			policies = append(policies, p)
		}
	}
	return policies
}

// Execute runs fn under the given policies, honoring ctx cancellation. With no
// policies it simply invokes fn once. The returned error is fn's error or a
// failsafe-go policy error (e.g. retrypolicy.ErrExceeded wrapping the last
// failure, circuitbreaker.ErrOpen, ratelimiter.ErrExceeded, timeout.ErrExceeded).
func Execute[T any](ctx context.Context, policies []failsafe.Policy[T], fn func(ctx context.Context) (T, error)) (T, error) {
	exec := failsafe.With(policies...).WithContext(ctx)
	return exec.GetWithExecution(func(e failsafe.Execution[T]) (T, error) {
		return fn(e.Context())
	})
}

// ExecuteCfg is a convenience wrapper that builds the policy stack from cfg and
// runs fn under it.
func ExecuteCfg[T any](ctx context.Context, cfg Config, fn func(ctx context.Context) (T, error)) (T, error) {
	return Execute(ctx, Policies[T](cfg), fn)
}
