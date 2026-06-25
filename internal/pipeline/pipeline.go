// Package pipeline orchestrates the triage -> analysis -> remediation flow.
//
// The pipeline is wired entirely through ports: an llm.Provider for the three
// LLM stages, a security.Sanitizer applied to every prompt input before it
// leaves the process (a hard HIPAA gate), a CodeValidator gating the generated
// patch before delivery (NoopValidator by default), and an scm.PRTarget that
// delivers the resulting change. A flow id is propagated through ctx via obs so
// every stage's logs and spans correlate to one incident's journey.
package pipeline

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strings"

	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/avivl/cloud-sre-agent/internal/llm"
	"github.com/avivl/cloud-sre-agent/internal/obs"
	"github.com/avivl/cloud-sre-agent/internal/scm"
	"github.com/avivl/cloud-sre-agent/internal/security"
)

// Sanitizer is the prompt-input scrubber the pipeline requires. It matches the
// concrete *security.Sanitizer surface so the pipeline depends on behavior, not
// a struct, and stays testable.
type Sanitizer interface {
	Sanitize(s string) string
	SanitizeEvent(e domain.LogEvent) domain.LogEvent
}

// Deliverer delivers a change to a source-control destination. It mirrors the
// scm.PRTarget port.
type Deliverer interface {
	Name() string
	Deliver(ctx context.Context, change scm.Change) (scm.Ref, error)
}

// Pipeline holds the collaborators wired through the ports. Construct it with
// New; all fields are required except Validator (defaults to NoopValidator) and
// Logger (defaults to slog.Default).
type Pipeline struct {
	provider  llm.Provider
	sanitizer Sanitizer
	validator CodeValidator
	target    Deliverer
	logger    *slog.Logger
	// lang is the language label handed to the validator for the generated
	// patch; defaults to "go".
	lang string
}

// Option configures a Pipeline.
type Option func(*Pipeline)

// WithValidator sets the code validator. A nil validator is ignored (the
// NoopValidator default survives).
func WithValidator(v CodeValidator) Option {
	return func(p *Pipeline) {
		if v != nil {
			p.validator = v
		}
	}
}

// WithLogger sets the base logger. A nil logger is ignored.
func WithLogger(l *slog.Logger) Option {
	return func(p *Pipeline) {
		if l != nil {
			p.logger = l
		}
	}
}

// WithLang sets the language label passed to the validator. Empty is ignored.
func WithLang(lang string) Option {
	return func(p *Pipeline) {
		if lang != "" {
			p.lang = lang
		}
	}
}

// New constructs a Pipeline. provider, sanitizer, and target are required; New
// returns an error if any is nil.
func New(provider llm.Provider, sanitizer Sanitizer, target Deliverer, opts ...Option) (*Pipeline, error) {
	if provider == nil {
		return nil, errors.New("pipeline: llm provider is required")
	}
	if sanitizer == nil {
		return nil, errors.New("pipeline: sanitizer is required")
	}
	if target == nil {
		return nil, errors.New("pipeline: delivery target is required")
	}
	p := &Pipeline{
		provider:  provider,
		sanitizer: sanitizer,
		validator: NoopValidator{},
		target:    target,
		logger:    slog.Default(),
		lang:      "go",
	}
	for _, opt := range opts {
		opt(p)
	}
	return p, nil
}

// Result bundles every stage artifact plus the delivery reference, so callers
// (and tests) can inspect the full journey of one incident.
type Result struct {
	Triage      domain.TriageResult
	Analysis    domain.Analysis
	Remediation domain.RemediationPlan
	Ref         scm.Ref
}

