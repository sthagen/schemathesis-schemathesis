from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import ANY

import jsonschema
import pytest
from _pytest.main import ExitCode
from hypothesis import HealthCheck, Phase, find, given, settings
from hypothesis import strategies as st

import schemathesis
from schemathesis.generation.hypothesis import examples, strategies
from schemathesis.specs.openapi.examples import (
    ParameterExample,
    extract_from_schemas,
    extract_inner_examples,
    extract_top_level,
    find_in_responses,
    find_matching_in_responses,
    produce_combinations,
)
from schemathesis.specs.openapi.parameters import parameters_to_json_schema
from schemathesis.transport.wsgi import WSGI_TRANSPORT
from test.utils import assert_requests_call

if TYPE_CHECKING:
    from schemathesis.schemas import APIOperation
    from schemathesis.specs.openapi.schemas import BaseOpenAPISchema


@pytest.fixture(scope="module")
def dict_with_examples() -> dict[str, Any]:
    return {
        "openapi": "3.0.2",
        "info": {"title": "Test", "description": "Test", "version": "0.1.0"},
        "servers": [{"url": "http://127.0.0.1:8081/{basePath}", "variables": {"basePath": {"default": "api"}}}],
        "paths": {
            "/success": {
                "parameters": [
                    {
                        "name": "SESSION",
                        "in": "cookie",
                        "required": True,
                        "schema": {"type": "string", "example": "cookie2", "examples": ["cookie3"]},
                        "example": "cookie0",
                        "examples": {
                            "cookie1": {"value": "cookie1"},
                            "cookie4": {"$ref": "#/components/examples/Referenced3"},
                        },
                    },
                ],
                "post": {
                    "parameters": [
                        {
                            "name": "anyKey",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                            "example": "header0",
                            "examples": {"header1": {"value": "header1"}, "header2": {"value": "header2"}},
                        },
                        {
                            "name": "id",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "example": "query0",
                            "examples": {
                                "query1": {"value": "query1"},
                                "query3": {"$ref": "#/components/examples/Referenced3"},
                            },
                        },
                        {"name": "genericObject", "in": "query", "schema": {"type": "string"}},
                        {"$ref": "#/components/parameters/Referenced"},
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"foo": {"type": "string"}},
                                    "example": {"foo": "string4"},
                                    "examples": [{"foo": "string5"}],
                                },
                                "example": {"foo": "string0"},
                                "examples": {
                                    "body1": {"value": {"foo": "string1"}},
                                    "body2": {"value": {"foo": "string2"}},
                                    "body3": {"value": {"foo": "string3"}},
                                },
                            },
                            "multipart/form-data": {
                                "schema": {"type": "object", "properties": {"bar": {"type": "string"}}},
                                "example": {"bar": "string0"},
                                "examples": {
                                    "body1": {"value": {"bar": "string1"}},
                                    "body2": {"$ref": "#/components/examples/Referenced2"},
                                },
                            },
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                },
            }
        },
        "components": {
            "parameters": {
                "Referenced": {
                    "name": "Referenced",
                    "in": "query",
                    "required": True,
                    "example": "Ref-1",
                    "schema": {
                        "type": "string",
                        "example": "Ref-2",
                    },
                    "examples": {"referenced-3": {"$ref": "#/components/examples/Referenced3"}},
                }
            },
            "examples": {
                "Referenced2": {"bar": "referenced-body2"},
                "Referenced3": "referenced-string3",
            },
        },
    }


@pytest.fixture(scope="module")
def dict_with_property_examples() -> dict[str, Any]:
    return {
        "openapi": "3.0.2",
        "info": {"title": "Test", "description": "Test", "version": "0.1.0"},
        "servers": [{"url": "http://127.0.0.1:8081/{basePath}", "variables": {"basePath": {"default": "api"}}}],
        "paths": {
            "/success": {
                "post": {
                    "parameters": [
                        {
                            "name": "q-1",
                            "in": "query",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "foo-1": {"type": "string", "example": "foo-11", "examples": ["foo-12"]},
                                    "bar-1": {"type": "string", "example": "bar-11"},
                                    "spam-1": {"type": "string"},
                                },
                            },
                        },
                        {
                            "name": "q-2",
                            "in": "query",
                            "schema": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "foo-2": {"type": "string", "example": "foo-21"},
                                        "bar-2": {"type": "string", "example": "bar-21", "examples": ["bar-22"]},
                                        "spam-2": {"type": "string"},
                                    },
                                    "required": ["spam-2"],
                                },
                            },
                        },
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "key": {"type": "string", "example": "json-key-1", "examples": ["json-key-2"]}
                                    },
                                },
                            },
                            "multipart/form-data": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "key": {
                                                "type": "string",
                                                "example": "form-key-1",
                                                "examples": ["form-key-2"],
                                            }
                                        },
                                    },
                                },
                            },
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }


@pytest.fixture(scope="module")
def schema_with_examples(dict_with_examples) -> BaseOpenAPISchema:
    return schemathesis.openapi.from_dict(dict_with_examples)


@pytest.fixture(scope="module")
def schema_with_property_examples(dict_with_property_examples) -> BaseOpenAPISchema:
    return schemathesis.openapi.from_dict(dict_with_property_examples)


@pytest.fixture
def operation(schema_with_examples) -> APIOperation:
    """Returns first (and only) API operation from schema_with_examples."""
    return next(schema_with_examples.get_all_operations()).ok()


@pytest.fixture
def operation_with_property_examples(schema_with_property_examples) -> APIOperation:
    """Returns first (and only) API operation from schema_with_examples."""
    return next(schema_with_property_examples.get_all_operations()).ok()


def example_to_dict(example):
    if isinstance(example, ParameterExample):
        return {"container": example.container, "name": example.name, "value": example.value}
    return {"value": example.value, "media_type": example.media_type}


