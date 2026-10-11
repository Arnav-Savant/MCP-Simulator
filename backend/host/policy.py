from dataclasses import dataclass

from scenarios.models import PolicyConfig


@dataclass
class Verdict:
    allowed: bool
    reason: str = ""


class Policy:
    def __init__(self, cfg: PolicyConfig | None = None):
        self.cfg = cfg or PolicyConfig()

    def check(self, tool: str, arguments: dict, catalog_names: set[str]) -> Verdict:
        if tool in self.cfg.denied_tools:
            return Verdict(False, f"tool '{tool}' is on the host deny list")
        if self.cfg.enforce_catalog and tool not in catalog_names:
            return Verdict(False, f"tool '{tool}' is not in the discovered catalog")
        limit = self.cfg.max_abs_number
        if limit is not None:
            for key, value in arguments.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool) and abs(value) > limit:
                    return Verdict(False, f"argument '{key}'={value} exceeds the host limit of {limit}")
        return Verdict(True)