// Process runs an incident through triage -> analysis -> remediation and
// delivers the resulting change. A flow id derived from the incident is added
// to ctx so all stage logs correlate. When triage judges the incident
// non-actionable, Process returns ErrNotActionable and does not call the later
// stages or the delivery target.
func (p *Pipeline) Process(ctx context.Context, inc domain.Incident) (Result, error) {
	if err := inc.Validate(); err != nil {
		return Result{}, fmt.Errorf("pipeline: invalid incident: %w", err)
	}

	flowID := "flow-" + inc.ID
	ctx = obs.WithFlowID(ctx, flowID)
	log := obs.LoggerFrom(ctx, p.logger)
	log.Info("pipeline: processing incident", "incident_id", inc.ID, "pattern", inc.Pattern)

	triage, err := p.triage(ctx, inc)
	if err != nil {
		return Result{}, err
	}
	log.Info("pipeline: triage complete", "category", triage.Category, "actionable", triage.Actionable, "confidence", triage.Confidence)

	if !triage.Actionable {
		return Result{Triage: triage}, ErrNotActionable
	}

	analysis, err := p.analyze(ctx, inc, triage)
	if err != nil {
		return Result{Triage: triage}, err
	}
	log.Info("pipeline: analysis complete", "confidence", analysis.Confidence)

	plan, err := p.remediate(ctx, inc, analysis)
	if err != nil {
		return Result{Triage: triage, Analysis: analysis}, err
	}
	log.Info("pipeline: remediation drafted", "target_file", plan.TargetFile)

	vr, err := p.validator.Validate(ctx, plan.CodePatch, p.lang)
	if err != nil {
		return Result{Triage: triage, Analysis: analysis, Remediation: plan}, fmt.Errorf("pipeline: validate patch: %w", err)
	}
	if !vr.OK {
		return Result{Triage: triage, Analysis: analysis, Remediation: plan},
			fmt.Errorf("%w: %s", ErrPatchRejected, strings.Join(vr.Diagnostics, "; "))
	}

	ref, err := p.target.Deliver(ctx, scm.Change{
		FilePath:    plan.TargetFile,
		Patch:       plan.CodePatch,
		Description: plan.ProposedFix,
		Severity:    plan.Priority,
	})
	if err != nil {
		return Result{Triage: triage, Analysis: analysis, Remediation: plan}, fmt.Errorf("pipeline: deliver: %w", err)
	}
	log.Info("pipeline: delivered remediation", "target", p.target.Name(), "ref_id", ref.ID)

	return Result{Triage: triage, Analysis: analysis, Remediation: plan, Ref: ref}, nil
}

// ErrNotActionable is returned by Process when triage judges the incident does
// not warrant remediation. It is not a failure; callers may treat it as a
// benign skip.
var ErrNotActionable = errors.New("pipeline: incident not actionable")

// ErrPatchRejected is returned when the CodeValidator rejects the generated
// patch.
var ErrPatchRejected = errors.New("pipeline: patch rejected by validator")

// triage runs the fast first-pass classification stage.
func (p *Pipeline) triage(ctx context.Context, inc domain.Incident) (domain.TriageResult, error) {
	schema, err := llm.SchemaFor[domain.TriageResult]()
	if err != nil {
		return domain.TriageResult{}, fmt.Errorf("pipeline: triage schema: %w", err)
	}
	req := llm.Request{
		Messages: []llm.Message{
			{Role: llm.RoleSystem, Content: p.sanitizer.Sanitize(triageSystemPrompt)},
			{Role: llm.RoleUser, Content: p.sanitizer.Sanitize(p.incidentPrompt(inc))},
		},
	}.WithSchema(schema, "TriageResult")

	resp, err := p.provider.Generate(ctx, req)
	if err != nil {
		return domain.TriageResult{}, fmt.Errorf("pipeline: triage generate: %w", err)
	}
	var out domain.TriageResult
	if err := resp.Decode(&out); err != nil {
		return domain.TriageResult{}, fmt.Errorf("pipeline: triage decode: %w", err)
	}
	out.IncidentID = inc.ID
	return out, nil
}

// analyze runs the deep root-cause analysis stage.
func (p *Pipeline) analyze(ctx context.Context, inc domain.Incident, triage domain.TriageResult) (domain.Analysis, error) {
	schema, err := llm.SchemaFor[domain.Analysis]()
	if err != nil {
		return domain.Analysis{}, fmt.Errorf("pipeline: analysis schema: %w", err)
	}
	prompt := fmt.Sprintf("%s\n\nTriage category: %s\nTriage reasoning: %s",
		p.incidentPrompt(inc), triage.Category, triage.Reasoning)
	req := llm.Request{
		Messages: []llm.Message{
			{Role: llm.RoleSystem, Content: p.sanitizer.Sanitize(analysisSystemPrompt)},
			{Role: llm.RoleUser, Content: p.sanitizer.Sanitize(prompt)},
		},
	}.WithSchema(schema, "Analysis")

	resp, err := p.provider.Generate(ctx, req)
	if err != nil {
		return domain.Analysis{}, fmt.Errorf("pipeline: analysis generate: %w", err)
	}
	var out domain.Analysis
	if err := resp.Decode(&out); err != nil {
		return domain.Analysis{}, fmt.Errorf("pipeline: analysis decode: %w", err)
	}
	out.IncidentID = inc.ID
	return out, nil
}

