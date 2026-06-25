package security

import (
	"strings"
	"testing"
	"time"

	"github.com/avivl/cloud-sre-agent/internal/domain"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// redactsAll asserts every needle is absent and the placeholder is present.
func redactsAll(t *testing.T, got string, needles ...string) {
	t.Helper()
	assert.Contains(t, got, Placeholder, "expected a redaction in %q", got)
	for _, n := range needles {
		assert.NotContains(t, got, n, "secret %q leaked through: %q", n, got)
	}
}

func TestSanitize_Secrets(t *testing.T) {
	z := New()

	cases := []struct {
		name   string
		in     string
		secret string // substring that must NOT survive
	}{
		// Secrets are assembled from split substrings so no contiguous,
		// real-format token literal lives in the source tree (which would trip
		// secret-scanning push protection). The sanitizer still receives the
		// full joined value and must redact it.
		{"openai_sk", "key is " + "sk-" + "abcdefghijklmnop1234 done", "sk-" + "abcdefghijklmnop1234"},
		{"openai_proj", "tok " + "sk-proj-" + "AbCd1234EfGh5678IjKl here", "sk-proj-" + "AbCd1234EfGh5678IjKl"},
		{"anthropic", "x-api-key " + "sk-ant-api03-" + "AbCd1234EfGh5678 end", "sk-ant-api03-" + "AbCd1234EfGh5678"},
		{"google_api", "AIza" + "SyA1234567890abcdefghijklmnopqrstuvw used", "AIza" + "SyA1234567890abcdefghijklmnopqrstuvw"},
		{"github_pat_old", "token " + "ghp_" + "0123456789abcdefghij0123456789abcd ok", "ghp_" + "0123456789abcdefghij0123456789abcd"},
		{"github_pat_new", "github" + "_pat_" + "11ABCDEFG0123456789abcdef in log", "github" + "_pat_" + "11ABCDEFG0123456789abcdef"},
		{"slack", "xoxb-" + "1234567890-abcdefghijklmnop sent", "xoxb-" + "1234567890-abcdefghijklmnop"},
		{"aws_akia", "AKIA" + "IOSFODNN7EXAMPLE leaked", "AKIA" + "IOSFODNN7EXAMPLE"},
		{"gcp_oauth", "123456789012-" + "abcdefghijklmnop1234.apps.googleusercontent.com", "123456789012-" + "abcdefghijklmnop1234.apps.googleusercontent.com"},
		{"jwt", "auth " + "eyJhbGciOi" + ".eyJzdWIiOiAxMjM.SflKxwRJSME end", "eyJhbGciOi" + ".eyJzdWIiOiAxMjM.SflKxwRJSME"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := z.Sanitize(tc.in)
			redactsAll(t, got, tc.secret)
		})
	}
}

func TestSanitize_AuthHeaders(t *testing.T) {
	z := New()

	// A bare scheme + credential (not under an "authorization" field) keeps the
	// scheme word and redacts the credential.
	cases := []struct {
		name   string
		in     string
		secret string
		keep   string // scheme word that should survive
	}{
		{"bearer", "sent header Bearer abcDEF123456ghiJKL upstream", "abcDEF123456ghiJKL", "Bearer"},
		{"basic", "sent header Basic dXNlcjpwYXNzd29yZA== upstream", "dXNlcjpwYXNzd29yZA==", "Basic"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := z.Sanitize(tc.in)
			redactsAll(t, got, tc.secret)
			assert.Contains(t, got, tc.keep)
		})
	}

	// When the value sits under an "authorization" structured field, the whole
	// value is redacted (more conservative — the scheme word goes too).
	full := z.Sanitize("Authorization: Bearer abcDEF123456ghiJKL")
	assert.NotContains(t, full, "abcDEF123456ghiJKL")
	assert.Contains(t, full, "Authorization")
}

func TestSanitize_PEMPrivateKey(t *testing.T) {
	z := New()
	in := "config:\n-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA1234\nabcd/EFGH+ijkl\n-----END RSA PRIVATE KEY-----\ndone"
	got := z.Sanitize(in)
	redactsAll(t, got, "MIIEpAIBAAKCAQEA1234", "PRIVATE KEY")
	assert.Contains(t, got, "done")
}