def test_extract_top_level(operation):
    top_level_examples = list(extract_top_level(operation))
    extracted = [example_to_dict(example) for example in top_level_examples]
    assert extracted == [
        {"container": "headers", "name": "anyKey", "value": "header0"},
        {"container": "headers", "name": "anyKey", "value": "header1"},
        {"container": "headers", "name": "anyKey", "value": "header2"},
        {"container": "cookies", "name": "SESSION", "value": "cookie0"},
        {"container": "cookies", "name": "SESSION", "value": "cookie2"},
        {"container": "cookies", "name": "SESSION", "value": "cookie1"},
        {"container": "cookies", "name": "SESSION", "value": "referenced-string3"},
        {"container": "cookies", "name": "SESSION", "value": "cookie3"},
        {"container": "query", "name": "id", "value": "query0"},
        {"container": "query", "name": "id", "value": "query1"},
        {"container": "query", "name": "id", "value": "referenced-string3"},
        {"container": "query", "name": "Referenced", "value": "Ref-1"},
        {"container": "query", "name": "Referenced", "value": "Ref-2"},
        {"container": "query", "name": "Referenced", "value": "referenced-string3"},
        {"media_type": "application/json", "value": {"foo": "string0"}},
        {"media_type": "application/json", "value": {"foo": "string4"}},
        {"media_type": "application/json", "value": {"foo": "string1"}},
        {"media_type": "application/json", "value": {"foo": "string2"}},
        {"media_type": "application/json", "value": {"foo": "string3"}},
        {"media_type": "application/json", "value": {"foo": "string5"}},
        {"media_type": "multipart/form-data", "value": {"bar": "string0"}},
        {"media_type": "multipart/form-data", "value": {"bar": "string1"}},
        {"media_type": "multipart/form-data", "value": {"bar": "referenced-body2"}},
    ]
    assert list(produce_combinations(top_level_examples)) == [
        {
            "body": {"foo": "string0"},
            "cookies": {"SESSION": "cookie0"},
            "headers": {"anyKey": "header0"},
            "media_type": "application/json",
            "query": {"Referenced": "Ref-1", "id": "query0"},
        },
        {
            "body": {"foo": "string4"},
            "cookies": {"SESSION": "cookie2"},
            "headers": {"anyKey": "header1"},
            "media_type": "application/json",
            "query": {"Referenced": "Ref-2", "id": "query1"},
        },
        {
            "body": {"foo": "string1"},
            "cookies": {"SESSION": "cookie1"},
            "headers": {"anyKey": "header2"},
            "media_type": "application/json",
            "query": {"Referenced": "referenced-string3", "id": "referenced-string3"},
        },
        {
            "body": {"foo": "string2"},
            "cookies": {"SESSION": "referenced-string3"},
            "headers": {"anyKey": "header0"},
            "media_type": "application/json",
            "query": {"Referenced": "Ref-1", "id": "query0"},
        },
        {
            "body": {"foo": "string3"},
            "cookies": {"SESSION": "cookie3"},
            "headers": {"anyKey": "header1"},
            "media_type": "application/json",
            "query": {"Referenced": "Ref-2", "id": "query1"},
        },
        {
            "body": {"foo": "string5"},
            "cookies": {"SESSION": "cookie0"},
            "headers": {"anyKey": "header0"},
            "media_type": "application/json",
            "query": {"Referenced": "Ref-1", "id": "query0"},
        },
        {
            "body": {"bar": "string0"},
            "cookies": {"SESSION": "cookie2"},
            "headers": {"anyKey": "header1"},
            "media_type": "multipart/form-data",
            "query": {"Referenced": "Ref-2", "id": "query1"},
        },
        {
            "body": {"bar": "string1"},
            "cookies": {"SESSION": "cookie1"},
            "headers": {"anyKey": "header2"},
            "media_type": "multipart/form-data",
            "query": {"Referenced": "referenced-string3", "id": "referenced-string3"},
        },
        {
            "body": {"bar": "referenced-body2"},
            "cookies": {"SESSION": "referenced-string3"},
            "headers": {"anyKey": "header0"},
            "media_type": "multipart/form-data",
            "query": {"Referenced": "Ref-1", "id": "query0"},
        },
    ]


def test_examples_from_cli(ctx, app, cli, base_url, schema_with_examples):
    schema = schema_with_examples.raw_schema
    app["config"].update({"schema_data": schema})
    schema_path = ctx.makefile(schema)
    result = cli.run(
        str(schema_path),
        f"--url={base_url}",
        "--phases=examples",
        "--checks=not_a_server_error",
    )

    assert result.exit_code == ExitCode.OK, result.stdout
    # The request body has the 3 examples defined. Because 3 is the most examples defined
    # for any parameter, we expect to generate 3 requests.
    assert "9 generated" in result.stdout


def test_network_error_with_flaky_generation(ctx, cli, snapshot_cli, schema_with_examples):
    # Assume that there is a user-defined hook that makes data generation flaky
    module = ctx.write_pymodule(
        """
import schemathesis


@schemathesis.hook
def before_generate_case(context, strategy):
    seen = set()

    def is_not_seen(case) -> bool:
        hashed = hash(case)
        if hashed not in seen:
            seen.add(hashed)
            return True
        return False

    return strategy.filter(is_not_seen)
"""
    )

    schema_file = ctx.makefile(schema_with_examples.raw_schema)
    assert (
        cli.main(
            "run",
            str(schema_file),
            "--url=http://127.0.0.1:1",
            "--seed=23",
            "--phases=fuzzing",
            hooks=module,
        )
        == snapshot_cli
    )


@pytest.fixture
def explicit_header(ctx):
    with ctx.check("""
@schemathesis.check
def explicit_header(ctx, response, case):
    assert case.headers["anyKey"] == "OVERRIDE"
    assert case.query["id"] == "OVERRIDE"
""") as module:
        yield module