// remediate runs the final stage that produces a concrete code patch.
func (p *Pipeline) remediate(ctx context.Context, inc domain.Incident, analysis domain.Analysis) (domain.RemediationPlan, error) {
	schema, err := llm.SchemaFor[domain.RemediationPlan]()
	if err != nil {
		return domain.RemediationPlan{}, fmt.Errorf("pipeline: remediation schema: %w", err)
	}
	prompt := fmt.Sprintf("%s\n\nRoot cause: %s\nProposed fix: %s",
		p.incidentPrompt(inc), analysis.RootCause, analysis.ProposedFix)
	req := llm.Request{
		Messages: []llm.Message{
			{Role: llm.RoleSystem, Content: p.sanitizer.Sanitize(remediationSystemPrompt)},
			{Role: llm.RoleUser, Content: p.sanitizer.Sanitize(prompt)},
		},
	}.WithSchema(schema, "RemediationPlan")

	resp, err := p.provider.Generate(ctx, req)
	if err != nil {
		return domain.RemediationPlan{}, fmt.Errorf("pipeline: remediation generate: %w", err)
	}
	var out domain.RemediationPlan
	if err := resp.Decode(&out); err != nil {
		return domain.RemediationPlan{}, fmt.Errorf("pipeline: remediation decode: %w", err)
	}
	out.IncidentID = inc.ID
	if out.Priority == domain.SeverityUnknown {
		out.Priority = severityFromScore(inc.SeverityScore)
	}
	if err := out.Validate(); err != nil {
		return domain.RemediationPlan{}, fmt.Errorf("pipeline: remediation invalid: %w", err)
	}
	return out, nil
}

// incidentPrompt renders the incident into a prompt body using only the
// detector's synthetic, PHI-free fields (Pattern, Summary, severity score) plus
// derived counts and affected-service identifiers. Raw sample-event message and
// source bodies are deliberately NOT included: they are operator log text that
// may carry PHI, and the synthetic Pattern/Summary already convey what the model
// needs. This is a hard HIPAA gate (the outer Sanitize call is a second line of
// defense, not the primary one).
func (p *Pipeline) incidentPrompt(inc domain.Incident) string {
	var b strings.Builder
	fmt.Fprintf(&b, "Incident %s\nPattern: %s\nSeverity score: %.2f\nSummary: %s\n",
		inc.ID, inc.Pattern, inc.SeverityScore, inc.Summary)
	if len(inc.AffectedServices) > 0 {
		fmt.Fprintf(&b, "Affected services: %s\n", strings.Join(inc.AffectedServices, ", "))
	}
	if n := len(inc.SampleEvents); n > 0 {
		// Report only an aggregate severity breakdown of the sample events — never
		// their raw message/source bodies — so no free-text log content reaches
		// the model.
		fmt.Fprintf(&b, "Sample events: %d (%s)\n", n, severityBreakdown(inc.SampleEvents))
	}
	return b.String()
}

// severityBreakdown summarizes a set of events as a compact, PHI-free count per
// severity label, e.g. "error: 3, warning: 1". Severities are reported in
// descending urgency.
func severityBreakdown(events []domain.LogEvent) string {
	counts := make(map[domain.Severity]int, len(events))
	for _, e := range events {
		counts[e.Severity]++
	}
	order := []domain.Severity{
		domain.SeverityCritical, domain.SeverityError, domain.SeverityWarning,
		domain.SeverityInfo, domain.SeverityDebug, domain.SeverityUnknown,
	}
	parts := make([]string, 0, len(counts))
	for _, sev := range order {
		if c := counts[sev]; c > 0 {
			parts = append(parts, fmt.Sprintf("%s: %d", sev, c))
		}
	}
	return strings.Join(parts, ", ")
}

// severityFromScore maps a [0,1] severity score to a domain.Severity used as
// the remediation priority when the model leaves it unset.
func severityFromScore(score float64) domain.Severity {
	switch {
	case score >= 0.9:
		return domain.SeverityCritical
	case score >= 0.5:
		return domain.SeverityError
	case score >= 0.2:
		return domain.SeverityWarning
	default:
		return domain.SeverityInfo
	}
}

const triageSystemPrompt = `You are an SRE triage assistant. Classify the incident: its category, severity, ` +
	`whether it is actionable (warrants a code fix), your confidence, brief reasoning, and concrete next actions. ` +
	`Respond only with the requested JSON.`

const analysisSystemPrompt = `You are an SRE root-cause analyst. Given an incident and its triage, determine the most ` +
	`likely root cause and a proposed fix at a high level, with key supporting points and your confidence. ` +
	`Respond only with the requested JSON.`

const remediationSystemPrompt = `You are an SRE remediation engineer. Produce a concrete code patch that addresses the ` +
	`root cause. Include the target file path, a unified-diff code patch, a short proposed-fix description, an ` +
	`estimated effort, and restate the root-cause analysis. Respond only with the requested JSON.`

// compile-time check that the concrete sanitizer satisfies the pipeline's
// Sanitizer interface, and that the scm target satisfies Deliverer.
var (
	_ Sanitizer = (*security.Sanitizer)(nil)
	_ Deliverer = (scm.PRTarget)(nil)
)