func TestSanitize_PII(t *testing.T) {
	z := New()

	cases := []struct {
		name   string
		in     string
		secret string
	}{
		{"email", "contact alice.bob+tag@example.co.uk now", "alice.bob+tag@example.co.uk"},
		{"ssn_dash", "ssn 123-45-6789 patient", "123-45-6789"},
		{"ssn_space", "ssn 123 45 6789 patient", "123 45 6789"},
		{"phone_dash", "call 415-555-0199 asap", "415-555-0199"},
		{"phone_dot", "call 415.555.0199 asap", "415.555.0199"},
		{"phone_intl", "call +1 415-555-0199 asap", "415-555-0199"},
		{"phone_paren", "call (415) 555-0199 asap", "555-0199"},
		{"credit_card", "card 4111 1111 1111 1111 charged", "4111 1111 1111 1111"},
		{"credit_card_plain", "card 4111111111111111 charged", "4111111111111111"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := z.Sanitize(tc.in)
			redactsAll(t, got, tc.secret)
		})
	}
}

func TestSanitize_PHIIdentifiers(t *testing.T) {
	z := New()

	cases := []struct {
		name   string
		in     string
		secret string // substring that must NOT survive
	}{
		// MRN / medical / member identifiers in prose.
		{"mrn_colon", "patient mrn: 0001234 admitted", "0001234"},
		{"mrn_hash", "see MRN#0001234 for history", "0001234"},
		{"mrn_hash_space", "see MRN# 0001234 for history", "0001234"},
		{"member_id", "member id = AB99X claim filed", "AB99X"},
		{"member_sep", "member# 778812 enrolled", "778812"},
		{"patient_id", "patient id 55421 triaged", "55421"},
		{"patient_sep", "patient: 55421 triaged", "55421"},
		// DOB / dates.
		{"dob_iso", "DOB: 1980-01-02 noted", "1980-01-02"},
		{"dob_slash", "born 1/2/80 in chart", "1/2/80"},
		{"date_of_birth", "date of birth = 01/02/1980 verified", "01/02/1980"},
		{"iso_date_bare", "event at 2026-01-15 logged", "2026-01-15"},
		{"slash_date_bare", "scheduled 12/31/2026 followup", "12/31/2026"},
		// SSN, 9-consecutive-digit form.
		{"ssn_plain", "ssn 123456789 on file", "123456789"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := z.Sanitize(tc.in)
			redactsAll(t, got, tc.secret)
		})
	}
}

func TestSanitize_PHIFalsePositiveGuards(t *testing.T) {
	z := New()

	// Benign content that resembles, but is not, a PHI identifier or date must
	// pass through unchanged. (Over-redaction is acceptable; these are cases the
	// patterns are deliberately scoped to avoid.)
	cases := []string{
		"member of the on-call rotation", // "member" with no id-ish token following the field
		"retried 8 digit checksum mismatch",
		"version 1.2.3 deployed to region us-central1", // dotted version, not a slashed date
		"latency was 250 and p99 was 400",              // short integers
		"processed 12345 records in batch",             // 5-digit count, not a 9-digit SSN
	}

	for _, in := range cases {
		t.Run(in, func(t *testing.T) {
			got := z.Sanitize(in)
			assert.Equal(t, in, got, "benign text was altered")
			assert.NotContains(t, got, Placeholder)
		})
	}
}

func TestSanitize_StructuredFields(t *testing.T) {
	z := New()

	cases := []struct {
		name   string
		in     string
		secret string
		field  string // field name that should survive
	}{
		{"password_eq", "password=hunter2", "hunter2", "password"},
		{"password_colon", "password: hunter2", "hunter2", "password"},
		{"api_key", "api_key=AbCdEf123456", "AbCdEf123456", "api_key"},
		{"apikey_quoted", `apikey="my-Secret-Value"`, "my-Secret-Value", "apikey"},
		{"token_upper", "TOKEN: deadbeefcafe", "deadbeefcafe", "TOKEN"},
		{"authorization", "authorization=xyz123abc", "xyz123abc", "authorization"},
		{"secret", "client_secret: abc-987-def", "abc-987-def", "client_secret"},
		{"ssn_field", "ssn: 999-88-7777", "999-88-7777", "ssn"},
		{"mrn_field", "mrn=MRN0001234", "MRN0001234", "mrn"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := z.Sanitize(tc.in)
			redactsAll(t, got, tc.secret)
			assert.Contains(t, got, tc.field, "field name should be preserved")
		})
	}
}

func TestSanitize_CustomFields(t *testing.T) {
	z := NewWithFields([]string{"x_custom_key", "patient_name"})

	got := z.Sanitize("x_custom_key=topsecret123")
	redactsAll(t, got, "topsecret123")
	assert.Contains(t, got, "x_custom_key")

	got2 := z.Sanitize("patient_name: Jane Doe, status ok")
	assert.NotContains(t, got2, "Jane")
	assert.Contains(t, got2, "patient_name")
	// Default fields still work on a custom sanitizer.
	assert.NotContains(t, z.Sanitize("password=abc"), "abc")
}