def test_parameter_override(ctx, cli, openapi3_base_url, snapshot_cli, explicit_header):
    schema_file = ctx.openapi.write_schema(
        {
            "/success": {
                "post": {
                    "parameters": [
                        {
                            "name": "anyKey",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                            "example": "header0",
                        },
                        {
                            "name": "id",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "example": "query0",
                        },
                    ],
                    "responses": {"200": {"description": "OK"}},
                },
            }
        }
    )
    assert (
        cli.main(
            "run",
            str(schema_file),
            "--seed=23",
            "--phases=examples",
            f"--url={openapi3_base_url}",
            "--checks=explicit_header",
            hooks=explicit_header,
            config={
                "parameters": {
                    "anyKey": "OVERRIDE",
                    "id": "OVERRIDE",
                }
            },
        )
        == snapshot_cli
    )


def test_extract_from_schemas(operation_with_property_examples):
    extracted = [example_to_dict(example) for example in extract_from_schemas(operation_with_property_examples)]
    assert extracted == [
        {"container": "query", "name": "q-1", "value": {"bar-1": "bar-11", "foo-1": "foo-11"}},
        {"container": "query", "name": "q-1", "value": {"bar-1": "bar-11", "foo-1": "foo-12"}},
        {"container": "query", "name": "q-2", "value": [{"bar-2": "bar-21", "foo-2": "foo-21", "spam-2": ""}]},
        {"container": "query", "name": "q-2", "value": [{"bar-2": "bar-22", "foo-2": "foo-21", "spam-2": ""}]},
        {"media_type": "application/json", "value": {"key": "json-key-1"}},
        {"media_type": "application/json", "value": {"key": "json-key-2"}},
        {"media_type": "multipart/form-data", "value": [{"key": "form-key-1"}]},
        {"media_type": "multipart/form-data", "value": [{"key": "form-key-2"}]},
    ]


def test_multipart_examples():
    # Regression after parameters refactoring
    # When the schema contains examples for multipart forms
    raw_schema = {
        "openapi": "3.0.0",
        "info": {"title": "Sample API", "description": "API description in Markdown.", "version": "1.0.0"},
        "paths": {
            "/test": {
                "post": {
                    "description": "Test",
                    "requestBody": {
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "properties": {
                                        "key": {
                                            "example": "test",
                                            "type": "string",
                                        },
                                    },
                                    "type": "object",
                                }
                            }
                        }
                    },
                    "responses": {"default": {"description": "OK"}},
                },
            },
        },
    }
    schema = schemathesis.openapi.from_dict(raw_schema)
    # Then examples should be correctly generated
    strategies = schema["/test"]["POST"].get_strategies_from_examples()
    assert len(strategies) == 1
    assert find(strategies[0], lambda case: case.body == {"key": "test"})


def test_invalid_x_examples(ctx):
    # See GH-982
    # When an Open API 2.0 schema contains a non-object type in `x-examples`
    schema = ctx.openapi.build_schema(
        {
            "/test": {
                "post": {
                    "parameters": [
                        {"name": "body", "in": "body", "schema": {"type": "integer"}, "x-examples": {"foo": "value"}}
                    ],
                    "responses": {"default": {"description": "OK"}},
                }
            }
        },
        version="2.0",
    )
    schema = schemathesis.openapi.from_dict(schema)
    # Then such examples should be skipped as invalid (there should be an object)
    assert schema["/test"]["POST"].get_strategies_from_examples() == []


def test_shared_examples_openapi_2(ctx):
    schema = ctx.openapi.build_schema(
        {
            "/test": {
                "parameters": [
                    {
                        "name": "any",
                        "in": "body",
                        "required": True,
                        "schema": {},
                    },
                ],
                "post": {
                    "parameters": [
                        {"name": "body", "in": "body", "schema": {}, "x-examples": {"foo": {"value": "value"}}}
                    ],
                    "responses": {"default": {"description": "OK"}},
                },
            }
        },
        version="2.0",
    )
    schema = schemathesis.openapi.from_dict(schema)
    strategies = schema["/test"]["POST"].get_strategies_from_examples()
    assert len(strategies) == 1
    assert find(strategies[0], lambda case: case.body == "value")


@pytest.mark.parametrize("examples", [{"example1": {"value": "value"}}, ["value"]])
def test_examples_ref_openapi_2(ctx, examples):
    schema = ctx.openapi.build_schema(
        {
            "/test": {
                "post": {
                    "parameters": [{"$ref": "#/components/parameters/Referenced"}],
                    "responses": {"default": {"description": "OK"}},
                },
            }
        },
        components={
            "parameters": {
                "Referenced": {
                    "name": "Referenced",
                    "in": "body",
                    "required": True,
                    "schema": {},
                    "x-examples": examples,
                }
            }
        },
        version="2.0",
    )
    schema = schemathesis.openapi.from_dict(schema)
    strategies = schema["/test"]["POST"].get_strategies_from_examples()
    assert len(strategies) == 1
    assert find(strategies[0], lambda case: case.body == "value")


@pytest.mark.parametrize("body", ["BodyDirect", "BodyRef"])
def test_examples_ref_openapi_3(ctx, body):
    schema = ctx.openapi.build_schema(
        {
            "/test": {
                "post": {
                    "requestBody": {"$ref": f"#/components/requestBodies/{body}"},
                    "responses": {"default": {"description": "OK"}},
                },
            }
        },
        components={
            "requestBodies": {
                "BodyDirect": {
                    "content": {
                        "application/json": {
                            "schema": {},
                            "examples": {"example1": {"value": "value"}},
                        }
                    }
                },
                "BodyRef": {"$ref": "#/components/requestBodies/BodyDirect"},
            }
        },
    )
    schema = schemathesis.openapi.from_dict(schema)
    strategies = schema["/test"]["POST"].get_strategies_from_examples()
    assert len(strategies) == 1
    assert find(strategies[0], lambda case: case.body == "value")


