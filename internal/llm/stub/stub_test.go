package stub

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/llm"
)

func TestProvider_Name(t *testing.T) {
	assert.Equal(t, "stub", New().Name())
}

// schemaNameFor mirrors the pipeline: it builds the schema for T and returns the
// schema name the pipeline attaches for that stage, so the stub is exercised
// exactly as in production wiring.
func generate(t *testing.T, schema []byte, name string) llm.Response {
	t.Helper()
	req := llm.Request{
		Messages: []llm.Message{{Role: llm.RoleUser, Content: "go"}},
	}.WithSchema(schema, name)
	resp, err := New().Generate(context.Background(), req)
	require.NoError(t, err)
	require.NotEmpty(t, resp.Text)
	return resp
}

// TestTriageDecodes asserts the triage stage's structured output decodes into a
// domain.TriageResult and carries the actionable flag the pipeline needs to
// advance to later stages.
func TestTriageDecodes(t *testing.T) {
	schema, err := llm.SchemaFor[domain.TriageResult]()
	require.NoError(t, err)

	resp := generate(t, schema, "TriageResult")

	var out domain.TriageResult
	require.NoError(t, resp.Decode(&out))
	assert.True(t, out.Actionable, "triage must be actionable so the pipeline proceeds offline")
	assert.True(t, out.Severity.Valid())
}

// TestAnalysisDecodes asserts the analysis stage's structured output decodes
// into a domain.Analysis with the required free-text fields populated.
func TestAnalysisDecodes(t *testing.T) {
	schema, err := llm.SchemaFor[domain.Analysis]()
	require.NoError(t, err)

	resp := generate(t, schema, "Analysis")

	var out domain.Analysis
	require.NoError(t, resp.Decode(&out))
	assert.NotEmpty(t, out.RootCause)
	assert.NotEmpty(t, out.ProposedFix)
}

// TestRemediationDecodes asserts the remediation stage's structured output
// decodes into a domain.RemediationPlan and, after the pipeline sets the
// server-owned IncidentID, passes domain validation (non-empty code patch and
// target file).
func TestRemediationDecodes(t *testing.T) {
	schema, err := llm.SchemaFor[domain.RemediationPlan]()
	require.NoError(t, err)

	resp := generate(t, schema, "RemediationPlan")

	var out domain.RemediationPlan
	require.NoError(t, resp.Decode(&out))
	assert.NotEmpty(t, out.CodePatch)
	assert.NotEmpty(t, out.TargetFile)
	assert.True(t, out.Priority.Valid())

	// The pipeline sets IncidentID after decode; emulate it and confirm the plan
	// then satisfies domain validation.
	out.IncidentID = "inc-1"
	assert.NoError(t, out.Validate())
}

// TestUnknownSchemaDecodes asserts an empty/unknown schema name still yields a
// valid JSON object that decodes cleanly into a domain type.
func TestUnknownSchemaDecodes(t *testing.T) {
	resp := generate(t, nil, "")
	var out domain.TriageResult
	assert.NoError(t, resp.Decode(&out))
}

// TestContextCancelled asserts a cancelled context is honored.
func TestContextCancelled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err := New().Generate(ctx, llm.Request{Messages: []llm.Message{{Role: llm.RoleUser, Content: "x"}}})
	assert.Error(t, err)
}
