// Package domain defines the core, dependency-free types shared across the
// SRE agent: log events, detected incidents, and the triage -> analysis ->
// remediation artifacts. These types carry no I/O and no provider coupling so
// that every port and adapter can speak the same vocabulary.
package domain

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/invopop/jsonschema"
)

// Severity is an ordered log/incident severity level.
type Severity int

// Severity levels, ascending in urgency.
const (
	SeverityUnknown Severity = iota
	SeverityDebug
	SeverityInfo
	SeverityWarning
	SeverityError
	SeverityCritical
)

// severityLabels are the canonical lowercase labels for the meaningful (non-
// unknown) severity levels, in ascending order. They are the single source of
// truth for both String and the JSON-schema enum, so structured-output schemas
// advertise exactly the strings MarshalJSON produces.
var severityLabels = []string{"debug", "info", "warning", "error", "critical"}

// String renders the severity as a lowercase label.
func (s Severity) String() string {
	switch s {
	case SeverityDebug:
		return "debug"
	case SeverityInfo:
		return "info"
	case SeverityWarning:
		return "warning"
	case SeverityError:
		return "error"
	case SeverityCritical:
		return "critical"
	case SeverityUnknown:
		return "unknown"
	default:
		return "unknown"
	}
}

// JSONSchema makes the reflected JSON schema advertise a Severity as a string
// enum of the real labels rather than a bare integer, so a structured-output
// model emits e.g. "critical" and round-trips through UnmarshalJSON.
func (Severity) JSONSchema() *jsonschema.Schema {
	enum := make([]any, len(severityLabels))
	for i, l := range severityLabels {
		enum[i] = l
	}
	return &jsonschema.Schema{
		Type:        "string",
		Enum:        enum,
		Description: "severity level",
	}
}

// Valid reports whether s is a defined severity level.
func (s Severity) Valid() bool {
	return s >= SeverityUnknown && s <= SeverityCritical
}

// MarshalJSON emits the lowercase string label so structured-output schemas and
// JSON payloads carry a stable, human-readable severity rather than a bare int.
func (s Severity) MarshalJSON() ([]byte, error) {
	return json.Marshal(s.String())
}

// UnmarshalJSON accepts the string label produced by MarshalJSON (and, for
// robustness, a bare numeric severity), mapping it back to a Severity via
// ParseSeverity.
func (s *Severity) UnmarshalJSON(data []byte) error {
	var label string
	if err := json.Unmarshal(data, &label); err != nil {
		// Fall back to a numeric severity for compatibility with raw int input.
		var n int
		if numErr := json.Unmarshal(data, &n); numErr != nil {
			return fmt.Errorf("severity: expected string or int: %w", err)
		}
		*s = Severity(n)
		return nil
	}
	*s = ParseSeverity(label)
	return nil
}

// ParseSeverity maps a case-insensitive label to a Severity. Unrecognized
// labels return SeverityUnknown.
func ParseSeverity(label string) Severity {
	switch strings.ToLower(strings.TrimSpace(label)) {
	case "debug", "trace":
		return SeverityDebug
	case "info", "notice":
		return SeverityInfo
	case "warning", "warn":
		return SeverityWarning
	case "error", "err":
		return SeverityError
	case "critical", "fatal", "alert", "emergency", "panic", "emerg":
		return SeverityCritical
	default:
		return SeverityUnknown
	}
}

// LogEvent is a single normalized log line drawn from a LogSource.
type LogEvent struct {
	ID        string            `json:"id"`
	Timestamp time.Time         `json:"timestamp"`
	Severity  Severity          `json:"severity"`
	Message   string            `json:"message"`
	Source    string            `json:"source"`
	Labels    map[string]string `json:"labels,omitempty"`
}

