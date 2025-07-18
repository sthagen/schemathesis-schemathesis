import uuid
from unittest.mock import ANY

import pytest
from hypothesis import Phase, settings
from requests import Request

import schemathesis
from schemathesis.config._projects import ProjectConfig
from schemathesis.core import NOT_SET
from schemathesis.generation import GenerationMode
from schemathesis.generation.hypothesis.builder import HypothesisTestConfig, HypothesisTestMode, create_test
from schemathesis.generation.meta import TestPhase
from schemathesis.specs.openapi.constants import LOCATION_TO_CONTAINER
from test.utils import assert_requests_call

POSITIVE_CASES = [
    {"headers": {"h1": "5", "h2": "000"}, "query": {"q1": "5", "q2": "0000"}, "body": {"j-prop": 0}},
    {"headers": {"h1": "5", "h2": "000"}, "query": {"q1": "6", "q2": "000"}, "body": {"j-prop": 0}},
    {"headers": {"h1": "5", "h2": "00"}, "query": {"q1": "5", "q2": "000"}, "body": {"j-prop": 0}},
    {"headers": {"h1": "4", "h2": "000"}, "query": {"q1": "5", "q2": "000"}, "body": {"j-prop": 0}},
    {"headers": {"h1": "5", "h2": "000"}, "query": {"q1": "5", "q2": "000"}, "body": {"x-prop": ""}},
    {"headers": {"h1": "5", "h2": "000"}, "query": {"q1": "5", "q2": "000"}, "body": {"j-prop": 0}},
]
NEGATIVE_CASES = [
    {"query": {"q1": ANY}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": ["0", "0"]}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": [ANY, ANY], "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "00"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": ["null", "null"]}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "null"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "false"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": "4", "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": ["null", "null"], "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": "", "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": "null", "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": "false", "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0000"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "{}"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "null,null"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "null"}, "body": False},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "false"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": "6", "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": "{}", "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": "null,null", "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": "", "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": "null", "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": "false", "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {"x-prop": {}}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {"x-prop": [None, None]}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {"x-prop": None}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {"x-prop": 0}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {"x-prop": 0}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": [None, None]},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": ""},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": False},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {"j-prop": {}}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {"j-prop": [None, None]}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {"j-prop": ""}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {"j-prop": None}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {"j-prop": False}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": {"j-prop": ANY}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": [None, None]},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": ""},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": False},
    {"query": {"q1": ANY, "q2": "0"}, "headers": {"h1": ANY, "h2": "0"}, "body": 0},
]
MIXED_CASES = [
    {"query": {"q1": "5"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": ["000", "000"]}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": ["5", "5"], "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "00"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": ["null", "null"]}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "null"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "false"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "0"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "0000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "4", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": ["null", "null"], "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "null", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "false", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": ANY, "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "6", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "0000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "{}"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "null,null"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "null"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "false"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "0"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "00"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "6", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "{}", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "null,null", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "null", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "false", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": ANY, "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "4", "h2": "000"}, "body": {"j-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"x-prop": {}}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"x-prop": [None, None]}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"x-prop": None}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"x-prop": False}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"x-prop": 0}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": [None, None]},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": ""},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": False},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": 0},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"x-prop": ""}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": {}}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": [None, None]}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": ""}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": None}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": False}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": ANY}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": [None, None]},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": ""},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": False},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": 0},
    {"query": {"q1": "5", "q2": "000"}, "headers": {"h1": "5", "h2": "000"}, "body": {"j-prop": 0}},
]


def build_schema(ctx, parameters=None, request_body=None, responses=None, version="3.0.2", path="/foo", method="post"):
    if responses is None:
        responses = {"default": {"description": "OK"}}

    schema = {
        path: {
            method: {
                "responses": responses,
            }
        }
    }
    if parameters is not None:
        schema[path][method]["parameters"] = parameters

    if request_body is not None:
        schema[path][method]["requestBody"] = request_body

    return ctx.openapi.build_schema(schema, version=version)


def assert_positive_coverage(schema, expected, path=None):
    return assert_coverage(schema, [GenerationMode.POSITIVE], expected, path)


def assert_negative_coverage(schema, expected, path=None):
    return assert_coverage(schema, [GenerationMode.NEGATIVE], expected, path)


@pytest.mark.parametrize(
    ("methods", "expected"),
    [
        (
            [GenerationMode.POSITIVE],
            POSITIVE_CASES,
        ),
        (
            [GenerationMode.NEGATIVE],
            NEGATIVE_CASES,
        ),
        (
            [GenerationMode.POSITIVE, GenerationMode.NEGATIVE],
            MIXED_CASES,
        ),
    ],
)
def test_phase(ctx, methods, expected):
    schema = build_schema(
        ctx,
        [
            {
                "in": "query",
                "name": "q1",
                "schema": {"type": "integer", "minimum": 5},
                "required": True,
            },
            {
                "in": "query",
                "name": "q2",
                "schema": {"type": "string", "minLength": 3},
                "required": True,
            },
            {
                "in": "header",
                "name": "h1",
                "schema": {"type": "integer", "maximum": 5},
                "required": True,
            },
            {
                "in": "header",
                "name": "h2",
                "schema": {"type": "string", "maxLength": 3},
                "required": True,
            },
        ],
        {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"j-prop": {"type": "integer"}},
                        "required": ["j-prop"],
                    },
                },
                "application/xml": {
                    "schema": {
                        "type": "object",
                        "properties": {"x-prop": {"type": "string"}},
                        "required": ["x-prop"],
                    },
                },
            },
        },
    )
    assert_coverage(schema, methods, expected)


