import json
import os
import threading
import time

from server.build import PREFIX

TERMINAL_OPS = {"completed", "failed"}


class StderrPump:
    """Owns the pipe wired to the server's stderr; parses MCPLAB_EVENT lines on a reader thread."""

    def __init__(self):
        read_fd, write_fd = os.pipe()
        self.write_file = os.fdopen(write_fd, "w")
        self._read_file = os.fdopen(read_fd, "r", errors="replace")
        self._cond = threading.Condition()
        self._events: list[dict] = []
        self.other_lines: list[str] = []
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        for line in self._read_file:
            line = line.rstrip("\n")
            with self._cond:
                if line.startswith(PREFIX):
                    try:
                        self._events.append(json.loads(line[len(PREFIX):]))
                    except json.JSONDecodeError:
                        self.other_lines.append(line)
                else:
                    self.other_lines.append(line)
                self._cond.notify_all()

    def drain(self, expected_terminal: int, timeout: float = 3.0) -> tuple[list[dict], bool]:
        """Block until `expected_terminal` completed/failed events arrived (or timeout); return and clear all."""
        deadline = time.monotonic() + timeout
        with self._cond:
            while sum(1 for e in self._events if e["op"] in TERMINAL_OPS) < expected_terminal:
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                self._cond.wait(left)
            events = sorted(self._events, key=lambda e: e["n"])
            complete = sum(1 for e in events if e["op"] in TERMINAL_OPS) >= expected_terminal
            self._events = []
            return events, complete

    def settle(self, seconds: float = 0.2) -> None:
        """Short grace period so diagnostic stderr text from a dying process is captured."""
        time.sleep(seconds)

    def close(self) -> None:
        try:
            self.write_file.close()
        except OSError:
            pass