def test_boolean_subschema(ctx):
    schema = ctx.openapi.build_schema(
        {
            "/test": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"foo": {"type": "string", "example": "foo-value"}, "bar": True},
                                    "required": ["foo", "bar"],
                                },
                            }
                        }
                    },
                    "responses": {"default": {"description": "OK"}},
                },
            }
        }
    )
    schema = schemathesis.openapi.from_dict(schema)
    strategy = schema["/test"]["POST"].get_strategies_from_examples()[0]
    example = examples.generate_one(strategy)
    assert example.body == {"bar": ANY, "foo": "foo-value"}


def test_examples_ref_missing_components(ctx):
    schema = ctx.openapi.build_schema(
        {
            "/test": {
                "post": {
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "foo-1": {"type": "string", "example": "foo-11"},
                                    "spam-1": {"$ref": "#/components/schemas/Referenced"},
                                },
                                "required": ["foo-1", "spam-1"],
                            },
                        }
                    ],
                    "responses": {"default": {"description": "OK"}},
                },
            }
        },
        components={
            "schemas": {
                "Referenced": {
                    "type": "object",
                    "properties": {"inner": {"$ref": "#/components/schemas/Key0"}},
                    "required": ["inner"],
                },
                **{f"Key{idx}": {"$ref": f"#/components/schemas/Key{idx + 1}"} for idx in range(8)},
                "Key8": {"enum": ["example"]},
            }
        },
    )
    schema = schemathesis.openapi.from_dict(schema)
    strategy = schema["/test"]["POST"].get_strategies_from_examples()[0]
    example = examples.generate_one(strategy)
    assert example.query == {"q": {"foo-1": "foo-11", "spam-1": {"inner": "example"}}}


@pytest.mark.parametrize("key", ["anyOf", "oneOf"])
def test_examples_in_any_of_top_level(ctx, key):
    schema = ctx.openapi.build_schema(
        {
            "/test": {
                "post": {
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "schema": {
                                key: [
                                    {
                                        "example": "foo-1-1",
                                        "examples": ["foo-1-2"],
                                        "type": "string",
                                    },
                                    {
                                        "example": "foo-2-1",
                                        "examples": ["foo-2-2"],
                                        "type": "string",
                                    },
                                    True,
                                ]
                            },
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    key: [
                                        {
                                            "example": "body-1-1",
                                            "examples": ["body-1-2"],
                                            "type": "string",
                                        },
                                        {
                                            "example": "body-2-1",
                                            "examples": ["body-2-2"],
                                            "type": "string",
                                        },
                                        True,
                                    ]
                                }
                            },
                        }
                    },
                    "responses": {"default": {"description": "OK"}},
                },
            }
        }
    )
    schema = schemathesis.openapi.from_dict(schema)
    extracted = [example_to_dict(example) for example in extract_top_level(schema["/test"]["POST"])]
    assert extracted == [
        {"container": "query", "name": "q", "value": "foo-1-1"},
        {"container": "query", "name": "q", "value": "foo-2-1"},
        {"container": "query", "name": "q", "value": "foo-1-2"},
        {"container": "query", "name": "q", "value": "foo-2-2"},
        {"media_type": "application/json", "value": "body-1-1"},
        {"media_type": "application/json", "value": "body-2-1"},
        {"media_type": "application/json", "value": "body-1-2"},
        {"media_type": "application/json", "value": "body-2-2"},
    ]


def test_examples_in_all_of_top_level(ctx):
    schema = ctx.openapi.build_schema(
        {
            "/test": {
                "post": {
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "schema": {
                                "allOf": [
                                    {
                                        "example": "foo-1-1",
                                        "examples": ["foo-1-2"],
                                        "type": "string",
                                    },
                                    {
                                        "example": "foo-2-1",
                                        "examples": ["foo-2-2"],
                                        "type": "string",
                                    },
                                    True,
                                ]
                            },
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "allOf": [
                                        {
                                            "example": "body-1-1",
                                            "examples": ["body-1-2"],
                                            "type": "string",
                                        },
                                        {
                                            "example": "body-2-1",
                                            "examples": ["body-2-2"],
                                            "type": "string",
                                        },
                                        True,
                                    ]
                                }
                            },
                        }
                    },
                    "responses": {"default": {"description": "OK"}},
                },
            }
        }
    )
    schema = schemathesis.openapi.from_dict(schema)
    extracted = [example_to_dict(example) for example in extract_top_level(schema["/test"]["POST"])]
    assert extracted == [
        {"container": "query", "name": "q", "value": "foo-1-1"},
        {"container": "query", "name": "q", "value": "foo-1-2"},
        {"container": "query", "name": "q", "value": "foo-2-1"},
        {"container": "query", "name": "q", "value": "foo-2-2"},
        {"media_type": "application/json", "value": "body-1-1"},
        {"media_type": "application/json", "value": "body-1-2"},
        {"media_type": "application/json", "value": "body-2-1"},
        {"media_type": "application/json", "value": "body-2-2"},
    ]


