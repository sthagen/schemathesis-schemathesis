from __future__ import annotations

import os
import platform
from functools import lru_cache, wraps
from typing import Any, Callable, TypeVar

import click
import pytest
import requests
import urllib3
from syrupy import SnapshotAssertion

import schemathesis
from schemathesis import Case
from schemathesis.checks import not_a_server_error
from schemathesis.core.deserialization import deserialize_yaml
from schemathesis.core.transforms import deepclone
from schemathesis.runner import Status, from_schema
from schemathesis.runner.events import AfterExecution, EngineEvent, EngineFinished, Initialized, NonFatalError
from schemathesis.schemas import BaseSchema

HERE = os.path.dirname(os.path.abspath(__file__))


def get_schema_path(schema_name: str) -> str:
    return os.path.join(HERE, "data", schema_name)


SIMPLE_PATH = get_schema_path("simple_swagger.yaml")


def get_schema(schema_name: str = "simple_swagger.yaml", **kwargs: Any) -> BaseSchema:
    schema = make_schema(schema_name, **kwargs)
    return schemathesis.openapi.from_dict(schema)


def merge_recursively(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Merge two dictionaries recursively."""
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_recursively(a[key], b[key])
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a


def make_schema(schema_name: str = "simple_swagger.yaml", **kwargs: Any) -> dict[str, Any]:
    schema = deepclone(load_schema(schema_name))
    return merge_recursively(kwargs, schema)


@lru_cache
def load_schema(schema_name: str) -> dict[str, Any]:
    path = get_schema_path(schema_name)
    with open(path) as fd:
        return deserialize_yaml(fd)


def integer(**kwargs: Any) -> dict[str, Any]:
    return {"type": "integer", "in": "query", **kwargs}


def as_param(*parameters: Any) -> dict[str, Any]:
    return {"paths": {"/users": {"get": {"parameters": list(parameters), "responses": {"200": {"description": "OK"}}}}}}


def noop(value: Any) -> bool:
    return True


def _assert_value(value: Any, type: type, predicate: Callable = noop) -> None:
    assert isinstance(value, type)
    assert predicate(value)


def assert_int(value: Any, predicate: Callable = noop) -> None:
    _assert_value(value, int, predicate)


def assert_str(value: Any, predicate: Callable = noop) -> None:
    _assert_value(value, str, predicate)


def assert_list(value: Any, predicate: Callable = noop) -> None:
    _assert_value(value, list, predicate)


def assert_requests_call(case: Case):
    """Verify that all generated input parameters are usable by requests."""
    with pytest.raises((requests.exceptions.ConnectionError, urllib3.exceptions.NewConnectionError)):
        # On Windows it may take time to get the connection error, hence we set a timeout
        case.call(base_url="http://127.0.0.1:1", timeout=0.001)


def strip_style_win32(styled_output: str) -> str:
    """Strip text style on Windows.

    `click.style` produces ANSI sequences, however they were not supported
    by PowerShell until recently and colored output is created differently.
    """
    if platform.system() == "Windows":
        return click.unstyle(styled_output)
    return styled_output


def flaky(*, max_runs: int, min_passes: int):
    """A decorator to mark a test as flaky."""

    def decorate(test):
        @wraps(test)
        def inner(*args, **kwargs):
            snapshot_fixture_name = None
            snapshot_cli = None
            for name, kwarg in kwargs.items():
                if isinstance(kwarg, SnapshotAssertion):
                    snapshot_fixture_name = name
                    snapshot_cli = kwarg
                    break
            runs = passes = 0
            while passes < min_passes:
                runs += 1
                try:
                    test(*args, **kwargs)
                except Exception:
                    if snapshot_fixture_name is not None:
                        kwargs[snapshot_fixture_name] = snapshot_cli.rebuild()
                    if runs >= max_runs:
                        raise
                else:
                    passes += 1

        return inner

    return decorate


E = TypeVar("E", bound=EngineEvent)


class EventStream:
    def __init__(self, schema, **options):
        options.setdefault("checks", [not_a_server_error])
        self.schema = from_schema(schema, **options)

    def execute(self) -> EventStream:
        self.events = list(self.schema.execute())
        return self

    def find(self, ty: type[E], **attrs) -> E | None:
        """Find first event of specified type matching all attribute predicates."""
        return next(
            (
                e
                for e in self.events
                if isinstance(e, ty)
                and all(v(getattr(e, k)) if callable(v) else getattr(e, k) == v for k, v in attrs.items())
            ),
            None,
        )

    def find_all(self, ty: type[E], **attrs) -> list[E]:
        """Find all events of specified type matching all attribute predicates."""
        return [
            e
            for e in self.events
            if isinstance(e, ty)
            and all(v(getattr(e, k)) if callable(v) else getattr(e, k) == v for k, v in attrs.items())
        ]

    def assert_errors(self):
        assert self.find(NonFatalError) is not None

    def assert_no_errors(self):
        assert self.find(NonFatalError) is None

    def assert_after_execution_status(self, status: Status) -> None:
        assert self.find(AfterExecution).status == status

    @property
    def started(self) -> Initialized | None:
        return self.find(Initialized)

    @property
    def finished(self) -> EngineFinished | None:
        return self.find(EngineFinished)