def test_phase_no_body(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "in": "query",
                "name": "q1",
                "schema": {"type": "integer", "minimum": 5},
                "required": True,
            },
        ],
    )
    assert_positive_coverage(schema, [{"query": {"q1": "6"}}, {"query": {"q1": "5"}}])


def test_with_example(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "in": "query",
                "name": "q1",
                "schema": {"type": "string", "example": "secret"},
                "required": True,
            },
        ],
    )
    assert_positive_coverage(schema, [{"query": {"q1": "secret"}}])


EXPECTED_EXAMPLES = [
    {"query": {"q1": "A1", "q2": "20"}},
    {"query": {"q1": "B2", "q2": "10"}},
    {"query": {"q1": "A1", "q2": "10"}},
]


def test_with_examples_openapi_3(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "in": "query",
                "name": "q1",
                "schema": {"type": "string"},
                "required": True,
                "examples": {
                    "first": {"value": "A1"},
                    "second": {"value": "B2"},
                },
            },
            {
                "in": "query",
                "name": "q2",
                "schema": {"type": "integer"},
                "required": True,
                "examples": {
                    "first": {"value": 10},
                    "second": {"value": 20},
                },
            },
        ],
    )
    assert_positive_coverage(schema, EXPECTED_EXAMPLES)


def test_with_optional_parameters(ctx):
    schema = build_schema(
        ctx,
        [
            {"in": "query", "name": "q1", "schema": {"type": "string"}, "required": True, "example": "A1"},
            {"in": "query", "name": "q2", "schema": {"type": "integer"}, "required": False, "example": 10},
            {"in": "query", "name": "q3", "schema": {"type": "integer"}, "required": False, "example": 15},
            {"in": "query", "name": "q4", "schema": {"type": "integer"}, "required": False, "example": 20},
        ],
    )
    assert_positive_coverage(
        schema,
        [
            {
                "query": {
                    "q1": "A1",
                    "q3": "15",
                    "q4": "20",
                },
            },
            {
                "query": {
                    "q1": "A1",
                    "q2": "10",
                    "q4": "20",
                },
            },
            {
                "query": {
                    "q1": "A1",
                    "q2": "10",
                    "q3": "15",
                },
            },
            {
                "query": {
                    "q1": "A1",
                    "q4": "20",
                },
            },
            {
                "query": {
                    "q1": "A1",
                    "q3": "15",
                },
            },
            {
                "query": {
                    "q1": "A1",
                    "q2": "10",
                },
            },
            {
                "query": {
                    "q1": "A1",
                },
            },
            {
                "query": {
                    "q1": "A1",
                    "q2": "10",
                    "q3": "15",
                    "q4": "20",
                },
            },
        ],
    )


def test_with_example_openapi_3(ctx):
    schema = build_schema(
        ctx,
        [
            {"in": "query", "name": "q1", "schema": {"type": "string"}, "required": True, "example": "A1"},
            {"in": "query", "name": "q2", "schema": {"type": "integer"}, "required": True, "example": 10},
        ],
    )
    assert_positive_coverage(
        schema,
        [
            {
                "query": {
                    "q1": "A1",
                    "q2": "10",
                },
            },
        ],
    )


def test_with_response_example_openapi_3(ctx):
    schema = ctx.openapi.build_schema(
        {
            "/items/{itemId}/": {
                "get": {
                    "parameters": [{"name": "itemId", "in": "path", "schema": {"type": "string"}, "required": True}],
                    "responses": {
                        "200": {
                            "description": "",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Item"},
                                    "examples": {
                                        "Example1": {"value": {"id": "123456"}},
                                        "Example2": {"value": {"itemId": "456789"}},
                                    },
                                }
                            },
                        }
                    },
                }
            }
        },
        components={"schemas": {"Item": {"properties": {"id": {"type": "string"}}}}},
    )
    assert_positive_coverage(
        schema,
        [
            {
                "path_parameters": {
                    "itemId": "456789",
                },
            },
            {
                "path_parameters": {
                    "itemId": "123456",
                },
            },
        ],
        path=("/items/{itemId}/", "get"),
    )


def test_with_examples_openapi_3_1(ctx):
    schema = ctx.openapi.build_schema(
        {
            "/foo": {
                "post": {
                    "parameters": [
                        {
                            "in": "query",
                            "name": "q1",
                            "schema": {"type": "string", "examples": ["A1", "B2"]},
                            "required": True,
                        },
                        {
                            "in": "query",
                            "name": "q2",
                            "schema": {"type": "integer", "examples": [10, 20]},
                            "required": True,
                        },
                    ],
                    "responses": {"default": {"description": "OK"}},
                }
            }
        },
        version="3.1.0",
    )
    assert_positive_coverage(schema, EXPECTED_EXAMPLES)


