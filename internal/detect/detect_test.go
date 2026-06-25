package detect

import (
	"testing"
	"time"

	"github.com/stretchr/testify/require"

	"github.com/avivl/cloud-sre-agent/internal/domain"
)

// ev builds a LogEvent at a fixed offset from a base time.
func ev(base time.Time, offset time.Duration, sev domain.Severity, src string) domain.LogEvent {
	return domain.LogEvent{
		ID:        "e",
		Timestamp: base.Add(offset),
		Severity:  sev,
		Message:   "boom",
		Source:    src,
	}
}

func TestNew_DefaultsFillZeroConfig(t *testing.T) {
	d := New(Config{})
	require.Equal(t, DefaultConfig(), d.cfg)
}

func TestNew_OverridesAndDisables(t *testing.T) {
	d := New(Config{
		Window:             10 * time.Second,
		MinEvents:          2,
		ErrorRateThreshold: 0.25,
		CriticalCount:      0, // 0 is "use default" per New semantics
		Cooldown:           0, // 0 is "use default" per New semantics
	})
	require.Equal(t, 10*time.Second, d.cfg.Window)
	require.Equal(t, 2, d.cfg.MinEvents)
	require.InEpsilon(t, 0.25, d.cfg.ErrorRateThreshold, 1e-9)
	require.Equal(t, DefaultConfig().CriticalCount, d.cfg.CriticalCount)
	require.Equal(t, DefaultConfig().Cooldown, d.cfg.Cooldown)
}

func TestObserve_TableDriven(t *testing.T) {
	base := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)

	tests := []struct {
		name       string
		cfg        Config
		events     []domain.LogEvent
		wantFires  int
		assertLast func(t *testing.T, inc *domain.Incident)
	}{
		{
			name: "below min events never fires",
			cfg:  Config{Window: time.Minute, MinEvents: 5, ErrorRateThreshold: 0.5, Cooldown: time.Minute},
			events: []domain.LogEvent{
				ev(base, 0, domain.SeverityError, "svc-a"),
				ev(base, time.Second, domain.SeverityError, "svc-a"),
			},
			wantFires: 0,
		},
		{
			name: "error rate crossed fires once with cooldown",
			cfg:  Config{Window: time.Minute, MinEvents: 4, ErrorRateThreshold: 0.5, Cooldown: time.Minute},
			events: []domain.LogEvent{
				ev(base, 0, domain.SeverityInfo, "svc-a"),
				ev(base, time.Second, domain.SeverityError, "svc-a"),
				ev(base, 2*time.Second, domain.SeverityError, "svc-b"),
				ev(base, 3*time.Second, domain.SeverityError, "svc-b"), // 3/4 = 0.75 >= 0.5
				ev(base, 4*time.Second, domain.SeverityError, "svc-b"), // still in cooldown
			},
			wantFires: 1,
			assertLast: func(t *testing.T, inc *domain.Incident) {
				t.Helper()
				require.Equal(t, "elevated-error-rate", inc.Pattern)
				require.Equal(t, []string{"svc-a", "svc-b"}, inc.AffectedServices)
				require.NoError(t, inc.Validate())
				require.LessOrEqual(t, inc.SeverityScore, 1.0)
				require.GreaterOrEqual(t, inc.SeverityScore, 0.0)
			},
		},
		{
			name: "critical count is a hard trigger even below error rate",
			cfg:  Config{Window: time.Minute, MinEvents: 3, ErrorRateThreshold: 0.99, CriticalCount: 2, Cooldown: time.Minute},
			events: []domain.LogEvent{
				ev(base, 0, domain.SeverityInfo, "svc-a"),
				ev(base, time.Second, domain.SeverityCritical, "svc-a"),
				ev(base, 2*time.Second, domain.SeverityCritical, "svc-a"), // 2 criticals
			},
			wantFires: 1,
			assertLast: func(t *testing.T, inc *domain.Incident) {
				t.Helper()
				require.Equal(t, "critical-event-burst", inc.Pattern)
			},
		},
		{
			name: "old events evicted from window drop the rate below threshold",
			cfg:  Config{Window: 5 * time.Second, MinEvents: 3, ErrorRateThreshold: 0.9, Cooldown: time.Minute},
			events: []domain.LogEvent{
				ev(base, 0, domain.SeverityError, "svc-a"),
				ev(base, time.Second, domain.SeverityError, "svc-a"),
				// 10s later: the two old errors are evicted; only infos remain.
				ev(base, 10*time.Second, domain.SeverityInfo, "svc-a"),
				ev(base, 11*time.Second, domain.SeverityInfo, "svc-a"),
				ev(base, 12*time.Second, domain.SeverityInfo, "svc-a"),
			},
			wantFires: 0,
		},
		{
			name: "cooldown elapsed allows a second incident",
			cfg:  Config{Window: 10 * time.Minute, MinEvents: 2, ErrorRateThreshold: 0.5, Cooldown: 30 * time.Second},
			events: []domain.LogEvent{
				ev(base, 0, domain.SeverityError, "svc-a"),
				ev(base, time.Second, domain.SeverityError, "svc-a"),    // fires #1
				ev(base, 2*time.Second, domain.SeverityError, "svc-a"),  // within cooldown
				ev(base, 40*time.Second, domain.SeverityError, "svc-a"), // cooldown elapsed -> fires #2
			},
			wantFires: 2,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			d := New(tt.cfg)
			var fires int
			var last *domain.Incident
			for _, e := range tt.events {
				if inc := d.Observe(e); inc != nil {
					fires++
					last = inc
				}
			}
			require.Equal(t, tt.wantFires, fires)
			if tt.assertLast != nil {
				require.NotNil(t, last)
				tt.assertLast(t, last)
			}
		})
	}
}

