package resilience

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"

	"github.com/failsafe-go/failsafe-go"
	"github.com/failsafe-go/failsafe-go/circuitbreaker"
	"github.com/failsafe-go/failsafe-go/ratelimiter"
	"github.com/failsafe-go/failsafe-go/timeout"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

var errTransient = errors.New("transient failure")

// fakeOp is a deterministic operation: it fails the first failTimes calls,
// then succeeds, recording how many times it was invoked.
type fakeOp struct {
	failTimes int32
	calls     atomic.Int32
}

func (f *fakeOp) run(_ context.Context) (string, error) {
	n := f.calls.Add(1)
	if n <= f.failTimes {
		return "", errTransient
	}
	return "ok", nil
}

func fastRetry() RetryConfig {
	return RetryConfig{
		Enabled:      true,
		MaxRetries:   5,
		InitialDelay: time.Millisecond,
		MaxDelay:     2 * time.Millisecond,
		JitterFactor: 0.1,
	}
}

func TestExecute_RetrySucceedsAfterTransientFailures(t *testing.T) {
	op := &fakeOp{failTimes: 2}
	policies := Policies[string](Config{Retry: fastRetry()})

	got, err := Execute(context.Background(), policies, op.run)
	require.NoError(t, err)
	assert.Equal(t, "ok", got)
	// 2 failures + 1 success = 3 invocations.
	assert.Equal(t, int32(3), op.calls.Load())
}

func TestExecute_RetryExhausted(t *testing.T) {
	op := &fakeOp{failTimes: 100} // always fails
	cfg := fastRetry()
	cfg.MaxRetries = 2
	policies := Policies[string](Config{Retry: cfg})

	_, err := Execute(context.Background(), policies, op.run)
	require.Error(t, err)
	assert.ErrorIs(t, err, errTransient)
	// initial + 2 retries = 3 invocations.
	assert.Equal(t, int32(3), op.calls.Load())
}

func TestExecute_NoPoliciesRunsOnce(t *testing.T) {
	op := &fakeOp{failTimes: 1}
	got, err := Execute(context.Background(), nil, op.run)
	require.Error(t, err)
	assert.Empty(t, got)
	assert.Equal(t, int32(1), op.calls.Load())
}

func TestExecute_NoPoliciesSuccess(t *testing.T) {
	op := &fakeOp{failTimes: 0}
	got, err := Execute(context.Background(), nil, op.run)
	require.NoError(t, err)
	assert.Equal(t, "ok", got)
}

func TestCircuitBreaker_OpensAfterThreshold(t *testing.T) {
	// Breaker only (no retry) so each Execute is a single attempt.
	cfg := Config{
		CircuitBreaker: CircuitBreakerConfig{
			Enabled:          true,
			FailureThreshold: 2,
			Delay:            time.Hour, // stay open for the test
		},
	}
	policies := Policies[string](cfg)

	alwaysFail := func(_ context.Context) (string, error) {
		return "", errTransient
	}

	// First two failures trip the breaker.
	_, err1 := Execute(context.Background(), policies, alwaysFail)
	assert.ErrorIs(t, err1, errTransient)
	_, err2 := Execute(context.Background(), policies, alwaysFail)
	assert.ErrorIs(t, err2, errTransient)

	// Breaker is now open: the next call short-circuits without invoking fn.
	invoked := false
	_, err3 := Execute(context.Background(), policies, func(_ context.Context) (string, error) {
		invoked = true
		return "ok", nil
	})
	assert.ErrorIs(t, err3, circuitbreaker.ErrOpen)
	assert.False(t, invoked, "fn must not run while breaker is open")
}

func TestCircuitBreaker_RecoversAfterDelay(t *testing.T) {
	cfg := Config{
		CircuitBreaker: CircuitBreakerConfig{
			Enabled:          true,
			FailureThreshold: 1,
			SuccessThreshold: 1,
			Delay:            5 * time.Millisecond,
		},
	}
	policies := Policies[string](cfg)

	_, err := Execute(context.Background(), policies, func(_ context.Context) (string, error) {
		return "", errTransient
	})
	require.ErrorIs(t, err, errTransient)

	// Immediately open.
	_, err = Execute(context.Background(), policies, func(_ context.Context) (string, error) {
		return "ok", nil
	})
	require.ErrorIs(t, err, circuitbreaker.ErrOpen)

	// After the delay it half-opens and a success closes it.
	require.Eventually(t, func() bool {
		got, e := Execute(context.Background(), policies, func(_ context.Context) (string, error) {
			return "ok", nil
		})
		return e == nil && got == "ok"
	}, 200*time.Millisecond, 2*time.Millisecond)
}