def test_with_examples_openapi_3_request_body(ctx):
    schema = build_schema(
        ctx,
        request_body={
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "address": {
                                "type": "object",
                                "properties": {"street": {"type": "string"}, "city": {"type": "string"}},
                            },
                        },
                        "required": ["name", "age"],
                    },
                    "examples": {
                        "example1": {
                            "value": {
                                "name": "John Doe",
                                "age": 30,
                                "tags": ["developer", "python"],
                                "address": {"street": "123 Main St", "city": "Anytown"},
                            }
                        },
                        "example2": {
                            "value": {
                                "name": "Jane Smith",
                                "age": 25,
                                "tags": ["designer", "ui/ux"],
                                "address": {"street": "456 Elm St", "city": "Somewhere"},
                            }
                        },
                    },
                }
            },
            "required": True,
        },
    )
    assert_positive_coverage(
        schema,
        [
            {
                "body": {
                    "name": "John Doe",
                    "age": 30,
                    "tags": ["developer", "python"],
                    "address": {"street": "123 Main St", "city": "Somewhere"},
                }
            },
            {
                "body": {
                    "name": "John Doe",
                    "age": 30,
                    "tags": ["developer", "python"],
                    "address": {"street": "456 Elm St", "city": "Anytown"},
                }
            },
            {"body": {"name": "John Doe", "age": 30, "tags": ["developer", "python"], "address": {}}},
            {
                "body": {
                    "name": "John Doe",
                    "age": 30,
                    "tags": ["developer", "python"],
                    "address": {"street": "123 Main St"},
                }
            },
            {"body": {"name": "John Doe", "age": 30, "tags": ["developer", "python"], "address": {"city": "Anytown"}}},
            {
                "body": {
                    "name": "John Doe",
                    "age": 30,
                    "tags": ["developer", "python"],
                    "address": {"street": "456 Elm St", "city": "Somewhere"},
                }
            },
            {
                "body": {
                    "name": "John Doe",
                    "age": 30,
                    "tags": [""],
                    "address": {"street": "123 Main St", "city": "Anytown"},
                }
            },
            {
                "body": {
                    "name": "John Doe",
                    "age": 30,
                    "tags": ["designer", "ui/ux"],
                    "address": {"street": "123 Main St", "city": "Anytown"},
                }
            },
            {
                "body": {
                    "name": "John Doe",
                    "age": 25,
                    "tags": ["developer", "python"],
                    "address": {"street": "123 Main St", "city": "Anytown"},
                }
            },
            {
                "body": {
                    "name": "Jane Smith",
                    "age": 30,
                    "tags": ["developer", "python"],
                    "address": {"street": "123 Main St", "city": "Anytown"},
                }
            },
            {"body": {"name": "John Doe", "age": 30}},
            {"body": {"name": "John Doe", "age": 30, "tags": ["developer", "python"]}},
            {"body": {"name": "John Doe", "age": 30, "address": {"street": "123 Main St", "city": "Anytown"}}},
            {
                "body": {
                    "name": "Jane Smith",
                    "age": 25,
                    "tags": ["designer", "ui/ux"],
                    "address": {"street": "456 Elm St", "city": "Somewhere"},
                }
            },
            {
                "body": {
                    "name": "John Doe",
                    "age": 30,
                    "tags": ["developer", "python"],
                    "address": {"street": "123 Main St", "city": "Anytown"},
                }
            },
        ],
    )


@pytest.mark.parametrize(
    ["first", "second"],
    [
        (
            {
                "first": {"value": "A1"},
                "second": {"value": "B2"},
            },
            {
                "first": {"value": 10},
                "second": {"value": 20},
            },
        ),
        (
            ["A1", "B2"],
            [10, 20],
        ),
    ],
)
def test_with_examples_openapi_2(ctx, first, second):
    schema = build_schema(
        ctx,
        [
            {
                "in": "query",
                "name": "q1",
                "type": "string",
                "required": True,
                "x-examples": first,
            },
            {
                "in": "query",
                "name": "q2",
                "type": "integer",
                "required": True,
                "x-examples": second,
            },
        ],
        version="2.0",
    )
    assert_positive_coverage(schema, EXPECTED_EXAMPLES)


def test_mixed_type_keyword(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "name": "key",
                "in": "query",
                "required": False,
                "schema": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["a", "b"],
                        "additionalProperties": False,
                    },
                },
            },
        ],
    )
    assert_negative_coverage(
        schema,
        [
            {
                "query": {"key": ["0", "0"]},
            },
            {
                "query": {"key": [ANY]},
            },
            {
                "query": {"key": [["null", "null"]]},
            },
            {
                "query": {"key": ["null"]},
            },
            {
                "query": {"key": ["false"]},
            },
            {
                "query": {"key": ["0"]},
            },
            {
                "query": {"key": ""},
            },
            {
                "query": {"key": "null"},
            },
            {
                "query": {"key": "false"},
            },
        ],
    )


def test_negative_patterns(ctx):
    schema = build_schema(
        ctx,
        request_body={
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "minLength": 3,
                                "maxLength": 10,
                                "pattern": "^[a-zA-Z0-9-_]$",
                            },
                        },
                        "required": ["name"],
                    },
                }
            },
            "required": True,
        },
    )
    assert_negative_coverage(
        schema,
        [
            {
                "body": {},
            },
            {
                "body": {
                    "name": "000",
                },
            },
            {
                "body": {
                    "name": "00000000000",
                },
            },
            {
                "body": {
                    "name": "00",
                },
            },
            {
                "body": {
                    "name": {},
                },
            },
            {
                "body": {
                    "name": [None, None],
                },
            },
            {
                "body": {
                    "name": None,
                },
            },
            {
                "body": {
                    "name": False,
                },
            },
            {
                "body": {
                    "name": 0,
                },
            },
            {
                "body": [None, None],
            },
            {
                "body": "",
            },
            {},
            {
                "body": False,
            },
            {
                "body": 0,
            },
        ],
    )