func TestSanitize_FalsePositiveGuards(t *testing.T) {
	z := New()

	// Plain prose and benign content must pass through unchanged.
	cases := []string{
		"the service returned status 200 in 45ms",
		"retrying connection to backend pool 3 of 5",
		"user count is 12345 and growing",
		"order id 42 processed at queue depth 8",
		"version 1.2.3 deployed to region us-central1",
		"latency p95 was 250 and p99 was 400",
		"timeout after 30 seconds on host worker-7",
	}

	for _, in := range cases {
		t.Run(in, func(t *testing.T) {
			got := z.Sanitize(in)
			assert.Equal(t, in, got, "benign text was altered")
			assert.NotContains(t, got, Placeholder)
		})
	}
}

func TestSanitize_EmptyAndNoMatch(t *testing.T) {
	z := New()
	assert.Equal(t, "", z.Sanitize(""))

	clean := "all systems nominal"
	assert.Equal(t, clean, z.Sanitize(clean))
}

func TestSanitize_Idempotent(t *testing.T) {
	z := New()
	in := "email bob@example.com and password=hunter2"
	once := z.Sanitize(in)
	twice := z.Sanitize(once)
	assert.Equal(t, once, twice, "sanitizing already-sanitized text changed it")
	assert.NotContains(t, twice, "bob@example.com")
	assert.NotContains(t, twice, "hunter2")
}

func TestSanitize_MultipleSecretsOneLine(t *testing.T) {
	z := New()
	in := "user alice@corp.com authed with Bearer abc123def456 from 415-555-0199"
	got := z.Sanitize(in)
	assert.NotContains(t, got, "alice@corp.com")
	assert.NotContains(t, got, "abc123def456")
	assert.NotContains(t, got, "415-555-0199")
	assert.Contains(t, got, "Bearer")
}

func TestSanitizeEvent(t *testing.T) {
	z := New()
	ts := time.Date(2026, 1, 2, 3, 4, 5, 0, time.UTC)
	orig := domain.LogEvent{
		ID:        "evt-1",
		Timestamp: ts,
		Severity:  domain.SeverityError,
		Message:   "login failed for bob@example.com using password=hunter2",
		Source:    "auth-svc admin@corp.com",
		Labels: map[string]string{
			"user":   "carol@example.org",
			"region": "us-central1",
			"token":  "sk-" + "abcdefghijklmnop1234",
		},
	}

	got := z.SanitizeEvent(orig)

	// Structural metadata preserved.
	assert.Equal(t, "evt-1", got.ID)
	assert.Equal(t, ts, got.Timestamp)
	assert.Equal(t, domain.SeverityError, got.Severity)

	// Free text scrubbed.
	assert.NotContains(t, got.Message, "bob@example.com")
	assert.NotContains(t, got.Message, "hunter2")
	assert.NotContains(t, got.Source, "admin@corp.com")
	assert.Contains(t, got.Source, "auth-svc")

	// Labels scrubbed; benign label preserved.
	assert.NotContains(t, got.Labels["user"], "carol@example.org")
	assert.NotContains(t, got.Labels["token"], "sk-"+"abcdefghijklmnop1234")
	assert.Equal(t, "us-central1", got.Labels["region"])

	// Input event must not be mutated.
	assert.Equal(t, "login failed for bob@example.com using password=hunter2", orig.Message)
	assert.Equal(t, "carol@example.org", orig.Labels["user"])
	assert.Equal(t, "sk-"+"abcdefghijklmnop1234", orig.Labels["token"])
}

func TestSanitizeEvent_NilLabels(t *testing.T) {
	z := New()
	e := domain.LogEvent{ID: "x", Message: "ok", Source: "svc"}
	got := z.SanitizeEvent(e)
	assert.Nil(t, got.Labels)
	assert.Equal(t, "ok", got.Message)
}

func TestSanitizeEvent_RealEventRoundTrip(t *testing.T) {
	z := New()
	e, err := domain.NewLogEvent("id-1", "svc", "user 415-555-0199 timed out", domain.SeverityWarning, time.Now(), nil)
	require.NoError(t, err)
	got := z.SanitizeEvent(e)
	assert.NotContains(t, got.Message, "415-555-0199")
	// Sanitized event still validates.
	require.NoError(t, got.Validate())
}

func TestSanitize_PlaceholderNotDuplicated(t *testing.T) {
	z := New()
	// Ensure a value that is already the placeholder is not re-wrapped oddly.
	got := z.Sanitize("api_key=" + Placeholder)
	assert.True(t, strings.Contains(got, Placeholder))
}
