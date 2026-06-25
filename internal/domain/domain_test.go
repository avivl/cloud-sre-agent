package domain

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestSeverity_String(t *testing.T) {
	cases := map[Severity]string{
		SeverityUnknown:  "unknown",
		SeverityDebug:    "debug",
		SeverityInfo:     "info",
		SeverityWarning:  "warning",
		SeverityError:    "error",
		SeverityCritical: "critical",
		Severity(99):     "unknown",
	}
	for sev, want := range cases {
		assert.Equal(t, want, sev.String())
	}
}

func TestSeverity_Valid(t *testing.T) {
	assert.True(t, SeverityInfo.Valid())
	assert.True(t, SeverityCritical.Valid())
	assert.False(t, Severity(99).Valid())
	assert.False(t, Severity(-1).Valid())
}

func TestParseSeverity(t *testing.T) {
	cases := map[string]Severity{
		"DEBUG":     SeverityDebug,
		"info":      SeverityInfo,
		"WARN":      SeverityWarning,
		"error":     SeverityError,
		"fatal":     SeverityCritical,
		"emergency": SeverityCritical,
		"nonsense":  SeverityUnknown,
		// Casing and surrounding whitespace are normalized.
		"WaRnInG":    SeverityWarning,
		"  error  ":  SeverityError,
		"\tCRITICAL": SeverityCritical,
		"Info":       SeverityInfo,
		"trace":      SeverityDebug,
		"":           SeverityUnknown,
	}
	for label, want := range cases {
		assert.Equal(t, want, ParseSeverity(label), "label %q", label)
	}
}

func TestSeverity_JSONRoundTrip(t *testing.T) {
	for _, sev := range []Severity{
		SeverityDebug, SeverityInfo, SeverityWarning, SeverityError, SeverityCritical,
	} {
		b, err := json.Marshal(sev)
		require.NoError(t, err)
		// Marshals as the lowercase string label, not a bare int.
		assert.Equal(t, `"`+sev.String()+`"`, string(b))

		var got Severity
		require.NoError(t, json.Unmarshal(b, &got))
		assert.Equal(t, sev, got)
	}
}

func TestSeverity_UnmarshalJSON_NumericFallback(t *testing.T) {
	var s Severity
	require.NoError(t, json.Unmarshal([]byte("4"), &s))
	assert.Equal(t, SeverityError, s)

	require.Error(t, json.Unmarshal([]byte("true"), &s))
}

func TestSeverity_StructRoundTrip(t *testing.T) {
	// A struct carrying a Severity round-trips the string form, which is what the
	// LLM structured-output path relies on.
	in := TriageResult{Category: "latency", Severity: SeverityCritical, Actionable: true}
	b, err := json.Marshal(in)
	require.NoError(t, err)
	assert.Contains(t, string(b), `"severity":"critical"`)

	var out TriageResult
	require.NoError(t, json.Unmarshal(b, &out))
	assert.Equal(t, SeverityCritical, out.Severity)
}

func TestNewLogEvent(t *testing.T) {
	now := time.Now()
	e, err := NewLogEvent("evt-1", "file:app.log", "boom", SeverityError, now, map[string]string{"svc": "api"})
	require.NoError(t, err)
	assert.Equal(t, "evt-1", e.ID)
	assert.Equal(t, SeverityError, e.Severity)
	assert.Equal(t, "api", e.Labels["svc"])

	_, err = NewLogEvent("", "src", "msg", SeverityInfo, now, nil)
	assert.Error(t, err)

	_, err = NewLogEvent("id", "src", "", SeverityInfo, now, nil)
	assert.Error(t, err)

	_, err = NewLogEvent("id", "src", "msg", Severity(99), now, nil)
	assert.Error(t, err)
}

func TestIncident_Validate(t *testing.T) {
	good := Incident{ID: "inc-1", Pattern: "error-spike", SeverityScore: 0.8}
	require.NoError(t, good.Validate())

	assert.Error(t, Incident{Pattern: "p", SeverityScore: 0.5}.Validate())
	assert.Error(t, Incident{ID: "inc", SeverityScore: 0.5}.Validate())
	assert.Error(t, Incident{ID: "inc", Pattern: "p", SeverityScore: 1.5}.Validate())
	assert.Error(t, Incident{ID: "inc", Pattern: "p", SeverityScore: -0.1}.Validate())
}

func TestRemediationPlan_Validate(t *testing.T) {
	good := RemediationPlan{
		IncidentID: "inc-1",
		CodePatch:  "--- a\n+++ b\n",
		TargetFile: "main.go",
		Priority:   SeverityError,
	}
	require.NoError(t, good.Validate())

	assert.Error(t, RemediationPlan{CodePatch: "x", TargetFile: "f"}.Validate())
	assert.Error(t, RemediationPlan{IncidentID: "i", TargetFile: "f"}.Validate())
	assert.Error(t, RemediationPlan{IncidentID: "i", CodePatch: "x"}.Validate())
}