def test_array_in_header_path_query(ctx):
    schema = build_schema(
        ctx,
        [
            {"name": "X-API-Key-1", "in": "header", "required": True, "schema": {"type": "string"}},
            {"name": "key", "in": "query", "required": True, "schema": {"type": "string"}},
            {"name": "bar", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        path="/foo/{bar}",
    )
    assert_negative_coverage(
        schema,
        [
            {
                "headers": {"X-API-Key-1": "0"},
                "path_parameters": {"bar": "0"},
            },
            {
                "path_parameters": {"bar": "0"},
                "query": {"key": "0"},
            },
            {
                "headers": {"X-API-Key-1": "0"},
                "path_parameters": {"bar": "0"},
                "query": {"key": ["0", "0"]},
            },
            {
                "headers": {"X-API-Key-1": "0"},
                "path_parameters": {"bar": "0"},
                "query": {"key": ["null", "null"]},
            },
            {
                "headers": {"X-API-Key-1": "0"},
                "path_parameters": {"bar": "0"},
                "query": {"key": "null"},
            },
            {
                "headers": {"X-API-Key-1": "0"},
                "path_parameters": {"bar": "0"},
                "query": {"key": "false"},
            },
            {
                "headers": {"X-API-Key-1": "{}"},
                "path_parameters": {"bar": "0"},
                "query": {"key": "0"},
            },
            {
                "headers": {"X-API-Key-1": "null,null"},
                "path_parameters": {"bar": "0"},
                "query": {"key": "0"},
            },
            {
                "headers": {"X-API-Key-1": "null"},
                "path_parameters": {"bar": "0"},
                "query": {"key": "0"},
            },
            {
                "headers": {"X-API-Key-1": "false"},
                "path_parameters": {"bar": "0"},
                "query": {"key": "0"},
            },
            {
                "headers": {"X-API-Key-1": "0"},
                "path_parameters": {"bar": {}},
                "query": {"key": "0"},
            },
            {
                "headers": {"X-API-Key-1": "0"},
                "path_parameters": {"bar": "null,null"},
                "query": {"key": "0"},
            },
            {
                "headers": {"X-API-Key-1": "0"},
                "path_parameters": {"bar": "null"},
                "query": {"key": "0"},
            },
            {
                "headers": {"X-API-Key-1": "0"},
                "path_parameters": {"bar": "false"},
                "query": {"key": "0"},
            },
        ],
        path=("/foo/{bar}", "post"),
    )


def test_required_header(ctx):
    schema = build_schema(
        ctx,
        [
            {"name": "X-API-Key-1", "in": "header", "required": True, "schema": {"type": "string"}},
            {"name": "X-API-Key-2", "in": "header", "required": True, "schema": {"type": "string"}},
        ],
    )
    assert_negative_coverage(
        schema,
        [
            {
                "headers": {"X-API-Key-1": "0"},
            },
            {
                "headers": {"X-API-Key-2": "0"},
            },
            {
                "headers": {"X-API-Key-1": "0", "X-API-Key-2": "{}"},
            },
            {
                "headers": {"X-API-Key-1": "0", "X-API-Key-2": "null,null"},
            },
            {
                "headers": {"X-API-Key-1": "0", "X-API-Key-2": "null"},
            },
            {
                "headers": {"X-API-Key-1": "0", "X-API-Key-2": "false"},
            },
            {
                "headers": {"X-API-Key-1": "{}", "X-API-Key-2": "0"},
            },
            {
                "headers": {"X-API-Key-1": "null,null", "X-API-Key-2": "0"},
            },
            {
                "headers": {"X-API-Key-1": "null", "X-API-Key-2": "0"},
            },
            {
                "headers": {"X-API-Key-1": "false", "X-API-Key-2": "0"},
            },
        ],
    )


def test_required_and_optional_headers(ctx):
    schema = build_schema(
        ctx,
        [
            {"name": "X-API-Key-1", "in": "header", "required": True, "schema": {"type": "string"}},
            {"name": "X-API-Key-2", "in": "header", "schema": {"type": "string"}},
        ],
    )
    assert_negative_coverage(
        schema,
        [
            {
                "headers": {"X-API-Key-1": "", "x-schemathesis-unknown-property": "42"},
            },
            {
                "headers": {"X-API-Key-1": "{}"},
            },
            {
                "headers": {"X-API-Key-1": "null,null"},
            },
            {
                "headers": {"X-API-Key-1": "null"},
            },
            {
                "headers": {"X-API-Key-1": "false"},
            },
            {
                "headers": {"X-API-Key-1": "0"},
            },
            {
                "headers": {"X-API-Key-2": "0"},
            },
            {
                "headers": {"X-API-Key-1": "0", "X-API-Key-2": "{}"},
            },
            {
                "headers": {"X-API-Key-1": "0", "X-API-Key-2": "null,null"},
            },
            {
                "headers": {"X-API-Key-1": "0", "X-API-Key-2": "null"},
            },
            {
                "headers": {"X-API-Key-1": "0", "X-API-Key-2": "false"},
            },
            {
                "headers": {"X-API-Key-1": "{}", "X-API-Key-2": "0"},
            },
            {
                "headers": {"X-API-Key-1": "null,null", "X-API-Key-2": "0"},
            },
            {
                "headers": {"X-API-Key-1": "null", "X-API-Key-2": "0"},
            },
            {
                "headers": {"X-API-Key-1": "false", "X-API-Key-2": "0"},
            },
        ],
    )


def test_path_parameter_string_non_empty(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "name": "name",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            }
        ],
    )
    assert_positive_coverage(schema, [{"path_parameters": {"name": "0"}}])


