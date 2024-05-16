import json
import pathlib

import pytest

import schemathesis
import hypothesis
from hypothesis import HealthCheck, Phase, Verbosity
from schemathesis.runner import from_schema

CURRENT_DIR = pathlib.Path(__file__).parent.absolute()
CATALOG_DIR = CURRENT_DIR / "data"


def read_json_from_catalog(path: str):
    with (CATALOG_DIR / path).open() as fd:
        return json.load(fd)


# Small size (~2k lines in YAML)
BBCI = read_json_from_catalog("bbci.json")
BBCI_SCHEMA = schemathesis.from_dict(BBCI)
BBCI_OPERATIONS = list(BBCI_SCHEMA.get_all_operations())
# Medium size (~8k lines in YAML)
VMWARE = read_json_from_catalog("vmware.json")
VMWARE_SCHEMA = schemathesis.from_dict(VMWARE)
VMWARE_OPERATIONS = list(VMWARE_SCHEMA.get_all_operations())
# Large size (~92k lines in YAML)
STRIPE = read_json_from_catalog("stripe.json")
STRIPE_SCHEMA = schemathesis.from_dict(STRIPE)
# Medium GraphQL schema (~6k lines)
UNIVERSE = read_json_from_catalog("universe.json")
UNIVERSE_SCHEMA = schemathesis.graphql.from_dict(UNIVERSE)


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "raw_schema, loader",
    [
        (BBCI, schemathesis.from_dict),
        (VMWARE, schemathesis.from_dict),
        (UNIVERSE, schemathesis.graphql.from_dict),
    ],
    ids=("bbci", "vmware", "universe"),
)
def test_get_all_operations(raw_schema, loader):
    schema = loader(raw_schema)

    for _ in schema.get_all_operations():
        pass


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "raw_schema, loader",
    [
        (BBCI, schemathesis.from_dict),
        (VMWARE, schemathesis.from_dict),
        (UNIVERSE, schemathesis.graphql.from_dict),
    ],
    ids=("bbci", "vmware", "universe"),
)
def test_length(raw_schema, loader):
    schema = loader(raw_schema)
    _ = len(schema)


# Schemas with pre-populated cache
BBCI_OPERATION_ID = "Get_Categories_"
BBCI_OPERATION_KEY = ("/categories", "get")
BBCI_SCHEMA_WITH_OPERATIONS_CACHE = schemathesis.from_dict(BBCI)
BBCI_SCHEMA_WITH_OPERATIONS_CACHE.get_operation_by_id(BBCI_OPERATION_ID)
_ = BBCI_SCHEMA_WITH_OPERATIONS_CACHE.operations
VMWARE_OPERATION_ID = "listProblemEvents"
VMWARE_OPERATION_KEY = ("/entities/problems", "get")
VMWARE_SCHEMA_WITH_OPERATIONS_CACHE = schemathesis.from_dict(VMWARE)
VMWARE_SCHEMA_WITH_OPERATIONS_CACHE.get_operation_by_id(VMWARE_OPERATION_ID)
_ = VMWARE_SCHEMA_WITH_OPERATIONS_CACHE.operations
UNIVERSE_SCHEMA_WITH_OPERATIONS_CACHE = schemathesis.graphql.from_dict(UNIVERSE)
_ = UNIVERSE_SCHEMA_WITH_OPERATIONS_CACHE.operations
UNIVERSE_OPERATION_KEY = ("Query", "manageTickets")


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "raw_schema, key, loader",
    [
        (BBCI, BBCI_OPERATION_KEY, schemathesis.from_dict),
        (VMWARE, VMWARE_OPERATION_KEY, schemathesis.from_dict),
        (UNIVERSE, UNIVERSE_OPERATION_KEY, schemathesis.graphql.from_dict),
    ],
    ids=("bbci", "vmware", "universe"),
)
def test_get_operation_single(raw_schema, key, loader):
    schema = loader(raw_schema)
    current = schema
    for segment in key:
        current = current[segment]


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "schema, key",
    [
        (BBCI_SCHEMA_WITH_OPERATIONS_CACHE, BBCI_OPERATION_KEY),
        (VMWARE_SCHEMA_WITH_OPERATIONS_CACHE, VMWARE_OPERATION_KEY),
        (UNIVERSE_SCHEMA_WITH_OPERATIONS_CACHE, UNIVERSE_OPERATION_KEY),
    ],
    ids=("bbci", "vmware", "universe"),
)
def test_get_operation_repeatedly(schema, key):
    current = schema
    for segment in key:
        current = current[segment]


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "raw_schema, key",
    [(BBCI, BBCI_OPERATION_ID), (VMWARE, VMWARE_OPERATION_ID)],
    ids=("bbci", "vmware"),
)
def test_get_operation_by_id_single(raw_schema, key):
    schema = schemathesis.from_dict(raw_schema)
    _ = schema.get_operation_by_id(key)


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "schema, key",
    [
        (BBCI_SCHEMA_WITH_OPERATIONS_CACHE, BBCI_OPERATION_ID),
        (VMWARE_SCHEMA_WITH_OPERATIONS_CACHE, VMWARE_OPERATION_ID),
    ],
    ids=("bbci", "vmware"),
)
def test_get_operation_by_id_repeatedly(schema, key):
    _ = schema.get_operation_by_id(key)


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "raw_schema, key",
    [
        (BBCI, "#/paths/~1categories/get"),
        (VMWARE, "#/paths/~1entities~1problems/get"),
    ],
    ids=("bbci", "vmware"),
)
def test_get_operation_by_reference_single(raw_schema, key):
    schema = schemathesis.from_dict(raw_schema)
    _ = schema.get_operation_by_reference(key)


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "schema, key",
    [
        (BBCI_SCHEMA_WITH_OPERATIONS_CACHE, "#/paths/~1categories/get"),
        (VMWARE_SCHEMA_WITH_OPERATIONS_CACHE, "#/paths/~1entities~1problems/get"),
    ],
    ids=("bbci", "vmware"),
)
def test_get_operation_by_reference_repeatedly(schema, key):
    _ = schema.get_operation_by_reference(key)


@pytest.mark.benchmark
@pytest.mark.parametrize("operations", [BBCI_OPERATIONS, VMWARE_OPERATIONS], ids=("bbci", "vmware"))
def test_as_json_schema(operations):
    for operation in operations:
        for parameter in operation.ok().iter_parameters():
            _ = parameter.as_json_schema(operation)


@pytest.mark.benchmark
def test_events():
    runner = from_schema(
        BBCI_SCHEMA,
        checks=(),
        count_operations=False,
        count_links=False,
        hypothesis_settings=hypothesis.settings(
            deadline=None,
            database=None,
            max_examples=1,
            derandomize=True,
            suppress_health_check=list(HealthCheck),
            phases=[Phase.explicit, Phase.generate],
            verbosity=Verbosity.quiet,
        ),
    )
    for _ in runner.execute():
        pass


@pytest.mark.benchmark
@pytest.mark.parametrize("raw_schema", [BBCI, VMWARE, STRIPE], ids=("bbci", "vmware", "stripe"))
def test_rewritten_components(raw_schema):
    schema = schemathesis.from_dict(raw_schema)

    _ = schema.rewritten_components


@pytest.mark.benchmark
@pytest.mark.parametrize("raw_schema", [BBCI, VMWARE, STRIPE], ids=("bbci", "vmware", "stripe"))
def test_links_count(raw_schema):
    schema = schemathesis.from_dict(raw_schema)

    _ = schema.links_count