func TestRetryAndCircuitBreaker_Compose(t *testing.T) {
	// Composition order is CircuitBreaker(Retry(fn)): retry is innermost, so it
	// exhausts and surfaces the transient error, while the breaker records the
	// single aggregate failure. A second call then trips the breaker.
	cfg := Config{
		Retry: RetryConfig{
			Enabled: true, MaxRetries: 1,
			InitialDelay: time.Millisecond, MaxDelay: 2 * time.Millisecond,
		},
		CircuitBreaker: CircuitBreakerConfig{
			Enabled:          true,
			FailureThreshold: 1,
			Delay:            time.Hour,
		},
	}
	policies := Policies[string](cfg)
	require.Len(t, policies, 2)

	op := &fakeOp{failTimes: 100}
	_, err := Execute(context.Background(), policies, op.run)
	require.Error(t, err)
	// Retry (inner) exhausts first, surfacing the underlying transient error.
	assert.ErrorIs(t, err, errTransient)
	// initial + 1 retry = 2 invocations of the inner fn.
	assert.Equal(t, int32(2), op.calls.Load())

	// The breaker recorded that aggregate failure (threshold 1) and is now open.
	invoked := false
	_, err = Execute(context.Background(), policies, func(_ context.Context) (string, error) {
		invoked = true
		return "ok", nil
	})
	assert.ErrorIs(t, err, circuitbreaker.ErrOpen)
	assert.False(t, invoked, "fn must not run while breaker is open")
}

func TestRateLimiter_FailFastWhenExhausted(t *testing.T) {
	cfg := Config{
		RateLimiter: RateLimiterConfig{
			Enabled:       true,
			MaxExecutions: 1,
			Period:        time.Hour, // one permit, then no refill in-test
			MaxWaitTime:   0,         // fail fast
		},
	}
	policies := Policies[string](cfg)

	ok := func(_ context.Context) (string, error) { return "ok", nil }

	_, err := Execute(context.Background(), policies, ok)
	require.NoError(t, err)

	_, err = Execute(context.Background(), policies, ok)
	assert.ErrorIs(t, err, ratelimiter.ErrExceeded)
}

func TestTimeout_ExceededOnSlowOperation(t *testing.T) {
	cfg := Config{
		Timeout: TimeoutConfig{Enabled: true, Timeout: 10 * time.Millisecond},
	}
	policies := Policies[string](cfg)

	slow := func(ctx context.Context) (string, error) {
		select {
		case <-time.After(200 * time.Millisecond):
			return "late", nil
		case <-ctx.Done():
			return "", ctx.Err()
		}
	}

	_, err := Execute(context.Background(), policies, slow)
	assert.ErrorIs(t, err, timeout.ErrExceeded)
}

func TestExecute_ContextCancellation(t *testing.T) {
	policies := Policies[string](Config{Retry: fastRetry()})

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // already cancelled

	op := &fakeOp{failTimes: 100}
	_, err := Execute(ctx, policies, op.run)
	require.Error(t, err)
	// Cancelled context must not allow unbounded retries.
	assert.LessOrEqual(t, op.calls.Load(), int32(1))
}

func TestPolicies_OrderAndOmission(t *testing.T) {
	// All enabled -> 4 policies in outermost-first order.
	all := Policies[string](DefaultConfig())
	assert.Len(t, all, 4)

	// Empty config -> no policies.
	none := Policies[string](Config{})
	assert.Empty(t, none)

	// Selective enablement.
	partial := Policies[string](Config{
		Retry:   fastRetry(),
		Timeout: TimeoutConfig{Enabled: true, Timeout: time.Second},
	})
	assert.Len(t, partial, 2)
}

func TestExecuteCfg_BuildsStack(t *testing.T) {
	op := &fakeOp{failTimes: 1}
	cfg := Config{Retry: fastRetry()}
	got, err := ExecuteCfg(context.Background(), cfg, op.run)
	require.NoError(t, err)
	assert.Equal(t, "ok", got)
	assert.Equal(t, int32(2), op.calls.Load())
}

func TestBuilders_NilWhenDisabled(t *testing.T) {
	assert.Nil(t, NewRetry[string](RetryConfig{}))
	assert.Nil(t, NewCircuitBreaker[string](CircuitBreakerConfig{}))
	assert.Nil(t, NewRateLimiter[string](RateLimiterConfig{}))
	assert.Nil(t, NewTimeout[string](TimeoutConfig{}))

	// Enabled-but-invalid rate limiter / timeout also yield nil.
	assert.Nil(t, NewRateLimiter[string](RateLimiterConfig{Enabled: true}))
	assert.Nil(t, NewTimeout[string](TimeoutConfig{Enabled: true}))
}

func TestNewRetry_FlatDelayPath(t *testing.T) {
	// InitialDelay set but MaxDelay < InitialDelay -> flat WithDelay path.
	p := NewRetry[string](RetryConfig{
		Enabled:      true,
		MaxRetries:   1,
		InitialDelay: time.Millisecond,
		MaxDelay:     0,
		MaxDuration:  time.Second,
	})
	require.NotNil(t, p)

	op := &fakeOp{failTimes: 1}
	got, err := failsafe.With(p).Get(func() (string, error) { return op.run(context.Background()) })
	require.NoError(t, err)
	assert.Equal(t, "ok", got)
}