@pytest.mark.parametrize("extra", [{}, {"pattern": "[0-9]{1}", "minLength": 1}])
def test_path_parameter_invalid_example(ctx, extra):
    schema = build_schema(
        ctx,
        [
            {
                "name": "name",
                "in": "path",
                "required": True,
                "schema": {"type": "string", **extra},
                "example": "/",
            }
        ],
    )
    assert_positive_coverage(schema, [{"path_parameters": {"name": "0"}}])


def test_path_parameter(ctx):
    schema = build_schema(
        ctx,
        [
            {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        path="/foo/{id}",
    )
    assert_negative_coverage(
        schema,
        [
            {
                "path_parameters": {
                    "id": {},
                },
            },
            {
                "path_parameters": {
                    "id": "null,null",
                },
            },
            {
                "path_parameters": {
                    "id": "null",
                },
            },
            {
                "path_parameters": {
                    "id": "false",
                },
            },
        ],
        path=("/foo/{id}", "post"),
    )


def test_incorrect_headers_with_loose_schema(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "name": "authorization",
                "in": "header",
                "required": False,
                "schema": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Authorization"},
            }
        ],
    )
    assert_positive_coverage(
        schema,
        (
            [
                {"headers": {"authorization": ANY}},
                {"headers": {"authorization": "null"}},
                {"headers": {"authorization": ""}},
            ],
            [
                {"headers": {"authorization": "null"}},
                {"headers": {"authorization": ""}},
            ],
        ),
    )


def test_incorrect_headers(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "name": "X-API-Key-1",
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
                "example": "тест",
            },
        ],
    )
    assert_positive_coverage(schema, [{"headers": {"X-API-Key-1": ""}}])


def test_use_default(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "name": "Key",
                "in": "query",
                "required": True,
                "schema": {"type": "string", "default": "DEFAULT-VALUE"},
            },
        ],
    )
    assert_positive_coverage(schema, [{"query": {"Key": "DEFAULT-VALUE"}}])


def test_optional_parameter_without_type(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "in": "query",
                "name": "query",
                "required": True,
                "schema": {"title": "Query", "type": "string"},
            },
            {
                "in": "query",
                "name": "locking_period",
                "required": False,
                "schema": {"default": 24, "title": "Locking Period"},
            },
        ],
    )
    assert_negative_coverage(
        schema,
        [
            {
                "query": {
                    "query": "",
                    "x-schemathesis-unknown-property": "42",
                },
            },
            {
                "query": {
                    "query": "0",
                },
            },
            {},
            {
                "query": {
                    "query": [
                        "0",
                        "0",
                    ],
                },
            },
            {
                "query": {
                    "query": [
                        "null",
                        "null",
                    ],
                },
            },
            {
                "query": {
                    "query": "null",
                },
            },
            {
                "query": {
                    "query": "false",
                },
            },
        ],
    )


def test_incorrect_headers_with_enum(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "name": "X-API-Key-1",
                "in": "header",
                "required": True,
                "schema": {"enum": ["foo"]},
            },
        ],
    )
    assert_negative_coverage(
        schema,
        (
            [
                {},
                {"headers": {"X-API-Key-1": "{}"}},
                {"headers": {"X-API-Key-1": "null,null"}},
                {"headers": {"X-API-Key-1": "null"}},
                {"headers": {"X-API-Key-1": "false"}},
                {"headers": {"X-API-Key-1": "0"}},
            ],
            [
                {},
                {"headers": {"X-API-Key-1": "{}"}},
                {"headers": {"X-API-Key-1": "null,null"}},
                {"headers": {"X-API-Key-1": "false"}},
                {"headers": {"X-API-Key-1": "0"}},
            ],
            [
                {},
                {"headers": {"X-API-Key-1": "{}"}},
                {"headers": {"X-API-Key-1": "null,null"}},
                {"headers": {"X-API-Key-1": "null"}},
                {"headers": {"X-API-Key-1": "0"}},
            ],
        ),
    )


def test_generate_empty_headers_too(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "name": "X-API-Key-1",
                "in": "header",
                "required": True,
                "schema": {
                    "maxLength": 40,
                    "pattern": "^[\\w\\W]+$",
                    "type": "string",
                },
            },
        ],
    )
    assert_negative_coverage(
        schema,
        [
            {},
            {"headers": {"X-API-Key-1": "{}"}},
            {"headers": {"X-API-Key-1": "null,null"}},
            {"headers": {"X-API-Key-1": "null"}},
            {"headers": {"X-API-Key-1": "false"}},
            {"headers": {"X-API-Key-1": "0"}},
            {"headers": {"X-API-Key-1": ""}},
        ],
    )


