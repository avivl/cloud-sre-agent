// Package detect provides a minimal, in-memory threshold detector. It
// accumulates domain.LogEvents over a sliding time window and emits a
// domain.Incident when the error rate or a high-severity event count crosses a
// configured threshold. State is kept entirely in memory and is not safe for
// concurrent use from multiple goroutines; the agent's consume loop drives it
// from a single goroutine.
package detect

import (
	"fmt"
	"sort"
	"time"

	"github.com/avivl/cloud-sre-agent/internal/domain"
)

// Config tunes the threshold detector. Zero values are replaced with the
// defaults from DefaultConfig by New.
type Config struct {
	// Window is the sliding time window over which events are accumulated.
	Window time.Duration
	// MinEvents is the minimum number of events in the window before the
	// detector will consider firing, so a single error in an empty window does
	// not trip a 100% error rate.
	MinEvents int
	// ErrorRateThreshold is the fraction (0,1] of events at SeverityError or
	// above that, once met, triggers an incident.
	ErrorRateThreshold float64
	// CriticalCount is the number of SeverityCritical events in the window that
	// triggers an incident regardless of the error rate. Zero disables this
	// trigger.
	CriticalCount int
	// Cooldown is the minimum time between two emitted incidents, so a sustained
	// error storm produces one incident rather than one per event.
	Cooldown time.Duration
}

// DefaultConfig returns production-leaning detector defaults: a 60s window, at
// least 5 events before firing, a 50% error-rate threshold, 3 criticals as a
// hard trigger, and a 60s cooldown between incidents.
func DefaultConfig() Config {
	return Config{
		Window:             60 * time.Second,
		MinEvents:          5,
		ErrorRateThreshold: 0.5,
		CriticalCount:      3,
		Cooldown:           60 * time.Second,
	}
}

// Detector accumulates events over a sliding window and emits incidents when
// thresholds are crossed. Construct it with New.
type Detector struct {
	cfg    Config
	events []domain.LogEvent
	// lastFiredAt is the timestamp of the most recently emitted incident, used
	// to enforce the cooldown. Zero means none has fired.
	lastFiredAt time.Time
	// windowNow is the maximum event timestamp observed so far (monotonic
	// non-decreasing). It is the detector's notion of "now" for eviction and
	// cooldown, so a single future- or past-dated event cannot rewind the window
	// or corrupt the cooldown.
	windowNow time.Time
	// seq makes emitted incident IDs unique within a detector's lifetime.
	seq uint64
}

// New returns a Detector. Unset/invalid Config fields fall back to
// DefaultConfig values so a zero Config yields a usable detector.
func New(cfg Config) *Detector {
	d := DefaultConfig()
	if cfg.Window > 0 {
		d.Window = cfg.Window
	}
	if cfg.MinEvents > 0 {
		d.MinEvents = cfg.MinEvents
	}
	if cfg.ErrorRateThreshold > 0 {
		d.ErrorRateThreshold = cfg.ErrorRateThreshold
	}
	// CriticalCount and Cooldown may legitimately be 0 (disabled), so only
	// override the default when the caller set a positive value.
	if cfg.CriticalCount > 0 {
		d.CriticalCount = cfg.CriticalCount
	}
	if cfg.Cooldown > 0 {
		d.Cooldown = cfg.Cooldown
	}
	return &Detector{cfg: d}
}

