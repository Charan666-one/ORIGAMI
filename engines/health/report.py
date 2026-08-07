"""Health report data types — what the Project Health Engine produces.

The engine only ever OBSERVES, ANALYZES, REPORTS and RECOMMENDS. It never edits
code (ORIGAMI core rule): every output here is advisory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# severity -> score penalty applied to that category
PENALTY = {"critical": 25.0, "warning": 6.0, "info": 1.0}


@dataclass
class Finding:
    category: str          # architecture | structure | quality | docs | dependencies | integration
    severity: str          # critical | warning | info
    message: str
    where: str = ""        # file / module the finding refers to
    recommendation: str = ""

    def line(self) -> str:
        icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(self.severity, "•")
        loc = f" ({self.where})" if self.where else ""
        return f"{icon} {self.message}{loc}"


@dataclass
class Capability:
    """Per-capability health card (skills are ORIGAMI's capabilities)."""
    name: str
    tools: int = 0
    lines: int = 0
    documented: bool = False
    tested: bool = False
    registered: bool = False
    contract_ok: bool = False   # follows the Skill ABC (specs + execute)
    warnings: List[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        checks = [self.documented, self.tested, self.registered, self.contract_ok,
                  self.lines <= 300]
        return round(100.0 * sum(1 for c in checks if c) / len(checks), 1)

    def line(self) -> str:
        flags = "".join([
            "📄" if self.documented else "·",
            "🧪" if self.tested else "·",
            "🔌" if self.registered else "·",
            "📐" if self.contract_ok else "·",
        ])
        return f"{self.name:<12} {self.score:5.1f}%  {flags}  {self.tools} tools, {self.lines} lines"


@dataclass
class HealthReport:
    scores: Dict[str, float] = field(default_factory=dict)
    findings: List[Finding] = field(default_factory=list)
    capabilities: List[Capability] = field(default_factory=list)
    stats: Dict[str, object] = field(default_factory=dict)

    @property
    def overall(self) -> float:
        if not self.scores:
            return 0.0
        return round(sum(self.scores.values()) / len(self.scores), 1)

    def by_severity(self, severity: str) -> List[Finding]:
        return [f for f in self.findings if f.severity == severity]

    def recommendations(self) -> List[str]:
        seen, out = set(), []
        for f in self.findings:
            if f.recommendation and f.recommendation not in seen:
                seen.add(f.recommendation)
                out.append(f.recommendation)
        return out


def score_for(findings: List[Finding], category: str) -> float:
    """100 minus severity penalties for that category (floored at 0)."""
    penalty = sum(PENALTY.get(f.severity, 1.0) for f in findings if f.category == category)
    return round(max(0.0, 100.0 - penalty), 1)
