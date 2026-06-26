// Package stub implements a NON-PRODUCTION, offline llm.Provider for local
// development, dogfooding, and CI. It makes NO network calls and contacts no
// external service, so it is exempt from the external-disclosure (BAA) gate in
// config validation.
//
// Generate returns a DETERMINISTIC, schema-VALID response. When the request
// carries a structured-output schema (Request.SchemaName, set by the pipeline
// to "TriageResult", "Analysis", or "RemediationPlan"), the provider emits a
// fixed JSON object whose shape matches that domain type, so the pipeline's
// Response.Decode succeeds for every stage with no real model. The canned
// values are chosen so the pipeline flows end to end offline: triage is
// actionable, and the remediation plan carries a non-empty code patch and
// target file (the fields domain.RemediationPlan.Validate requires).
//
// This provider produces canned, meaningless text — it MUST NOT be used in
// production. Select it only for offline/CI runs.
package stub

import (
	"context"
	"encoding/json"

	"github.com/avivl/cloud-sre-agent/internal/llm"
)

// providerName is the stable identifier reported by Name.
const providerName = "stub"

// Schema names the pipeline attaches per stage (llm.Request.SchemaName). They
// are the dispatch keys for the canned response bodies below.
const (
	schemaTriage      = "TriageResult"
	schemaAnalysis    = "Analysis"
	schemaRemediation = "RemediationPlan"
)

// Canned, deterministic structured-output bodies, one per pipeline stage. Each
// is valid JSON for the matching domain type's prompt-facing schema (the
// server-owned IncidentID field is json:"-" and intentionally absent). Severity
// fields use the lowercase string labels domain.Severity marshals to.
const (
	triageJSON = `{` +
		`"category":"stub",` +
		`"severity":"info",` +
		`"confidence":1,` +
		`"actionable":true,` +
		`"reasoning":"stub provider: deterministic offline triage",` +
		`"next_actions":["review stub output"]` +
		`}`

	analysisJSON = `{` +
		`"root_cause":"stub provider: deterministic offline root cause",` +
		`"proposed_fix":"stub provider: no real fix",` +
		`"key_points":["offline stub"],` +
		`"confidence":1` +
		`}`

	remediationJSON = `{` +
		`"root_cause_analysis":"stub provider: deterministic offline analysis",` +
		`"proposed_fix":"stub provider: no real fix",` +
		`"code_patch":"// stub patch: no-op (non-production offline provider)\n",` +
		`"priority":"info",` +
		`"estimated_effort":"none",` +
		`"target_file":"stub.txt"` +
		`}`
)

// Provider is the offline, deterministic llm.Provider used for dev/CI.
type Provider struct{}

// compile-time assurance the port is satisfied.
var _ llm.Provider = (*Provider)(nil)

// New constructs a stub Provider. It takes no configuration: there is no model,
// host, or key — the provider is fully offline.
func New() *Provider { return &Provider{} }

// Name reports the provider identifier.
func (*Provider) Name() string { return providerName }

// Generate returns a deterministic, schema-valid Response for req. It dispatches
// on req.SchemaName to the canned body for that pipeline stage; an empty or
// unrecognized schema name yields an empty JSON object, which still decodes
// cleanly into any of the domain structured-output types. No network call is
// made and ctx is honored only for cancellation.
func (*Provider) Generate(ctx context.Context, req llm.Request) (llm.Response, error) {
	if err := ctx.Err(); err != nil {
		return llm.Response{}, err
	}

	text := responseFor(req.SchemaName)
	return llm.Response{
		Text:         text,
		Model:        providerName,
		FinishReason: "stop",
	}, nil
}

// responseFor returns the canned JSON body for a given schema name. Unknown or
// empty names fall back to an empty object, which is valid JSON that decodes
// into any domain type (all fields are optional at unmarshal time).
func responseFor(schemaName string) string {
	switch schemaName {
	case schemaTriage:
		return triageJSON
	case schemaAnalysis:
		return analysisJSON
	case schemaRemediation:
		return remediationJSON
	default:
		return "{}"
	}
}

// ensure the canned bodies are well-formed JSON at package init in non-optimized
// builds; this is a cheap guard against typos in the literals above.
var _ = func() bool {
	for _, s := range []string{triageJSON, analysisJSON, remediationJSON} {
		if !json.Valid([]byte(s)) {
			panic("stub: canned response is not valid JSON")
		}
	}
	return true
}()