// Observe records an event and evaluates the thresholds against the current
// window. It returns a non-nil *domain.Incident when an incident is detected
// (and the cooldown allows it), otherwise nil. The event's Timestamp drives the
// sliding window; events with a zero timestamp are stamped with time.Now so
// out-of-band events still participate.
func (d *Detector) Observe(e domain.LogEvent) *domain.Incident {
	if e.Timestamp.IsZero() {
		e.Timestamp = time.Now().UTC()
	}
	d.events = append(d.events, e)

	// Advance the window clock monotonically: an out-of-order or stale-dated
	// event never rewinds "now". A single future-dated event does move it
	// forward, but that is the conservative choice (it can only evict, not
	// resurrect, old events).
	if e.Timestamp.After(d.windowNow) {
		d.windowNow = e.Timestamp
	}
	d.evict(d.windowNow)

	if len(d.events) < d.cfg.MinEvents {
		return nil
	}

	errCount, critCount := d.counts()
	rate := float64(errCount) / float64(len(d.events))

	critTrigger := d.cfg.CriticalCount > 0 && critCount >= d.cfg.CriticalCount
	rateTrigger := rate >= d.cfg.ErrorRateThreshold

	if !critTrigger && !rateTrigger {
		return nil
	}

	// Enforce cooldown relative to the monotonic window clock, not the arriving
	// event's (possibly out-of-order) timestamp.
	if !d.lastFiredAt.IsZero() && d.windowNow.Sub(d.lastFiredAt) < d.cfg.Cooldown {
		return nil
	}
	d.lastFiredAt = d.windowNow

	inc := d.buildIncident(d.windowNow, errCount, critCount, rate, critTrigger)
	return &inc
}

// evict drops events older than the window relative to now.
func (d *Detector) evict(now time.Time) {
	cutoff := now.Add(-d.cfg.Window)
	keep := d.events[:0]
	for _, ev := range d.events {
		if !ev.Timestamp.Before(cutoff) {
			keep = append(keep, ev)
		}
	}
	d.events = keep
}

// counts returns the number of error-or-above and critical events in the
// current window.
func (d *Detector) counts() (errCount, critCount int) {
	for _, ev := range d.events {
		if ev.Severity >= domain.SeverityError {
			errCount++
		}
		if ev.Severity >= domain.SeverityCritical {
			critCount++
		}
	}
	return errCount, critCount
}

// buildIncident assembles a validated-shape Incident from the current window.
func (d *Detector) buildIncident(at time.Time, errCount, critCount int, rate float64, critTrigger bool) domain.Incident {
	d.seq++
	id := fmt.Sprintf("incident-%d", d.seq)

	services := d.affectedServices()
	samples := d.samples()

	// Severity score blends the error rate with critical pressure, clamped to
	// [0,1] so it satisfies domain.Incident.Validate.
	score := rate
	if d.cfg.CriticalCount > 0 {
		critFrac := float64(critCount) / float64(d.cfg.CriticalCount)
		if critFrac > score {
			score = critFrac
		}
	}
	if score > 1 {
		score = 1
	}

	pattern := "elevated-error-rate"
	if critTrigger {
		pattern = "critical-event-burst"
	}

	summary := fmt.Sprintf(
		"%d errors of %d events (%.0f%% error rate, %d critical) over %s",
		errCount, len(d.events), rate*100, critCount, d.cfg.Window,
	)

	return domain.Incident{
		ID:               id,
		Pattern:          pattern,
		SeverityScore:    score,
		AffectedServices: services,
		SampleEvents:     samples,
		Summary:          summary,
		DetectedAt:       at,
	}
}

// affectedServices returns the distinct, sorted source identifiers seen in the
// window, so incident consumers know what to look at.
func (d *Detector) affectedServices() []string {
	seen := make(map[string]struct{})
	for _, ev := range d.events {
		if ev.Source != "" {
			seen[ev.Source] = struct{}{}
		}
	}
	if len(seen) == 0 {
		return nil
	}
	out := make([]string, 0, len(seen))
	for s := range seen {
		out = append(out, s)
	}
	sort.Strings(out)
	return out
}

// samples returns up to maxSamples of the highest-severity events in the
// window, most severe first, as evidence attached to the incident.
func (d *Detector) samples() []domain.LogEvent {
	const maxSamples = 5
	sorted := make([]domain.LogEvent, len(d.events))
	copy(sorted, d.events)
	sort.SliceStable(sorted, func(i, j int) bool {
		return sorted[i].Severity > sorted[j].Severity
	})
	if len(sorted) > maxSamples {
		sorted = sorted[:maxSamples]
	}
	return sorted
}
