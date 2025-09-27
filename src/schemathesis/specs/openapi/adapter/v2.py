from jsonschema import Draft4Validator

from schemathesis.specs.openapi.adapter import responses
from schemathesis.specs.openapi.adapter.protocol import ExtractResponseSchema

nullable_keyword = "x-nullable"
extract_response_schema: ExtractResponseSchema = responses.extract_response_schema_v2
jsonschema_validator_cls = Draft4Validator
