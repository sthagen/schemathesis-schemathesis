from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable, Iterable, Iterator, Optional

from schemathesis.config import ChecksConfig
from schemathesis.core.failures import (
    CustomFailure,
    Failure,
    FailureGroup,
    MalformedJson,
    ResponseTimeExceeded,
    ServerError,
)
from schemathesis.core.registries import Registry
from schemathesis.core.transport import Response
from schemathesis.generation.overrides import Override

if TYPE_CHECKING:
    from requests.models import CaseInsensitiveDict

    from schemathesis.engine.recorder import ScenarioRecorder
    from schemathesis.generation.case import Case

CheckFunction = Callable[["CheckContext", "Response", "Case"], Optional[bool]]


class CheckContext:
    """Context for Schemathesis checks.

    Provides access to broader test execution data beyond individual test cases.
    """

    override: Override | None
    auth: tuple[str, str] | None
    headers: CaseInsensitiveDict | None
    config: ChecksConfig
    transport_kwargs: dict[str, Any] | None
    recorder: ScenarioRecorder | None
    checks: list[CheckFunction]

    __slots__ = ("override", "auth", "headers", "config", "transport_kwargs", "recorder", "checks")

    def __init__(
        self,
        override: Override | None,
        auth: tuple[str, str] | None,
        headers: CaseInsensitiveDict | None,
        config: ChecksConfig,
        transport_kwargs: dict[str, Any] | None,
        recorder: ScenarioRecorder | None = None,
    ) -> None:
        self.override = override
        self.auth = auth
        self.headers = headers
        self.config = config
        self.transport_kwargs = transport_kwargs
        self.recorder = recorder
        self.checks = []
        for check in CHECKS.get_all():
            name = check.__name__
            if self.config.get_by_name(name=name).enabled:
                self.checks.append(check)
        if self.config.max_response_time.enabled:
            self.checks.append(max_response_time)

    def find_parent(self, *, case_id: str) -> Case | None:
        if self.recorder is not None:
            return self.recorder.find_parent(case_id=case_id)
        return None

    def find_related(self, *, case_id: str) -> Iterator[Case]:
        if self.recorder is not None:
            yield from self.recorder.find_related(case_id=case_id)

    def find_response(self, *, case_id: str) -> Response | None:
        if self.recorder is not None:
            return self.recorder.find_response(case_id=case_id)
        return None

    def record_case(self, *, parent_id: str, case: Case) -> None:
        if self.recorder is not None:
            self.recorder.record_case(parent_id=parent_id, transition=None, case=case)

    def record_response(self, *, case_id: str, response: Response) -> None:
        if self.recorder is not None:
            self.recorder.record_response(case_id=case_id, response=response)


CHECKS = Registry[CheckFunction]()
check = CHECKS.register


@check
def not_a_server_error(ctx: CheckContext, response: Response, case: Case) -> bool | None:
    """A check to verify that the response is not a server-side error."""
    from schemathesis.specs.graphql.schemas import GraphQLSchema
    from schemathesis.specs.graphql.validation import validate_graphql_response
    from schemathesis.specs.openapi.utils import expand_status_codes

    expected_statuses = expand_status_codes(ctx.config.not_a_server_error.expected_statuses or [])

    status_code = response.status_code
    if status_code not in expected_statuses:
        raise ServerError(operation=case.operation.label, status_code=status_code)
    if isinstance(case.operation.schema, GraphQLSchema):
        try:
            data = response.json()
            validate_graphql_response(case, data)
        except json.JSONDecodeError as exc:
            raise MalformedJson.from_exception(operation=case.operation.label, exc=exc) from None
    return None


DEFAULT_MAX_RESPONSE_TIME = 10.0


def max_response_time(ctx: CheckContext, response: Response, case: Case) -> bool | None:
    limit = ctx.config.max_response_time.limit or DEFAULT_MAX_RESPONSE_TIME
    elapsed = response.elapsed
    if elapsed > limit:
        raise ResponseTimeExceeded(
            operation=case.operation.label,
            message=f"Actual: {elapsed:.2f}ms\nLimit: {limit * 1000:.2f}ms",
            elapsed=elapsed,
            deadline=limit,
        )
    return None


def run_checks(
    *,
    case: Case,
    response: Response,
    ctx: CheckContext,
    checks: Iterable[CheckFunction],
    on_failure: Callable[[str, set[Failure], Failure], None],
    on_success: Callable[[str, Case], None] | None = None,
) -> set[Failure]:
    """Run a set of checks against a response."""
    collected: set[Failure] = set()

    for check in checks:
        name = check.__name__
        try:
            skip_check = check(ctx, response, case)
            if not skip_check and on_success:
                on_success(name, case)
        except Failure as failure:
            on_failure(name, collected, failure.with_traceback(None))
        except AssertionError as exc:
            custom_failure = CustomFailure(
                operation=case.operation.label,
                title=f"Custom check failed: `{name}`",
                message=str(exc),
                exception=exc,
            )
            on_failure(name, collected, custom_failure)
        except FailureGroup as group:
            for sub_failure in group.exceptions:
                on_failure(name, collected, sub_failure)

    return collected