@pytest.mark.parametrize("key", ["anyOf", "oneOf"])
def test_examples_in_any_of_in_schemas(ctx, key):
    schema = ctx.openapi.build_schema(
        {
            "/test": {
                "post": {
                    "parameters": [
                        {
                            "name": "q-1",
                            "in": "query",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "foo-1": {
                                        key: [
                                            {
                                                "example": "foo-1-1-1",
                                                "examples": ["foo-1-1-2"],
                                                "type": "string",
                                            },
                                            {
                                                "example": "foo-1-2-1",
                                                "examples": ["foo-1-2-2"],
                                                "type": "string",
                                            },
                                            True,
                                        ]
                                    },
                                    "bar-1": {
                                        key: [
                                            {
                                                "example": "bar-1-1-1",
                                                "type": "string",
                                            },
                                            {
                                                "example": "bar-1-2-1",
                                                "type": "string",
                                            },
                                            True,
                                        ]
                                    },
                                    "spam-1": {"type": "string"},
                                },
                                "required": ["foo-1", "bar-1"],
                            },
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "key": {
                                            key: [
                                                {
                                                    "example": "json-key-1-1",
                                                    "examples": ["json-key-1-2"],
                                                    "type": "string",
                                                },
                                                {
                                                    "example": "json-key-2-1",
                                                    "examples": ["json-key-2-2"],
                                                    "type": "string",
                                                },
                                                True,
                                            ]
                                        }
                                    },
                                }
                            },
                        }
                    },
                    "responses": {"default": {"description": "OK"}},
                },
            }
        }
    )
    schema = schemathesis.openapi.from_dict(schema)
    extracted = [example_to_dict(example) for example in extract_from_schemas(schema["/test"]["POST"])]
    assert extracted == [
        {"container": "query", "name": "q-1", "value": {"bar-1": "bar-1-1-1", "foo-1": "foo-1-1-1"}},
        {"container": "query", "name": "q-1", "value": {"bar-1": "bar-1-2-1", "foo-1": "foo-1-1-2"}},
        {"container": "query", "name": "q-1", "value": {"bar-1": "bar-1-1-1", "foo-1": "foo-1-2-1"}},
        {"container": "query", "name": "q-1", "value": {"bar-1": "bar-1-2-1", "foo-1": "foo-1-2-2"}},
        {"media_type": "application/json", "value": {"key": "json-key-1-1"}},
        {"media_type": "application/json", "value": {"key": "json-key-1-2"}},
        {"media_type": "application/json", "value": {"key": "json-key-2-1"}},
        {"media_type": "application/json", "value": {"key": "json-key-2-2"}},
    ]


def test_partial_examples(ctx):
    # When the API schema contains multiple parameters in the same location
    # And some of them don't have explicit examples and others do
    schema = ctx.openapi.build_schema(
        {
            "/test/{foo}/{bar}/": {
                "post": {
                    "parameters": [
                        {"name": "foo", "in": "path", "required": True, "schema": {"type": "string", "enum": ["A"]}},
                        {
                            "name": "bar",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "example": "bar-example"},
                        },
                    ],
                    "responses": {"default": {"description": "OK"}},
                }
            }
        }
    )
    schema = schemathesis.openapi.from_dict(schema)
    operation = schema["/test/{foo}/{bar}/"]["POST"]
    strategy = operation.get_strategies_from_examples()[0]
    # Then all generated examples should have those missing parts generated according to the API schema
    example = examples.generate_one(strategy)
    parameters_schema = parameters_to_json_schema(operation, operation.path_parameters)
    jsonschema.validate(example.path_parameters, parameters_schema)


def test_partial_examples_without_null_bytes_and_formats(ctx):
    schemathesis.openapi.format("even_4_digits", st.from_regex(r"\A[0-9]{4}\Z").filter(lambda x: int(x) % 2 == 0))
    schema = ctx.openapi.build_schema(
        {
            "/test/": {
                "post": {
                    "parameters": [
                        {
                            "name": "q1",
                            "in": "query",
                            "required": True,
                            "schema": {
                                "type": "object",
                                "properties": {"foo": {"type": "string"}},
                                "required": ["foo"],
                                "additionalProperties": False,
                            },
                        },
                        {
                            "name": "q2",
                            "in": "query",
                            "required": True,
                            "schema": {
                                "type": "object",
                                "properties": {"foo": {"type": "string", "format": "even_4_digits"}},
                                "required": ["foo"],
                                "additionalProperties": False,
                            },
                        },
                        {
                            "name": "q3",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "example": "test",
                        },
                    ],
                    "responses": {"default": {"description": "OK"}},
                }
            }
        }
    )
    schema = schemathesis.openapi.from_dict(schema)
    schema.config.generation.update(allow_x00=False)
    operation = schema["/test/"]["POST"]
    strategy = operation.get_strategies_from_examples()[0]

    @given(case=strategy)
    @settings(deadline=None, suppress_health_check=list(HealthCheck), phases=[Phase.generate])
    def test(case):
        assert "\x00" not in case.query["q1"]["foo"]
        assert len(case.query["q2"]["foo"]) == 4
        assert int(case.query["q2"]["foo"]) % 2 == 0

    test()


def test_external_value(ctx, server):
    # When the API schema contains examples via `externalValue` keyword
    schema = ctx.openapi.build_schema(
        {
            "/test/": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "integer"},
                                "examples": {
                                    "answer": {"externalValue": f"http://127.0.0.1:{server['port']}/answer.json"}
                                },
                            }
                        }
                    },
                    "responses": {"default": {"description": "OK"}},
                }
            }
        }
    )
    schema = schemathesis.openapi.from_dict(schema)
    operation = schema["/test/"]["POST"]
    strategy = operation.get_strategies_from_examples()[0]
    # Then this example should be used
    example = examples.generate_one(strategy)
    assert example.body == b"42"
    # And this data should be OK to send
    assert_requests_call(example)
    assert WSGI_TRANSPORT.serialize_case(example)["data"] == b"42"