@pytest.mark.parametrize(
    ["schema", "expected"],
    [
        (
            {
                "type": "array",
                "items": {"type": "boolean"},
                "maxItems": 3,
            },
            [
                {"body": [False, False, False, False]},
                {"body": [{}]},
                {"body": [[None, None]]},
                {"body": [""]},
                {"body": [None]},
                {"body": [0]},
                {"body": {}},
                {"body": ""},
                {},
                {"body": False},
                {"body": 0},
            ],
        ),
        (
            {
                "type": "array",
                "items": {"type": "boolean"},
                "minItems": 3,
            },
            [
                {"body": [False, False]},
                {"body": [{}]},
                {"body": [[None, None]]},
                {"body": [""]},
                {"body": [None]},
                {"body": [0]},
                {"body": {}},
                {"body": ""},
                {},
                {"body": False},
                {"body": 0},
            ],
        ),
        (
            {
                "type": "array",
                "items": {
                    "pattern": "[\\p{L}]+",
                },
                "maxItems": 50,
            },
            [
                {
                    "body": [],
                },
                {
                    "body": {},
                },
                {
                    "body": "",
                },
                {},
                {
                    "body": False,
                },
                {
                    "body": 0,
                },
            ],
        ),
    ],
)
@pytest.mark.filterwarnings("ignore::UserWarning")
def test_array_constraints(ctx, schema, expected):
    schema = build_schema(ctx, request_body={"required": True, "content": {"application/json": {"schema": schema}}})
    assert_negative_coverage(schema, expected)


def test_string_with_format(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "in": "path",
                "name": "foo_id",
                "schema": {"type": "string", "format": "uuid"},
                "required": True,
            },
        ],
        path="/foo/{foo_id}",
    )

    schema = schemathesis.openapi.from_dict(schema)

    def test(case):
        uuid.UUID(case.path_parameters["foo_id"], version=4)

    config = ProjectConfig()
    config.generation.update(modes=[GenerationMode.POSITIVE])
    test_func = create_test(
        operation=schema["/foo/{foo_id}"]["post"],
        test_func=test,
        config=HypothesisTestConfig(
            modes=[HypothesisTestMode.COVERAGE],
            project=config,
        ),
    )

    test_func()


def test_query_parameters_with_nested_enum(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "in": "query",
                "name": "q1",
                "schema": {
                    "items": {
                        "enum": [
                            "A",
                            "B",
                            "C",
                            "D",
                            "E",
                            "F",
                        ],
                        "type": "string",
                    },
                    "type": "array",
                },
                "required": True,
            },
        ],
    )
    assert_positive_coverage(
        schema,
        [
            {
                "query": {
                    "q1": [
                        "F",
                    ],
                },
            },
            {
                "query": {
                    "q1": [
                        "E",
                    ],
                },
            },
            {
                "query": {
                    "q1": [
                        "D",
                    ],
                },
            },
            {
                "query": {
                    "q1": [
                        "C",
                    ],
                },
            },
            {
                "query": {
                    "q1": [
                        "B",
                    ],
                },
            },
            {
                "query": {
                    "q1": [
                        "A",
                    ],
                },
            },
            {
                "query": {
                    "q1": [],
                },
            },
        ],
    )


def test_query_parameters_dont_exceed_max_length(ctx):
    schema = build_schema(
        ctx,
        [
            {
                "name": "foo",
                "in": "query",
                "required": False,
                "schema": {
                    "type": "string",
                    "pattern": "^bar\\.spam\\.[^,]+(?:,bar\\.spam\\.[^,]+)*$",
                    "minLength": 1,
                    "maxLength": 60,
                },
            },
        ],
    )
    assert_positive_coverage(
        schema,
        [
            {
                "query": {
                    "foo": "bar.spam.000000,bar.spam.0,bar.spam.0,bar.spam.0,bar.spam.0",
                },
            },
            {
                "query": {
                    "foo": "bar.spam.0000000,bar.spam.0,bar.spam.0,bar.spam.0,bar.spam.0",
                },
            },
            {
                "query": {
                    "foo": "bar.spam.0",
                },
            },
        ],
    )


def foo_id(value):
    return {
        "path_parameters": {
            "foo_id": value,
        },
    }


@pytest.mark.parametrize(
    ["schema", "expected"],
    [
        (
            {
                "type": "integer",
            },
            [
                foo_id({}),
                foo_id("null,null"),
                foo_id("null"),
                foo_id("false"),
            ],
        ),
        (
            {"type": "string", "format": "date-time"},
            [
                foo_id("0"),
                foo_id({}),
                foo_id("null,null"),
                foo_id("null"),
                foo_id("false"),
            ],
        ),
    ],
)
def test_path_parameters_always_present(ctx, schema, expected):
    schema = build_schema(
        ctx,
        [
            {
                "name": "foo_id",
                "in": "path",
                "required": True,
                "schema": schema,
            },
        ],
        path="/foo/{foo_id}",
    )
    assert_negative_coverage(
        schema,
        expected,
        ("/foo/{foo_id}", "post"),
    )


def test_path_parameters_without_constraints_negative(ctx):
    # When there are no constraints, then we can't generate negative values as everything will match the previous schema
    schema = build_schema(
        ctx,
        [
            {
                "name": "foo_id",
                "in": "path",
                "required": True,
                "schema": {},
            },
        ],
        path="/foo/{foo_id}",
    )
    assert_negative_coverage(
        schema,
        [],
        ("/foo/{foo_id}", "post"),
    )


