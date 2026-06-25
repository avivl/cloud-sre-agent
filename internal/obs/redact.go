package obs

import "log/slog"

// RedactedPlaceholder replaces any value flagged as sensitive in logs/traces.
const RedactedPlaceholder = "[REDACTED]"

// sensitiveKeys are log attribute keys whose values must never appear in
// structured output. Raw log payloads, prompts, and credentials live here so
// PHI/secrets do not leak into logs or traces.
var sensitiveKeys = map[string]struct{}{
	"raw":      {},
	"payload":  {},
	"prompt":   {},
	"message":  {},
	"body":     {},
	"content":  {},
	"token":    {},
	"api_key":  {},
	"apikey":   {},
	"secret":   {},
	"password": {},
	// error strings and source identifiers can echo raw log content / PHI, so
	// their values are masked in structured output as well. "err" is the same
	// class as "error"; both are masked so no call site can opt out by key name.
	"error":  {},
	"err":    {},
	"source": {},
}

// redactAttr is a slog ReplaceAttr hook that masks the value of any attribute
// whose key is sensitive. Group keys are left intact.
func redactAttr(_ []string, a slog.Attr) slog.Attr {
	if _, ok := sensitiveKeys[a.Key]; ok && a.Value.Kind() != slog.KindGroup {
		return slog.String(a.Key, RedactedPlaceholder)
	}
	return a
}

// Redacted wraps a value with a key known to be redacted, for callers that
// want to log a payload-bearing field by an explicit sensitive key.
func Redacted(key string, value any) slog.Attr {
	if _, ok := sensitiveKeys[key]; ok {
		return slog.String(key, RedactedPlaceholder)
	}
	return slog.Any(key, value)
}
