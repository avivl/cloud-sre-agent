package llm

import (
	"encoding/json"
	"fmt"
	"sort"

	"github.com/invopop/jsonschema"
)

// SchemaFor reflects a JSON schema for T, suitable for Request.Schema. It
// inlines definitions and omits the top-level $schema/$id so providers that
// expect a self-contained object schema accept it directly.
//
// The reflected schema is post-processed so that, at every object level (the
// root, every nested object property, and every entry under $defs/definitions),
// the "required" array lists ALL keys present in that object's "properties".
// OpenAI's strict json_schema mode rejects a schema whose "required" set does
// not cover its "properties"; Gemini and Anthropic tolerate a full required
// set, so a single shared schema is valid for all three. Decoding is unaffected
// because Go's omitempty only governs marshaling, not unmarshaling, so a field
// the model omits still decodes cleanly.
func SchemaFor[T any]() (json.RawMessage, error) {
	r := jsonschema.Reflector{
		DoNotReference:             true,
		Anonymous:                  true,
		AllowAdditionalProperties:  false,
		RequiredFromJSONSchemaTags: false,
	}
	var zero T
	s := r.Reflect(zero)
	s.Version = ""
	s.ID = ""
	b, err := json.Marshal(s)
	if err != nil {
		return nil, fmt.Errorf("llm: marshal schema for %T: %w", zero, err)
	}

	// Re-marshal through a generic map so required can be forced to cover every
	// property at all object levels, regardless of struct tags.
	var doc map[string]any
	if err := json.Unmarshal(b, &doc); err != nil {
		return nil, fmt.Errorf("llm: decode schema for %T: %w", zero, err)
	}
	requireAllProperties(doc)
	out, err := json.Marshal(doc)
	if err != nil {
		return nil, fmt.Errorf("llm: re-marshal schema for %T: %w", zero, err)
	}
	return out, nil
}

// requireAllProperties walks a decoded JSON schema node and, for every object
// schema with a "properties" map, sets "required" to the full (sorted) list of
// property keys. It recurses into nested property schemas and into the
// $defs/definitions sections so the rule holds at every object level. Sorting
// keeps the output deterministic regardless of map iteration order.
func requireAllProperties(node map[string]any) {
	if props, ok := node["properties"].(map[string]any); ok {
		keys := make([]string, 0, len(props))
		for k := range props {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		required := make([]any, len(keys))
		for i, k := range keys {
			required[i] = k
		}
		node["required"] = required

		// Recurse into each property's schema (nested objects, array items).
		for _, k := range keys {
			recurseSchema(props[k])
		}
	}

	// Recurse into definition sections so nested object types are covered too.
	for _, section := range []string{"$defs", "definitions"} {
		if defs, ok := node[section].(map[string]any); ok {
			for _, def := range defs {
				recurseSchema(def)
			}
		}
	}
}

// recurseSchema descends into a schema value (which may itself be an object
// schema, or carry "items" for arrays) and applies requireAllProperties.
func recurseSchema(v any) {
	sub, ok := v.(map[string]any)
	if !ok {
		return
	}
	requireAllProperties(sub)
	// Array element schemas live under "items"; cover their nested objects.
	if items, ok := sub["items"].(map[string]any); ok {
		recurseSchema(items)
	}
}
