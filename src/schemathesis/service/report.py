import json
import tarfile
import threading
import time
from io import BytesIO
from queue import Queue
from typing import Any, Optional

import attr

from ..cli.context import ExecutionContext
from ..cli.handlers import EventHandler
from ..runner.events import ExecutionEvent
from . import ServiceClient, events
from .constants import STOP_MARKER, WORKER_JOIN_TIMEOUT
from .metadata import Metadata
from .models import AnonymousUploadResponse
from .serialization import serialize_event


@attr.s(slots=True)
class ReportWriter:
    """Schemathesis.io test run report.

    Simplifies adding new files to the archive.
    """

    _tar: tarfile.TarFile = attr.ib()
    _events_count: int = attr.ib(default=0)

    def _add_json_file(self, name: str, data: Any) -> None:
        buffer = BytesIO()
        buffer.write(json.dumps(data, separators=(",", ":")).encode())
        buffer.seek(0)
        info = tarfile.TarInfo(name=name)
        info.size = len(buffer.getbuffer())
        info.mtime = int(time.time())
        self._tar.addfile(info, buffer)

    def add_metadata(self, slug: Optional[str], metadata: Metadata) -> None:
        data = {
            # API identifier on the Schemathesis.io side (optional)
            "slug": slug,
            ""
            # Metadata about CLI environment
            "environment": attr.asdict(metadata),
        }
        self._add_json_file("metadata.json", data)

    def add_event(self, event: ExecutionEvent) -> None:
        """Add an execution event to the report."""
        self._events_count += 1
        self._add_json_file(f"events/{self._events_count}.json", serialize_event(event))


@attr.s(slots=True)  # pragma: no mutate
class ReportHandler(EventHandler):
    client: ServiceClient = attr.ib()  # pragma: no mutate
    api_slug: Optional[str] = attr.ib()  # pragma: no mutate
    out_queue: Queue = attr.ib()  # pragma: no mutate
    in_queue: Queue = attr.ib(factory=Queue)  # pragma: no mutate
    worker: threading.Thread = attr.ib(init=False)  # pragma: no mutate

    def __attrs_post_init__(self) -> None:
        self.worker = threading.Thread(
            target=start,
            kwargs={
                "client": self.client,
                "api_slug": self.api_slug,
                "in_queue": self.in_queue,
                "out_queue": self.out_queue,
            },
        )
        self.worker.start()

    def handle_event(self, context: ExecutionContext, event: ExecutionEvent) -> None:
        self.in_queue.put(event)

    def shutdown(self) -> None:
        self._stop_worker()

    def _stop_worker(self) -> None:
        self.in_queue.put(STOP_MARKER)
        self.worker.join(WORKER_JOIN_TIMEOUT)


def start(client: ServiceClient, api_slug: Optional[str], in_queue: Queue, out_queue: Queue) -> None:
    """Create a compressed ``tar.gz`` file during the run & upload it to Schemathesis.io when the run is finished."""
    payload = BytesIO()
    try:
        with tarfile.open(mode="w:gz", fileobj=payload) as tar:
            writer = ReportWriter(tar)
            writer.add_metadata(api_slug, Metadata())
            while True:
                event = in_queue.get()
                if event is STOP_MARKER:
                    # Happens only if an exception happened in another thread
                    break
                # Add every event to the report
                writer.add_event(event)
                if event.is_terminal:
                    break
        response = client.upload_report(payload.getvalue())
        if isinstance(response, AnonymousUploadResponse):
            event = events.SuccessfulAnonymousUpload(message=response.message, signup_url=response.signup_url)
        else:
            event = events.SuccessfulUpload(message=response.message, report_url=response.report_url)
        out_queue.put(event)
        # TODO. do not upload test runs that did not start properly / interrupted ones
    except Exception as exc:
        out_queue.put(events.Error(exc))