func TestObserve_UniqueIncidentIDs(t *testing.T) {
	base := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	d := New(Config{Window: time.Hour, MinEvents: 2, ErrorRateThreshold: 0.5, Cooldown: time.Second})

	var ids []string
	for i := 0; i < 6; i++ {
		// space events past the 1s cooldown
		e := ev(base, time.Duration(i)*2*time.Second, domain.SeverityError, "svc")
		if inc := d.Observe(e); inc != nil {
			ids = append(ids, inc.ID)
		}
	}
	require.GreaterOrEqual(t, len(ids), 2)
	seen := map[string]struct{}{}
	for _, id := range ids {
		_, dup := seen[id]
		require.False(t, dup, "duplicate incident id %q", id)
		seen[id] = struct{}{}
	}
}

func TestObserve_MonotonicWindowClock(t *testing.T) {
	base := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)

	t.Run("cooldown is measured against the monotonic clock, not stale event times", func(t *testing.T) {
		// Window 2 minutes so events are not evicted by time here; cooldown 30s.
		d := New(Config{Window: 2 * time.Minute, MinEvents: 2, ErrorRateThreshold: 0.5, Cooldown: 30 * time.Second})

		// Two errors fire incident #1; the window clock is at t=1s.
		require.Nil(t, d.Observe(ev(base, 0, domain.SeverityError, "svc")))
		require.NotNil(t, d.Observe(ev(base, time.Second, domain.SeverityError, "svc")))

		// A stale, out-of-order event dated *before* lastFiredAt arrives. Under the
		// old logic e.Timestamp.Sub(lastFiredAt) would be negative and < cooldown,
		// correctly suppressed — but a stale event could also rewind the cooldown
		// math. With the monotonic clock the window stays at t=1s, so this stale
		// event is within cooldown and must not fire.
		require.Nil(t, d.Observe(ev(base, -10*time.Second, domain.SeverityError, "svc")),
			"stale past-dated event must not fire within cooldown")

		// A genuinely later event past the cooldown fires incident #2, with the
		// window clock having advanced monotonically.
		inc2 := d.Observe(ev(base, 45*time.Second, domain.SeverityError, "svc"))
		require.NotNil(t, inc2)
		require.Equal(t, base.Add(45*time.Second), inc2.DetectedAt)
	})

	t.Run("out-of-order events do not corrupt eviction", func(t *testing.T) {
		// 5s window. A future event advances the clock so older events are evicted
		// by the future cutoff rather than by each arriving event's own time.
		d := New(Config{Window: 5 * time.Second, MinEvents: 2, ErrorRateThreshold: 0.99, Cooldown: time.Minute})

		require.Nil(t, d.Observe(ev(base, 0, domain.SeverityError, "svc")))
		// Far-future event: advances windowNow to base+1m, evicting the t=0 event.
		require.Nil(t, d.Observe(ev(base, time.Minute, domain.SeverityInfo, "svc")))
		// Now a stale error at t=1s: it is older than the cutoff (base+1m-5s) and
		// would be evicted, so the error rate stays below the 0.99 threshold.
		got := d.Observe(ev(base, time.Second, domain.SeverityError, "svc"))
		require.Nil(t, got)
	})
}

func TestObserve_ZeroTimestampStamped(t *testing.T) {
	d := New(Config{MinEvents: 1, ErrorRateThreshold: 0.5, Cooldown: time.Nanosecond})
	inc := d.Observe(domain.LogEvent{ID: "e", Severity: domain.SeverityError, Message: "x", Source: "s"})
	require.NotNil(t, inc)
	require.False(t, inc.DetectedAt.IsZero())
}