def test_query_without_constraints_negative(ctx):
    # When there are no constraints, then we can't generate negative values as everything will match the previous schema
    schema = build_schema(
        ctx,
        [
            {
                "name": "q",
                "in": "query",
                "required": True,
                "schema": {},
            },
        ],
    )
    assert_negative_coverage(schema, [])


@pytest.mark.parametrize(
    ["schema", "required", "expected"],
    [
        [
            {
                "type": "string",
                "enum": ["foo", "bar", "spam"],
                "example": "spam",
            },
            False,
            [
                "http://127.0.0.1/foo?q=0&q=0",
                "http://127.0.0.1/foo?q=AAA",
                "http://127.0.0.1/foo?q=null&q=null",
                "http://127.0.0.1/foo?q=null",
                "http://127.0.0.1/foo?q=false",
            ],
        ],
        [
            {"type": "array", "items": {"type": "string"}},
            False,
            [
                "http://127.0.0.1/foo?q=0&q=0",
                "http://127.0.0.1/foo?q=null&q=null",
                "http://127.0.0.1/foo?q=null",
                "http://127.0.0.1/foo?q=false",
                "http://127.0.0.1/foo?q=0",
                "http://127.0.0.1/foo?q=",
                "http://127.0.0.1/foo?q=null",
                "http://127.0.0.1/foo?q=false",
            ],
        ],
        [
            {"type": "array", "items": {"type": "string"}},
            True,
            [
                "http://127.0.0.1/foo",
                "http://127.0.0.1/foo?q=0&q=0",
                "http://127.0.0.1/foo?q=null&q=null",
                "http://127.0.0.1/foo?q=null",
                "http://127.0.0.1/foo?q=false",
                "http://127.0.0.1/foo?q=0",
                "http://127.0.0.1/foo?q=",
                "http://127.0.0.1/foo?q=null",
                "http://127.0.0.1/foo?q=false",
            ],
        ],
    ],
)
def test_negative_query_parameter(ctx, schema, expected, required):
    schema = build_schema(
        ctx,
        [
            {
                "name": "q",
                "in": "query",
                "required": required,
                "schema": schema,
            }
        ],
    )

    schema = schemathesis.openapi.from_dict(schema)

    urls = []
    operation = schema["/foo"]["post"]

    def test(case):
        if case.meta.phase.name != TestPhase.COVERAGE:
            return
        if case.meta.phase.data.description.startswith("Unspecified"):
            return
        kwargs = case.as_transport_kwargs(base_url="http://127.0.0.1")
        request = Request(**kwargs).prepare()
        if not required:
            # We generate negative data - optional parameters should appear in the URL, but should be incorrect
            # Having it absent makes the case positive
            assert "?q=" in request.url
        urls.append(request.url)

    config = ProjectConfig()
    config.generation.update(modes=[GenerationMode.NEGATIVE])
    config.phases.coverage.generate_duplicate_query_parameters = True
    test_func = create_test(
        operation=operation,
        test_func=test,
        config=HypothesisTestConfig(
            modes=[HypothesisTestMode.COVERAGE],
            project=config,
            settings=settings(phases=[Phase.explicit]),
        ),
    )

    test_func()

    assert urls == expected


def test_negative_data_rejection(ctx, cli, openapi3_base_url, snapshot_cli):
    raw_schema = build_schema(
        ctx,
        [
            {
                "in": "query",
                "name": "page_num",
                "required": False,
                "schema": {"type": "integer", "minimum": 1, "maximum": 999, "default": 1},
            }
        ],
        path="/success",
        method="get",
    )
    schema_path = ctx.openapi.write_schema(raw_schema["paths"])
    assert (
        cli.main(
            "run",
            str(schema_path),
            "-c",
            "negative_data_rejection",
            f"--url={openapi3_base_url}",
            "--mode=all",
            "--max-examples=10",
            "--phases=coverage",
        )
        == snapshot_cli
    )