// Validate checks the minimally required fields of a LogEvent.
func (e LogEvent) Validate() error {
	if e.ID == "" {
		return fmt.Errorf("log event: id is required")
	}
	if e.Message == "" {
		return fmt.Errorf("log event %q: message is required", e.ID)
	}
	if !e.Severity.Valid() {
		return fmt.Errorf("log event %q: invalid severity %d", e.ID, e.Severity)
	}
	return nil
}

// NewLogEvent constructs a validated LogEvent. Labels may be nil.
func NewLogEvent(id, source, message string, sev Severity, ts time.Time, labels map[string]string) (LogEvent, error) {
	e := LogEvent{
		ID:        id,
		Timestamp: ts,
		Severity:  sev,
		Message:   message,
		Source:    source,
		Labels:    labels,
	}
	if err := e.Validate(); err != nil {
		return LogEvent{}, err
	}
	return e, nil
}

// Incident is a correlated cluster of log events the detector judged anomalous.
type Incident struct {
	ID               string     `json:"id"`
	Pattern          string     `json:"pattern"`
	SeverityScore    float64    `json:"severity_score"`
	AffectedServices []string   `json:"affected_services,omitempty"`
	SampleEvents     []LogEvent `json:"sample_events,omitempty"`
	Summary          string     `json:"summary"`
	DetectedAt       time.Time  `json:"detected_at"`
}

// Validate checks the minimally required fields of an Incident.
func (i Incident) Validate() error {
	if i.ID == "" {
		return fmt.Errorf("incident: id is required")
	}
	if i.Pattern == "" {
		return fmt.Errorf("incident %q: pattern is required", i.ID)
	}
	if i.SeverityScore < 0 || i.SeverityScore > 1 {
		return fmt.Errorf("incident %q: severity_score %f out of range [0,1]", i.ID, i.SeverityScore)
	}
	return nil
}

// TriageResult is the fast first-pass classification of an Incident. IncidentID
// is server-owned: the pipeline sets it after decoding the model's output, so it
// is excluded (json:"-") from the prompt-facing schema and never requested from
// the model.
type TriageResult struct {
	IncidentID  string   `json:"-"`
	Category    string   `json:"category"`
	Severity    Severity `json:"severity"`
	Confidence  float64  `json:"confidence"`
	Actionable  bool     `json:"actionable"`
	Reasoning   string   `json:"reasoning"`
	NextActions []string `json:"next_actions,omitempty"`
}

// Analysis is the deep root-cause analysis produced after triage. IncidentID is
// server-owned (set by the pipeline post-decode) and excluded from the
// prompt-facing schema.
type Analysis struct {
	IncidentID  string   `json:"-"`
	RootCause   string   `json:"root_cause"`
	ProposedFix string   `json:"proposed_fix"`
	KeyPoints   []string `json:"key_points,omitempty"`
	Confidence  float64  `json:"confidence"`
}

// RemediationPlan is the concrete, deliverable output of the pipeline: a code
// change with enough context to open as a patch or PR.
type RemediationPlan struct {
	// IncidentID is server-owned: the pipeline sets it after decoding, so it is
	// excluded (json:"-") from the prompt-facing schema and never requested.
	IncidentID        string   `json:"-"`
	RootCauseAnalysis string   `json:"root_cause_analysis"`
	ProposedFix       string   `json:"proposed_fix"`
	CodePatch         string   `json:"code_patch"`
	Priority          Severity `json:"priority"`
	EstimatedEffort   string   `json:"estimated_effort"`
	TargetFile        string   `json:"target_file"`
}

// Validate checks the minimally required fields of a RemediationPlan.
func (p RemediationPlan) Validate() error {
	if p.IncidentID == "" {
		return fmt.Errorf("remediation plan: incident_id is required")
	}
	if p.CodePatch == "" {
		return fmt.Errorf("remediation plan for %q: code_patch is required", p.IncidentID)
	}
	if p.TargetFile == "" {
		return fmt.Errorf("remediation plan for %q: target_file is required", p.IncidentID)
	}
	return nil
}
