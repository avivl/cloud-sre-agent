package llm

import (
	"encoding/json"
	"fmt"

	"github.com/invopop/jsonschema"
)

// SchemaFor reflects a JSON schema for T, suitable for Request.Schema. It
// inlines definitions and omits the top-level $schema/$id so providers that
// expect a self-contained object schema accept it directly.
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
	return b, nil
}
