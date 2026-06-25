package pipeline

import (
	"context"
	"encoding/json"
	"errors"
	"testing"

	"github.com/stretchr/testify/require"

	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/llm"
	"github.com/avivl/cloud-sre-agent/internal/scm"
	"github.com/avivl/cloud-sre-agent/internal/security"
)

// mockProvider returns canned JSON keyed by the schema name on the request, so
// each stage gets a deterministic, decodable response. No network.
type mockProvider struct {
	byName map[string]string
	err    error
	calls  []llm.Request
}

func (m *mockProvider) Name() string { return "mock" }

func (m *mockProvider) Generate(_ context.Context, req llm.Request) (llm.Response, error) {
	m.calls = append(m.calls, req)
	if m.err != nil {
		return llm.Response{}, m.err
	}
	text, ok := m.byName[req.SchemaName]
	if !ok {
		return llm.Response{}, errors.New("mock: no canned response for schema " + req.SchemaName)
	}
	return llm.Response{Text: text, Model: "mock"}, nil
}

func mustJSON(t *testing.T, v any) string {
	t.Helper()
	b, err := json.Marshal(v)
	require.NoError(t, err)
	return string(b)
}

// recordingTarget captures the delivered change.
type recordingTarget struct {
	got *scm.Change
	err error
}

func (r *recordingTarget) Name() string { return "recording" }

func (r *recordingTarget) Deliver(_ context.Context, c scm.Change) (scm.Ref, error) {
	if r.err != nil {
		return scm.Ref{}, r.err
	}
	r.got = &c
	return scm.Ref{ID: "ref-1", URL: "file:///out/ref-1.patch"}, nil
}

func sampleIncident() domain.Incident {
	return domain.Incident{
		ID:            "incident-1",
		Pattern:       "elevated-error-rate",
		SeverityScore: 0.8,
		Summary:       "lots of errors",
		SampleEvents: []domain.LogEvent{
			{ID: "e1", Severity: domain.SeverityError, Message: "db timeout for user@example.com", Source: "api"},
		},
		AffectedServices: []string{"api"},
	}
}

func actionableProvider(t *testing.T) *mockProvider {
	t.Helper()
	return &mockProvider{byName: map[string]string{
		"TriageResult": mustJSON(t, domain.TriageResult{
			Category: "database", Severity: domain.SeverityError, Confidence: 0.9, Actionable: true, Reasoning: "timeouts",
		}),
		"Analysis": mustJSON(t, domain.Analysis{
			RootCause: "connection pool exhausted", ProposedFix: "raise pool size", Confidence: 0.85,
		}),
		"RemediationPlan": mustJSON(t, domain.RemediationPlan{
			RootCauseAnalysis: "pool exhausted",
			ProposedFix:       "bump max conns",
			CodePatch:         "--- a/db.go\n+++ b/db.go\n@@ -1 +1 @@\n-max=10\n+max=50\n",
			TargetFile:        "db.go",
			EstimatedEffort:   "1h",
		}),
	}}
}

func TestProcess_HappyPath(t *testing.T) {
	prov := actionableProvider(t)
	tgt := &recordingTarget{}
	p, err := New(prov, security.New(), tgt)
	require.NoError(t, err)

	res, err := p.Process(context.Background(), sampleIncident())
	require.NoError(t, err)

	// Three LLM stages, in order, each schema-constrained.
	require.Len(t, prov.calls, 3)
	require.Equal(t, "TriageResult", prov.calls[0].SchemaName)
	require.Equal(t, "Analysis", prov.calls[1].SchemaName)
	require.Equal(t, "RemediationPlan", prov.calls[2].SchemaName)
	for _, c := range prov.calls {
		require.NotEmpty(t, c.Schema)
	}

	// IncidentID stamped on every artifact.
	require.Equal(t, "incident-1", res.Triage.IncidentID)
	require.Equal(t, "incident-1", res.Analysis.IncidentID)
	require.Equal(t, "incident-1", res.Remediation.IncidentID)

	// Delivered change carries the patch and target.
	require.NotNil(t, tgt.got)
	require.Equal(t, "db.go", tgt.got.FilePath)
	require.Contains(t, tgt.got.Patch, "max=50")
	require.Equal(t, "ref-1", res.Ref.ID)
}

func TestProcess_OmitsRawSampleEventBodies(t *testing.T) {
	prov := actionableProvider(t)
	p, err := New(prov, security.New(), &recordingTarget{})
	require.NoError(t, err)

	_, err = p.Process(context.Background(), sampleIncident())
	require.NoError(t, err)

	// The sample event carried a raw message ("db timeout for user@example.com").
	// The prompt must NOT include that body at all — only synthetic, PHI-free
	// fields plus an aggregate severity breakdown reach the model.
	for _, c := range prov.calls {
		userPrompt := c.Messages[1].Content
		require.NotContains(t, userPrompt, "user@example.com", "PHI-bearing message leaked")
		require.NotContains(t, userPrompt, "db timeout", "raw message body leaked")
		// The aggregate breakdown is present instead.
		require.Contains(t, userPrompt, "Sample events: 1")
		require.Contains(t, userPrompt, "error: 1")
	}
}

