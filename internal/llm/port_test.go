package llm

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestResponse_Decode(t *testing.T) {
	type target struct {
		Cause string `json:"cause"`
		Score int    `json:"score"`
	}
	resp := Response{Text: `{"cause":"oom","score":3}`}
	var out target
	require.NoError(t, resp.Decode(&out))
	assert.Equal(t, "oom", out.Cause)
	assert.Equal(t, 3, out.Score)

	assert.Error(t, Response{Text: ""}.Decode(&out))
	assert.Error(t, Response{Text: "not json"}.Decode(&out))
}

func TestRequest_WithSchema(t *testing.T) {
	r := Request{Messages: []Message{{Role: RoleUser, Content: "hi"}}}
	r = r.WithSchema(json.RawMessage(`{"type":"object"}`), "out")
	assert.Equal(t, "out", r.SchemaName)
	assert.JSONEq(t, `{"type":"object"}`, string(r.Schema))
}

func TestSchemaFor(t *testing.T) {
	type result struct {
		Cause string `json:"cause"`
		Score int    `json:"score"`
	}
	raw, err := SchemaFor[result]()
	require.NoError(t, err)

	var m map[string]any
	require.NoError(t, json.Unmarshal(raw, &m))
	assert.Equal(t, "object", m["type"])
	props, ok := m["properties"].(map[string]any)
	require.True(t, ok)
	assert.Contains(t, props, "cause")
	assert.Contains(t, props, "score")
	// Self-contained: no $schema envelope.
	assert.NotContains(t, m, "$schema")
}

// assertRequiredCoversProperties walks a decoded schema and asserts that, at
// every object level (root, nested object properties, array element schemas,
// and $defs/definitions entries), "required" lists every key in "properties".
// This is the invariant OpenAI strict json_schema mode enforces.
func assertRequiredCoversProperties(t *testing.T, node map[string]any) {
	t.Helper()
	if props, ok := node["properties"].(map[string]any); ok {
		reqRaw, ok := node["required"].([]any)
		require.True(t, ok, "object with properties must have a required array")
		got := make(map[string]bool, len(reqRaw))
		for _, r := range reqRaw {
			got[r.(string)] = true
		}
		for k := range props {
			assert.Truef(t, got[k], "property %q missing from required", k)
		}
		assert.Lenf(t, reqRaw, len(props), "required must have exactly one entry per property")
		for _, p := range props {
			recurseAssert(t, p)
		}
	}
	for _, section := range []string{"$defs", "definitions"} {
		if defs, ok := node[section].(map[string]any); ok {
			for _, def := range defs {
				recurseAssert(t, def)
			}
		}
	}
}

func recurseAssert(t *testing.T, v any) {
	t.Helper()
	sub, ok := v.(map[string]any)
	if !ok {
		return
	}
	assertRequiredCoversProperties(t, sub)
	if items, ok := sub["items"].(map[string]any); ok {
		recurseAssert(t, items)
	}
}

// TestSchemaFor_RequiredCoversProperties is the FIX 1 regression: a struct with
// an omitempty field must still appear in "required" so OpenAI strict mode
// accepts the schema. It drives a struct mirroring domain.TriageResult (whose
// NextActions field is `omitempty`) plus a nested object to cover recursion.
func TestSchemaFor_RequiredCoversProperties(t *testing.T) {
	type nested struct {
		Note string `json:"note,omitempty"`
	}
	type triageLike struct {
		Category    string   `json:"category"`
		Confidence  float64  `json:"confidence"`
		Actionable  bool     `json:"actionable"`
		Reasoning   string   `json:"reasoning"`
		NextActions []string `json:"next_actions,omitempty"`
		Detail      nested   `json:"detail"`
	}

	raw, err := SchemaFor[triageLike]()
	require.NoError(t, err)

	var doc map[string]any
	require.NoError(t, json.Unmarshal(raw, &doc))

	// The omitempty field is present in properties...
	props := doc["properties"].(map[string]any)
	assert.Contains(t, props, "next_actions")
	// ...and the invariant holds at every object level.
	assertRequiredCoversProperties(t, doc)
}
