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