def test_external_value_network_error(ctx):
    # When the external value is not available
    schema = ctx.openapi.build_schema(
        {
            "/test/": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "integer"},
                                "examples": {
                                    "answer": {
                                        # Not available
                                        "externalValue": "http://127.0.0.1:1/answer.json"
                                    }
                                },
                            }
                        }
                    },
                    "responses": {"default": {"description": "OK"}},
                }
            }
        }
    )
    schema = schemathesis.openapi.from_dict(schema)
    operation = schema["/test/"]["POST"]
    # Then this example should not be used
    assert not operation.get_strategies_from_examples()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"foo": {"value": 42}}, [42]),
        ({"foo": {}}, []),
    ],
)
def test_empty_example(value, expected):
    assert list(extract_inner_examples(value, value)) == expected


def test_example_override():
    raw_schema = {
        "openapi": "3.0.2",
        "info": {"title": "Test", "description": "Test", "version": "0.1.0"},
        "servers": [{"url": "http://127.0.0.1:8081/{basePath}", "variables": {"basePath": {"default": "api"}}}],
        "paths": {
            "/success": {
                "parameters": [
                    {
                        "name": "key",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                ],
                "get": {
                    "parameters": [
                        {
                            "name": "key",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "examples": {"query1": {"value": "query1"}},
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                },
            }
        },
    }
    schema = schemathesis.openapi.from_dict(raw_schema)
    operation = schema["/success"]["GET"]
    extracted = [example_to_dict(example) for example in extract_top_level(operation)]
    assert extracted == [{"container": "query", "name": "key", "value": "query1"}]


def test_no_wrapped_examples():
    # See GH-2238
    raw_schema = {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/register": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Register"},
                                "examples": {"objectExample": {"$ref": "#/components/examples/objectExample"}},
                            }
                        }
                    },
                    "responses": {"200": {"description": "Successful operation"}},
                }
            }
        },
        "components": {
            "schemas": {
                "Register": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "example": "username"},
                        "email": {"type": "string", "example": "john.doe@email.com"},
                        "password": {"type": "string", "example": "password"},
                    },
                },
            },
            "examples": {
                "objectExample": {
                    "summary": "summary",
                    "value": {"username": "username1", "email": "john.doe@email.com", "password": "password1"},
                },
            },
        },
    }
    schema = schemathesis.openapi.from_dict(raw_schema)
    operation = schema["/register"]["POST"]
    extracted = [example_to_dict(example) for example in extract_from_schemas(operation)]
    assert extracted == [
        {
            "media_type": "application/json",
            "value": {"username": "username", "email": "john.doe@email.com", "password": "password"},
        }
    ]
    extracted = [example_to_dict(example) for example in extract_top_level(operation)]
    assert extracted == [
        {
            "media_type": "application/json",
            "value": {"email": "john.doe@email.com", "password": "password1", "username": "username1"},
        },
    ]


def test_openapi_2_example():
    raw_schema = {
        "swagger": "2.0",
        "info": {"version": "0.1.0", "title": "Item List API", "license": {"name": "Test"}},
        "schemes": ["http"],
        "host": "localhost:8083",
        "securityDefinitions": {"ApiKeyAuth": {"in": "header", "name": "Authorization", "type": "apiKey"}},
        "paths": {
            "/items": {
                "post": {
                    "summary": "Add a new item to the list",
                    "operationId": "addItem",
                    "tags": ["items"],
                    "parameters": [
                        {
                            "in": "body",
                            "name": "Item",
                            "required": True,
                            "description": "item object for POST body",
                            "schema": {"$ref": "#/definitions/Item"},
                        }
                    ],
                    "responses": {
                        "201": {"description": "Item added successfully", "schema": {"$ref": "#/definitions/Item"}},
                        "400": {"description": "Bad Request", "schema": {"$ref": "#/definitions/Error"}},
                        "500": {"description": "Internal server error", "schema": {"$ref": "#/definitions/Error"}},
                        "401": {"description": "Access token is missing or invalid"},
                    },
                    "consumes": ["application/json"],
                    "produces": ["application/json"],
                    "security": [{"ApiKeyAuth": []}],
                }
            }
        },
        "definitions": {
            "Items": {"items": {"$ref": "#/definitions/Item"}, "type": "array"},
            "Error": {
                "type": "object",
                "required": ["message"],
                "properties": {"message": {"type": "string"}, "data": {"type": "object"}},
            },
            "Item": {
                "type": "object",
                "required": ["title", "description"],
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "ID of the list item.",
                        "format": "uuid",
                        "example": "415feabd-9114-44af-bc78-479299dadc1e",
                    },
                    "title": {"type": "string", "description": "Title of the item.", "example": "Learn Music"},
                    "description": {
                        "type": "string",
                        "description": "More detailed description of the item.",
                        "example": "learn to play drums",
                    },
                    "year": {"type": "string", "description": "Target year", "pattern": "^\\d{4}", "example": "1987"},
                },
                "example": {"title": "Reading", "description": "Read a comic"},
            },
        },
    }
    schema = schemathesis.openapi.from_dict(raw_schema)
    operation = schema["/items"]["POST"]
    extracted = [example_to_dict(example) for example in extract_from_schemas(operation)]
    assert extracted == [
        {
            "value": {
                "id": "415feabd-9114-44af-bc78-479299dadc1e",
                "title": "Learn Music",
                "description": "learn to play drums",
                "year": "1987",
            },
            "media_type": "application/json",
        }
    ]
    extracted = [example_to_dict(example) for example in extract_top_level(operation)]
    assert extracted == [
        {
            "value": {"title": "Reading", "description": "Read a comic"},
            "media_type": "application/json",
        }
    ]


