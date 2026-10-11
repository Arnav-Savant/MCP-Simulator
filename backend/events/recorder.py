from typing import Any, Callable

from events.model import Event, now


class Recorder:
    def __init__(self, run_id: str, scenario_id: str | None, on_emit: Callable[[], None] | None = None):
        self.run_id = run_id
        self.scenario_id = scenario_id
        self.events: list[Event] = []
        self.finished = False
        self._on_emit = on_emit

    def emit(self, component: str, operation: str, status: str, kind: str, message: str, **extra: Any) -> Event:
        seq = len(self.events) + 1
        event = Event(
            id=f"{self.run_id}-{seq:04d}",
            run_id=self.run_id,
            scenario_id=self.scenario_id,
            seq=seq,
            component=component,
            operation=operation,
            status=status,
            kind=kind,
            message=message,
            ts=now(),
            **extra,
        )
        self.events.append(event)
        if self._on_emit:
            self._on_emit()
        return event