@pytest.mark.openapi_version("3.0")
def test_unspecified_http_methods(ctx, cli, openapi3_base_url, snapshot_cli):
    raw_schema = {
        "/foo": {
            "post": {
                "parameters": [{"in": "query", "name": "key", "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "OK"}},
            },
            "get": {
                "responses": {"200": {"description": "OK"}},
            },
        }
    }
    schema = ctx.openapi.build_schema(raw_schema)

    schema = schemathesis.openapi.from_dict(schema)

    methods = set()
    operation = schema["/foo"]["post"]

    def test(case):
        if case.meta.phase.name != TestPhase.COVERAGE:
            return
        if not case.meta.phase.data.description.startswith("Unspecified"):
            return
        methods.add(case.method)
        assert f"-X {case.method}" in case.as_curl_command()

    config = ProjectConfig()
    config.generation.update(modes=[GenerationMode.NEGATIVE])
    test_func = create_test(
        operation=operation,
        test_func=test,
        config=HypothesisTestConfig(
            modes=[HypothesisTestMode.COVERAGE],
            project=config,
            settings=settings(phases=[Phase.explicit]),
        ),
    )

    test_func()

    assert methods == {"PATCH", "TRACE", "DELETE", "OPTIONS", "PUT"}

    methods = set()

    config = ProjectConfig()
    config.generation.update(modes=[GenerationMode.NEGATIVE])
    config.phases.coverage.unexpected_methods = {"DELETE", "PUT"}
    test_func = create_test(
        operation=operation,
        test_func=test,
        config=HypothesisTestConfig(
            modes=[HypothesisTestMode.COVERAGE],
            project=config,
            settings=settings(phases=[Phase.explicit]),
        ),
    )

    test_func()

    assert methods == {"DELETE", "PUT"}

    schema_path = ctx.openapi.write_schema(raw_schema)
    with ctx.check(
        """
import schemathesis

@schemathesis.check
def failed(ctx, response, case):
    if case.meta and getattr(case.meta.phase.data, "description", "") == "Unspecified HTTP method: DELETE":
        raise AssertionError(f"Should be {case.meta.phase.data.description}")
"""
    ) as module:
        assert (
            cli.main(
                "run",
                str(schema_path),
                "-c",
                "failed,unsupported_method",
                "--include-method=POST",
                f"--url={openapi3_base_url}",
                "--mode=negative",
                "--max-examples=10",
                "--continue-on-failure",
                hooks=module,
            )
            == snapshot_cli
        )


def test_urlencoded_payloads_are_valid(ctx):
    schema = build_schema(
        ctx,
        request_body={
            "required": True,
            "content": {
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "number", "example": 1},
                        },
                        "required": ["key"],
                    },
                    "example": {"key": 1},
                }
            },
        },
    )
    schema = schemathesis.openapi.from_dict(schema)

    operation = schema["/foo"]["post"]

    def test(case):
        if case.meta.phase != TestPhase.COVERAGE:
            return
        assert_requests_call(case)

    config = ProjectConfig()
    config.generation.update(modes=list(GenerationMode))
    test_func = create_test(
        operation=operation,
        test_func=test,
        config=HypothesisTestConfig(
            modes=[HypothesisTestMode.COVERAGE],
            project=config,
            settings=settings(phases=[Phase.explicit]),
        ),
    )

    test_func()


def test_no_missing_header_duplication(ctx):
    schema = build_schema(
        ctx,
        [
            {"name": "X-Key-1", "in": "header", "required": False, "schema": {"type": "string"}},
            {"name": "X-Key-2", "in": "header", "required": False, "schema": {"type": "string"}},
            {"name": "X-Key-3", "in": "header", "required": True, "schema": {"type": "string"}},
        ],
    )
    schema = schemathesis.openapi.from_dict(schema)

    descriptions = []
    operation = schema["/foo"]["post"]

    def test(case):
        if case.meta.phase.name != TestPhase.COVERAGE:
            return
        descriptions.append(case.meta.phase.data.description)

    config = ProjectConfig()
    config.generation.update(modes=list(GenerationMode))
    test_func = create_test(
        operation=operation,
        test_func=test,
        config=HypothesisTestConfig(
            modes=[HypothesisTestMode.COVERAGE],
            project=config,
            settings=settings(phases=[Phase.explicit]),
        ),
    )

    test_func()

    assert "Missing required property: X-Key-3" not in descriptions
    assert "Missing `X-Key-3` at header" in descriptions


def assert_coverage(schema, modes, expected, path=None):
    schema = schemathesis.openapi.from_dict(schema)
    schema.config.phases.coverage.generate_duplicate_query_parameters = True

    cases = []
    operation = schema[path[0]][path[1]] if path else schema["/foo"]["post"]

    def test(case):
        meta = case.meta
        if meta.phase.name != TestPhase.COVERAGE:
            return
        if meta.phase.data.description.startswith("Unspecified"):
            return
        assert_requests_call(case)
        mode = meta.generation.mode
        if len(modes) == 1:
            assert mode == modes[0]
        else:
            if mode == GenerationMode.POSITIVE:
                # If the main mode is positive, then all components should have the positive mode
                for component, info in case.meta.components.items():
                    assert info.mode == mode, f"{component.value} should have {mode.value} mode"
            if mode == GenerationMode.NEGATIVE:
                # If the main mode is negative, then at least one component should be negative
                assert any(info.mode == mode for info in case.meta.components.values())

        if meta.phase.data.description == "Maximum length string":
            value, parameter = get_value_and_parameter(case)
            assert len(value) == parameter.definition["schema"]["maxLength"]

        output = {}
        for container in LOCATION_TO_CONTAINER.values():
            value = getattr(case, container)
            if container != "body" and not value:
                continue
            if value is not None and value is not NOT_SET:
                output[container] = value
        cases.append(output)

    config = ProjectConfig()
    config.generation.update(modes=modes)
    config.phases.coverage.generate_duplicate_query_parameters = True
    test_func = create_test(
        operation=operation,
        test_func=test,
        config=HypothesisTestConfig(
            modes=[HypothesisTestMode.COVERAGE],
            project=config,
            settings=settings(phases=[Phase.explicit]),
        ),
    )

    test_func()

    if isinstance(expected, tuple):
        assert cases in expected
    else:
        assert cases == expected


def get_value_and_parameter(case):
    location = LOCATION_TO_CONTAINER[case.meta.phase.data.parameter_location]
    name = case.meta.phase.data.parameter
    container = getattr(case, location)
    parameter = getattr(case.operation, location).get(name)
    return container.get(name), parameter