def test_property_examples_behind_ref():
    raw_schema = {
        "swagger": "2.0",
        "info": {"version": "0.1.0", "title": "Item List API"},
        "schemes": ["http"],
        "host": "localhost:8083",
        "securityDefinitions": {"ApiKeyAuth": {"in": "header", "name": "Authorization", "type": "apiKey"}},
        "paths": {
            "/trees": {
                "post": {
                    "responses": {"200": {"description": "Ok"}},
                    "parameters": [
                        {
                            "in": "body",
                            "name": "Tree",
                            "schema": {"$ref": "#/definitions/Tree"},
                            "description": "tree to create",
                            "required": True,
                        }
                    ],
                }
            },
        },
        "definitions": {
            "Tree": {
                "properties": {
                    "id": {
                        "format": "uuid",
                        "type": "string",
                        "example": "415feabd-9114-44af-bc78-479299dadc1e",
                    },
                    "year": {"pattern": "^\\d{4}", "type": "string", "example": "2020"},
                    "branches": {"items": {"$ref": "#/definitions/Branch"}, "type": "array"},
                    "description": {"type": "string", "example": "white birch tree"},
                    "name": {"type": "string", "example": "Birch"},
                    "bird": {"$ref": "#/definitions/Bird", "type": "object"},
                },
                "required": ["name", "description"],
                "type": "object",
                "example": {"description": "Pine tree", "name": "Pine"},
            },
            "Nest": {
                "properties": {
                    "eggs": {"items": {"$ref": "#/definitions/Egg"}, "type": "array"},
                    "description": {"type": "string", "example": "first nest"},
                    "name": {"type": "string", "example": "nest1"},
                },
                "required": ["name"],
                "type": "object",
            },
            "Bark": {
                "properties": {
                    "description": {"type": "string", "example": "brown bark"},
                    "name": {"type": "string", "example": "bark1"},
                },
                "required": ["name", "description"],
                "type": "object",
            },
            "Leaf": {
                "properties": {
                    "description": {"type": "string", "example": "main leaf"},
                    "name": {"type": "string", "example": "leaf1"},
                },
                "required": ["name", "description"],
                "type": "object",
            },
            "Branch": {
                "properties": {
                    "leaves": {"items": {"$ref": "#/definitions/Leaf"}, "type": "array"},
                    "bark": {"$ref": "#/definitions/Bark", "type": "object"},
                    "description": {"type": "string", "example": "main branch"},
                    "name": {"type": "string", "example": "branch1"},
                },
                "required": ["name", "description"],
                "type": "object",
            },
            "Bird": {
                "properties": {
                    "nest": {"$ref": "#/definitions/Nest", "type": "object"},
                    "description": {"type": "string", "example": "brown sparrow"},
                    "name": {"type": "string", "example": "sparrow"},
                },
                "required": ["name", "description"],
                "type": "object",
            },
            "Trees": {"items": {"$ref": "#/definitions/Tree"}, "type": "array"},
            "Egg": {
                "properties": {
                    "description": {"type": "string", "example": "first egg"},
                    "name": {"type": "string", "example": "egg1"},
                },
                "required": ["name", "description"],
                "type": "object",
            },
        },
    }
    schema = schemathesis.openapi.from_dict(raw_schema)
    operation = schema["/trees"]["POST"]
    extracted = [example_to_dict(example) for example in extract_from_schemas(operation)]
    assert extracted == [
        {
            "value": {
                "id": "415feabd-9114-44af-bc78-479299dadc1e",
                "year": "2020",
                "branches": [
                    {
                        "leaves": [{"description": "main leaf", "name": "leaf1"}],
                        "bark": {"description": "brown bark", "name": "bark1"},
                        "description": "main branch",
                        "name": "branch1",
                    }
                ],
                "description": "white birch tree",
                "name": "Birch",
                "bird": {
                    "nest": {
                        "eggs": [{"description": "first egg", "name": "egg1"}],
                        "description": "first nest",
                        "name": "nest1",
                    },
                    "description": "brown sparrow",
                    "name": "sparrow",
                },
            },
            "media_type": "application/json",
        }
    ]


def test_property_examples_with_all_of():
    # See GH-2375
    raw_schema = {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/peers": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/peer"},
                            }
                        }
                    },
                    "responses": {"200": {"description": "Successful operation"}},
                }
            }
        },
        "components": {
            "schemas": {
                "peer": {
                    "type": "object",
                    "properties": {"outbound_proxy": {"$ref": "#/components/schemas/outbound_proxy_with_port"}},
                    "required": ["outbound_proxy"],
                },
                "outbound_proxy_common": {
                    "type": "object",
                    "properties": {"host": {"type": "string", "format": "ipv4", "example": "10.22.22.191"}},
                    "required": ["host"],
                },
                "outbound_proxy_with_port": {
                    "allOf": [
                        {"$ref": "#/components/schemas/outbound_proxy_common"},
                        {
                            "type": "object",
                            "properties": {"port": {"type": "integer", "example": 8080}},
                            "required": ["port"],
                        },
                    ]
                },
            }
        },
    }
    schema = schemathesis.openapi.from_dict(raw_schema)
    operation = schema["/peers"]["POST"]
    extracted = [example_to_dict(example) for example in extract_from_schemas(operation)]
    assert extracted == [
        {
            "value": {"outbound_proxy": {"host": "10.22.22.191", "port": 8080}},
            "media_type": "application/json",
        }
    ]


