import time
import uuid

from schemathesis.config import ProjectConfig
from schemathesis.core import Specification
from schemathesis.engine import events
from schemathesis.schemas import ApiStatistic


class LoadingStarted(events.EngineEvent):
    __slots__ = ("id", "timestamp", "location")

    def __init__(self, *, location: str) -> None:
        self.id = uuid.uuid4()
        self.timestamp = time.time()
        self.location = location


class LoadingFinished(events.EngineEvent):
    __slots__ = (
        "id",
        "timestamp",
        "location",
        "duration",
        "base_url",
        "base_path",
        "specification",
        "statistic",
        "schema",
        "config",
    )

    def __init__(
        self,
        *,
        location: str,
        start_time: float,
        base_url: str,
        base_path: str,
        specification: Specification,
        statistic: ApiStatistic,
        schema: dict,
        config: ProjectConfig,
    ) -> None:
        self.id = uuid.uuid4()
        self.timestamp = time.time()
        self.location = location
        self.duration = self.timestamp - start_time
        self.base_url = base_url
        self.specification = specification
        self.statistic = statistic
        self.schema = schema
        self.base_path = base_path
        self.config = config
