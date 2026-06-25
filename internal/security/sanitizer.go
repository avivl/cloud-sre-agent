// Package security provides a Sanitizer that redacts secrets and PII from
// text before it crosses a trust boundary — in particular, before any log
// content or prompt is sent to an LLM provider. This is a hard HIPAA gate:
// the sanitizer is deliberately conservative and prefers over-redaction to
// leaking sensitive data. Callers should treat its output as the only text
// safe to forward to a third party.
package security

import (
	"regexp"
	"strings"

	"github.com/avivl/cloud-sre-agent/internal/domain"
)

// Placeholder is the token substituted for any redacted value.
const Placeholder = "[REDACTED]"

// defaultSensitiveFields are structured field/key names whose values are
// always redacted when the sanitizer recognizes a "key: value" or
// "key=value" shape. Matching is case-insensitive.
var defaultSensitiveFields = []string{
	"password", "passwd", "pwd",
	"secret", "client_secret",
	"token", "access_token", "refresh_token", "id_token", "auth_token",
	"api_key", "apikey", "api-key",
	"authorization", "auth",
	"credential", "credentials",
	"private_key", "privatekey",
	"session", "session_id", "sessionid",
	"cookie", "set-cookie",
	"ssn",
	"dob",
	"mrn", // medical record number (PHI)
}

// rule is a single named redaction pattern applied to free text.
type rule struct {
	name string
	re   *regexp.Regexp
	// repl, when non-empty, is used as a replacement template that may
	// reference capture groups (e.g. "$1: [REDACTED]"). When empty the whole
	// match is replaced with Placeholder.
	repl string
}

// Sanitizer redacts secrets and PII from text. The zero value is not usable;
// construct one with New or NewWithFields.
type Sanitizer struct {
	rules []rule
	// fieldRE matches "<field><sep><value>" where field is one of the
	// configured sensitive field names. It is applied first so that, e.g.,
	// `password=hunter2` redacts the value regardless of its shape.
	fieldRE *regexp.Regexp
}

// New returns a Sanitizer using the default set of sensitive field names.
func New() *Sanitizer {
	return NewWithFields(nil)
}

// NewWithFields returns a Sanitizer whose structured-field redaction covers
// the default field names plus any extra names supplied. Extra names are
// matched case-insensitively. Passing nil yields the same behavior as New.
func NewWithFields(extraFields []string) *Sanitizer {
	fields := make([]string, 0, len(defaultSensitiveFields)+len(extraFields))
	fields = append(fields, defaultSensitiveFields...)
	fields = append(fields, extraFields...)

	return &Sanitizer{
		rules:   defaultRules(),
		fieldRE: buildFieldRE(fields),
	}
}

// buildFieldRE compiles a single regexp that matches any of the given field
// names followed by a separator (":" or "=", with optional surrounding
// whitespace and optional quotes around the value) and then a value run. The
// field name itself is captured so it can be preserved in the replacement.
func buildFieldRE(fields []string) *regexp.Regexp {
	escaped := make([]string, 0, len(fields))
	seen := make(map[string]struct{}, len(fields))
	for _, f := range fields {
		f = strings.TrimSpace(f)
		if f == "" {
			continue
		}
		key := strings.ToLower(f)
		if _, dup := seen[key]; dup {
			continue
		}
		seen[key] = struct{}{}
		escaped = append(escaped, regexp.QuoteMeta(f))
	}
	if len(escaped) == 0 {
		// Match nothing.
		return regexp.MustCompile(`a^`)
	}
	// (?i) case-insensitive; capture the field name and separator, then the
	// value: a quoted string or an unquoted run up to whitespace/comma/semicolon.
	pattern := `(?i)\b(` + strings.Join(escaped, "|") +
		`)(\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;]+)`
	return regexp.MustCompile(pattern)
}