def content(schema, **kwargs):
    return {
        "description": "",
        "content": {
            "application/json": {"schema": schema, **kwargs},
        },
    }


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"description": "Ok"}, {}),
        ({"$ref": "#/components/responses/NoExamples"}, {}),
        (
            {"$ref": "#/components/responses/SingleExample"},
            {
                "Item": [
                    {"id": "123456"},
                ],
            },
        ),
        (
            {"$ref": "#/components/responses/OneExample"},
            {
                "Item": [
                    {"id": "123456"},
                ],
            },
        ),
        (
            {"$ref": "#/components/responses/TwoExamples"},
            {
                "Item": [
                    {"id": "123456"},
                    {"id": "456789"},
                ],
            },
        ),
        (
            content({"$ref": "#/components/schemas/Item"}, examples={"Example1": {"value": {"id": "123456"}}}),
            {
                "Item": [
                    {"id": "123456"},
                ],
            },
        ),
        (
            # No `value` inside
            content({"$ref": "#/components/schemas/Item"}, examples={"Example1": {"externalValue": ""}}),
            {},
        ),
        (
            content({"$ref": "#/components/schemas/Item"}, **{"x-examples": {"Example1": {"value": {"id": "123456"}}}}),
            {
                "Item": [
                    {"id": "123456"},
                ],
            },
        ),
        (
            content({"$ref": "#/components/schemas/Item"}, **{"x-examples": [{"id": "123456"}]}),
            {
                "Item": [
                    {"id": "123456"},
                ],
            },
        ),
        (
            content({"$ref": "#/components/schemas/Item"}, **{"x-example": {"id": "123456"}}),
            {
                "Item": [
                    {"id": "123456"},
                ],
            },
        ),
        (
            content(
                {"properties": {"id": {"type": "string"}}},
                examples={"Example1": {"value": {"id": "123456"}}},
            ),
            {
                "200/application/json": [
                    {"id": "123456"},
                ],
            },
        ),
    ],
)
def test_find_in_responses(ctx, response, expected):
    schema = ctx.openapi.build_schema(
        {
            "/items/{itemId}/": {
                "get": {
                    "parameters": [{"name": "itemId", "in": "path", "schema": {"type": "string"}, "required": True}],
                    "responses": {"200": response},
                }
            }
        },
        components={
            "schemas": {
                "Item": {
                    "properties": {
                        "id": {
                            "type": "string",
                        }
                    }
                }
            },
            "responses": {
                "NoExamples": content({"$ref": "#/components/schemas/Item"}),
                "OneExample": content(
                    {"$ref": "#/components/schemas/Item"}, examples={"Example1": {"value": {"id": "123456"}}}
                ),
                "TwoExamples": content(
                    {"$ref": "#/components/schemas/Item"},
                    examples={
                        "Example1": {"value": {"id": "123456"}},
                        "Example2": {"value": {"id": "456789"}},
                    },
                ),
                "SingleExample": content({"$ref": "#/components/schemas/Item"}, example={"id": "123456"}),
            },
        },
    )
    schema = schemathesis.openapi.from_dict(schema)
    operation = schema["/items/{itemId}/"]["get"]
    assert find_in_responses(operation) == expected

    if expected:
        strategy = strategies.combine(operation.get_strategies_from_examples())
        collected = []

        @given(strategy)
        def test(case):
            collected.append(case.path_parameters)

        test()

        assert collected == [
            {"itemId": value} for group in expected.values() for values in group for value in values.values()
        ]


def test_find_in_responses_only_in_2xx(ctx):
    schema = ctx.openapi.build_schema(
        {
            "/items/{id}/": {
                "get": {
                    "parameters": [{"name": "id", "in": "path", "schema": {"type": "string"}, "required": True}],
                    "responses": {
                        "400": content(
                            {
                                "properties": {
                                    "id": {"type": "string"},
                                }
                            },
                            examples={
                                "Example1": {"value": {"id": "123456"}},
                            },
                        )
                    },
                }
            }
        }
    )
    schema = schemathesis.openapi.from_dict(schema)
    operation = schema["/items/{id}/"]["get"]
    assert find_in_responses(operation) == {}


@pytest.mark.parametrize(
    ("examples", "name", "expected"),
    [
        (
            {"Item": [{"id": "123"}, {"id": "456"}]},
            "id",
            ["123", "456"],
        ),
        (
            {"Item": [{"itemId": "123"}, {"itemId": "456"}]},
            "itemId",
            ["123", "456"],
        ),
        (
            {
                "Item": [
                    {"item": [{"itemId": "123"}, {"itemId": "789"}, {"unknown": 0}]},
                    {"itemId": "456"},
                    {"itemId": 789},
                    {"item": {"itemId": "42"}},
                    {"item": 55},
                    {"item": [55]},
                    {"item": [{"id": "143"}], "paginationInfo": {}},
                ]
            },
            "itemId",
            ["123", "789", "456", 789, "42", 55, "143"],
        ),
        (
            {
                "ItemResult": [
                    {"item": [{"id": "143"}, {"id": 55}, [], {}], "paginationInfo": {}},
                ]
            },
            "itemId",
            ["143", 55],
        ),
        (
            {"Item": [{"id": "123"}, {"id": "456"}]},
            "itemId",
            ["123", "456"],
        ),
        (
            {"Item": [{"ItemId": "123"}, {"ITEMID": "456"}]},
            "itemId",
            ["123", "456"],
        ),
        (
            {"Product": [{"productId": "123"}, {"product_id": "456"}]},
            "id",
            ["123", "456"],
        ),
        (
            {"User": [{"userId": "123"}, {"user_id": "456"}], "Item": [{"itemId": "789"}]},
            "userId",
            ["123", "456"],
        ),
        (
            {"User": [{"name": "John"}, {"age": 30}]},
            "id",
            [],
        ),
        (
            {"User": [{"name": "John"}, {"age": 30}]},
            "name",
            ["John"],
        ),
        (
            {"User": [{"name": "John"}]},
            "unknown",
            [],
        ),
        (
            {"User": [None]},
            "unknown",
            [],
        ),
    ],
)
def test_find_matching_in_responses(examples, name, expected):
    assert list(find_matching_in_responses(examples, name)) == expected


def test_find_matching_in_responses_yields_all():
    examples = {"Item": [{"id": "123"}, {"id": "456"}], "Product": [{"id": "789"}, {"productId": "101112"}]}
    result = list(find_matching_in_responses(examples, "id"))
    assert result == ["123", "456", "789", "101112"]


def test_find_matching_in_responses_empty():
    assert list(find_matching_in_responses({}, "id")) == []