func TestProcess_SanitizesPromptInputs(t *testing.T) {
	// Even though raw event bodies are dropped, the synthetic incident fields are
	// still routed through the sanitizer as a second line of defense. A summary
	// that somehow carried a secret must be scrubbed before reaching the model.
	prov := actionableProvider(t)
	p, err := New(prov, security.New(), &recordingTarget{})
	require.NoError(t, err)

	inc := sampleIncident()
	inc.Summary = "spike after deploy, token sk-abcdefghijklmnop1234 in config"
	_, err = p.Process(context.Background(), inc)
	require.NoError(t, err)

	userPrompt := prov.calls[0].Messages[1].Content
	require.Contains(t, userPrompt, security.Placeholder)
	require.NotContains(t, userPrompt, "sk-abcdefghijklmnop1234")
}

func TestProcess_NotActionableSkipsLaterStages(t *testing.T) {
	prov := &mockProvider{byName: map[string]string{
		"TriageResult": mustJSON(t, domain.TriageResult{
			Category: "noise", Actionable: false, Confidence: 0.95, Reasoning: "transient",
		}),
	}}
	tgt := &recordingTarget{}
	p, err := New(prov, security.New(), tgt)
	require.NoError(t, err)

	res, err := p.Process(context.Background(), sampleIncident())
	require.ErrorIs(t, err, ErrNotActionable)
	require.Len(t, prov.calls, 1) // only triage ran
	require.Nil(t, tgt.got)       // nothing delivered
	require.False(t, res.Triage.Actionable)
}

// rejectingValidator rejects every patch.
type rejectingValidator struct{}

func (rejectingValidator) Validate(_ context.Context, _ string, _ string) (ValidationResult, error) {
	return ValidationResult{OK: false, Diagnostics: []string{"syntax error"}}, nil
}

func TestProcess_PatchRejectedNotDelivered(t *testing.T) {
	prov := actionableProvider(t)
	tgt := &recordingTarget{}
	p, err := New(prov, security.New(), tgt, WithValidator(rejectingValidator{}))
	require.NoError(t, err)

	_, err = p.Process(context.Background(), sampleIncident())
	require.ErrorIs(t, err, ErrPatchRejected)
	require.Contains(t, err.Error(), "syntax error")
	require.Nil(t, tgt.got)
}

func TestProcess_ProviderError(t *testing.T) {
	prov := &mockProvider{err: errors.New("boom"), byName: map[string]string{}}
	p, err := New(prov, security.New(), &recordingTarget{})
	require.NoError(t, err)

	_, err = p.Process(context.Background(), sampleIncident())
	require.Error(t, err)
	require.Contains(t, err.Error(), "triage generate")
}

func TestProcess_InvalidIncident(t *testing.T) {
	p, err := New(actionableProvider(t), security.New(), &recordingTarget{})
	require.NoError(t, err)

	_, err = p.Process(context.Background(), domain.Incident{}) // missing id/pattern
	require.Error(t, err)
	require.Contains(t, err.Error(), "invalid incident")
}

func TestNew_Validation(t *testing.T) {
	_, err := New(nil, security.New(), &recordingTarget{})
	require.Error(t, err)
	_, err = New(actionableProvider(t), nil, &recordingTarget{})
	require.Error(t, err)
	_, err = New(actionableProvider(t), security.New(), nil)
	require.Error(t, err)
}

func TestStructuredSchema_SeverityIsStringEnum(t *testing.T) {
	// The schema the pipeline sends for each stage must advertise severity/priority
	// as a string enum of the real labels, not a bare integer, and must not request
	// the server-owned incident_id.
	for _, sc := range []struct {
		name   string
		schema func() (json.RawMessage, error)
		field  string
	}{
		{"TriageResult", llm.SchemaFor[domain.TriageResult], "severity"},
		{"RemediationPlan", llm.SchemaFor[domain.RemediationPlan], "priority"},
	} {
		t.Run(sc.name, func(t *testing.T) {
			raw, err := sc.schema()
			require.NoError(t, err)

			var s struct {
				Properties map[string]struct {
					Type string `json:"type"`
					Enum []any  `json:"enum"`
				} `json:"properties"`
				Required []string `json:"required"`
			}
			require.NoError(t, json.Unmarshal(raw, &s))

			f, ok := s.Properties[sc.field]
			require.True(t, ok, "schema missing %q field", sc.field)
			require.Equal(t, "string", f.Type)
			require.ElementsMatch(t,
				[]any{"debug", "info", "warning", "error", "critical"}, f.Enum)

			// incident_id is server-owned and must not appear.
			_, hasID := s.Properties["incident_id"]
			require.False(t, hasID, "incident_id should not be in the prompt-facing schema")
			require.NotContains(t, s.Required, "incident_id")
		})
	}
}

func TestProcess_DeliveryError(t *testing.T) {
	prov := actionableProvider(t)
	tgt := &recordingTarget{err: errors.New("disk full")}
	p, err := New(prov, security.New(), tgt)
	require.NoError(t, err)

	_, err = p.Process(context.Background(), sampleIncident())
	require.Error(t, err)
	require.Contains(t, err.Error(), "deliver")
}