// defaultRules returns the ordered free-text redaction rules. Order matters:
// the most specific / highest-confidence patterns run first so that broad
// patterns do not consume substrings the specific ones would have caught.
func defaultRules() []rule {
	return []rule{
		// Provider API-key shapes (high confidence; run before generic tokens).
		// OpenAI-style sk- keys (and sk-proj-, sk-ant- variants).
		{name: "openai_key", re: regexp.MustCompile(`\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}\b`)},
		// Google API keys.
		{name: "google_key", re: regexp.MustCompile(`\bAIza[0-9A-Za-z_-]{32,44}\b`)},
		// GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_, github_pat_).
		{name: "github_token", re: regexp.MustCompile(`\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b`)},
		// Slack tokens.
		{name: "slack_token", re: regexp.MustCompile(`\bxox[baprs]-[A-Za-z0-9-]{10,}\b`)},
		// AWS access key IDs.
		{name: "aws_access_key", re: regexp.MustCompile(`\b(?:AKIA|ASIA)[0-9A-Z]{16}\b`)},
		// Google OAuth client IDs.
		{name: "gcp_oauth_client", re: regexp.MustCompile(`\b[0-9]{6,}-[0-9a-z]{20,}\.apps\.googleusercontent\.com\b`)},
		// JWTs: three base64url segments separated by dots.
		{name: "jwt", re: regexp.MustCompile(`\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\b`)},
		// Bearer / Basic Authorization header values.
		{name: "bearer", re: regexp.MustCompile(`(?i)\b(Bearer|Basic|Token)\s+[A-Za-z0-9._~+/=-]{8,}`), repl: "$1 " + Placeholder},
		// Private-key PEM blocks.
		{name: "pem", re: regexp.MustCompile(`(?s)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----`)},

		// PHI identifiers in prose. These run before the SSN/credit-card numeric
		// rules so a labeled identifier (e.g. "MRN# 12345") is redacted as a unit
		// rather than partially consumed by a broader numeric rule.
		// MRN / medical / member identifiers written inline: "mrn: 12345",
		// "MRN#12345", "member id = X9", "patient id 778", "member# 778812". The
		// label is captured and preserved so the log stays readable; only the
		// identifier value is redacted. "mrn" matches as a bare keyword; the more
		// common English words "member"/"patient" require either an explicit "id"
		// or a "#"/":"/"="/"-" separator so prose like "member of the team" is not
		// touched.
		{
			name: "medical_id",
			re: regexp.MustCompile(`(?i)\b(` +
				`mrn\b#?\s*[:#=-]?\s*` +
				`|(?:member|patient)\s*id\b\s*[:#=-]?\s*` +
				`|(?:member|patient)\b\s*[#:=-]\s*` +
				`)\w+`),
			repl: "$1" + Placeholder,
		},
		// A date of birth referenced by label, e.g. "DOB: 1980-01-02",
		// "born 1/2/80", "date of birth = 01/02/1980". The label is preserved and
		// the date value redacted.
		{
			name: "dob",
			re:   regexp.MustCompile(`(?i)\b((?:dob|born|date\s+of\s+birth)\b\s*[:=]?\s*)\S+`),
			repl: "$1" + Placeholder,
		},

		// PII.
		// Email addresses.
		{name: "email", re: regexp.MustCompile(`\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b`)},
		// ISO dates (YYYY-MM-DD) and slashed dates (M/D/YY or MM/DD/YYYY). Dates are
		// treated as potential DOB/PHI and over-redacted per the HIPAA posture.
		{name: "date_iso", re: regexp.MustCompile(`\b\d{4}-\d{2}-\d{2}\b`)},
		{name: "date_slash", re: regexp.MustCompile(`\b\d{1,2}/\d{1,2}/\d{2,4}\b`)},
		// US SSN (NNN-NN-NNNN, with - or space separators).
		{name: "ssn", re: regexp.MustCompile(`\b\d{3}[- ]\d{2}[- ]\d{4}\b`)},
		// SSN written as 9 consecutive digits with no separators.
		{name: "ssn_plain", re: regexp.MustCompile(`\b\d{9}\b`)},
		// Credit-card-like 13-16 digit runs, optionally grouped by space/dash.
		{name: "credit_card", re: regexp.MustCompile(`\b(?:\d[ -]?){12,18}\d\b`)},
		// Phone numbers: optional +CC, then 10+ digits with common separators.
		// Requires separators or a leading + to avoid eating plain integers.
		{name: "phone", re: regexp.MustCompile(`(?:\+\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}\b`)},
	}
}

// Sanitize returns s with all detected secrets and PII replaced by
// Placeholder. It is safe to call on already-sanitized text (idempotent for
// the placeholder itself) and never returns an error.
func (z *Sanitizer) Sanitize(s string) string {
	if s == "" {
		return s
	}
	// Free-text patterns first (most-specific to least-specific within the
	// rule list). Running these before structured-field redaction means a
	// header value like `Bearer <token>` is fully redacted before the field
	// rule trims whatever remains after the field separator.
	out := s
	for _, r := range z.rules {
		if r.repl != "" {
			out = r.re.ReplaceAllString(out, r.repl)
		} else {
			out = r.re.ReplaceAllString(out, Placeholder)
		}
	}

	// Structured fields: redact the value but keep the field name so the log
	// stays readable (e.g. `api_key=[REDACTED]`).
	out = z.fieldRE.ReplaceAllStringFunc(out, func(m string) string {
		loc := fieldSepIdx(m)
		if loc < 0 {
			return Placeholder
		}
		return m[:loc] + Placeholder
	})
	return out
}

// fieldSepIdx returns the index just past the "<sep>" (": " / "=" plus
// surrounding whitespace) in a field match, i.e. where the value begins. It
// returns -1 if no separator is found.
func fieldSepIdx(m string) int {
	i := strings.IndexAny(m, ":=")
	if i < 0 {
		return -1
	}
	// Advance past the separator char and any trailing whitespace.
	i++
	for i < len(m) && (m[i] == ' ' || m[i] == '\t') {
		i++
	}
	return i
}

// SanitizeEvent returns a copy of e with its free-text and label fields run
// through Sanitize. The Labels map is copied so the input event is not
// mutated; both keys' values and the Source/Message fields are scrubbed. ID,
// Timestamp, and Severity are structural metadata and are left untouched.
func (z *Sanitizer) SanitizeEvent(e domain.LogEvent) domain.LogEvent {
	out := e
	out.Message = z.Sanitize(e.Message)
	out.Source = z.Sanitize(e.Source)
	if len(e.Labels) > 0 {
		labels := make(map[string]string, len(e.Labels))
		for k, v := range e.Labels {
			labels[k] = z.Sanitize(v)
		}
		out.Labels = labels
	}
	return out
}
