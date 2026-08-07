"""ProjectHealthEngine — keeps ORIGAMI architecturally clean for its whole life.

It treats ORIGAMI as a living system: it OBSERVES the repo, ANALYZES it, and
REPORTS with RECOMMENDATIONS. Per ORIGAMI's core rules it never modifies core,
memory, brain, planner, workflows or capabilities — analysis only.

    report = ProjectHealthEngine().run()
    print(report.overall, report.scores)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List, Optional, Tuple

from engines.health import analyzers as A
from engines.health.report import Capability, Finding, HealthReport, score_for

CATEGORIES = ["architecture", "structure", "quality", "docs", "dependencies",
              "integration", "scalability", "performance"]


def _is_source_repo(p: Path) -> bool:
    """The real source checkout — not an installed copy in site-packages."""
    return (p / "pyproject.toml").exists() and (p / "core").is_dir() and (p / "tests").is_dir()


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Locate the SOURCE repo to analyse.

    Order: $ORIGAMI_ROOT → cwd and its parents → this file's parents. The last is
    a fallback because an installed copy lives in site-packages (no tests/), and
    analysing that would report a hollow project.
    """
    env = os.getenv("ORIGAMI_ROOT")
    if env and _is_source_repo(Path(env)):
        return Path(env)

    if start is not None:
        here = Path(start).resolve()
        for parent in [here, *here.parents]:
            if _is_source_repo(parent):
                return parent

    for base in (Path.cwd(), Path(__file__).resolve()):
        for parent in [base, *base.parents]:
            if _is_source_repo(parent):
                return parent
    return Path.cwd()


class ProjectHealthEngine:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root else find_repo_root()
        self.analyzing_source = _is_source_repo(self.root)

    # ------------------------------------------------------------------ run

    def run(self) -> HealthReport:
        started = time.perf_counter()
        report = HealthReport()

        arch = A.analyze_architecture(self.root)
        structure = A.analyze_structure(self.root)
        quality = A.analyze_quality(self.root)
        docs = A.analyze_docs(self.root)
        deps = A.analyze_dependencies(self.root)
        caps, cap_findings = A.analyze_capabilities(self.root)
        integration = A.analyze_integration(self.root, arch)
        scal_findings, scal_notes = A.analyze_scalability(self.root, len(caps))
        perf_findings, perf_stats = self._performance()

        report.findings = (arch + structure + quality + docs + deps + cap_findings
                           + integration + scal_findings + perf_findings)
        report.capabilities = caps

        for category in CATEGORIES:
            report.scores[category] = score_for(report.findings, category)

        core_clean = not [f for f in arch if f.severity == "critical"]
        report.stats = {
            "capabilities": len(caps),
            "tools": sum(c.tools for c in caps),
            "python_files": len(A.python_files(self.root)),
            "test_files": len(A.python_files(self.root, "tests")),
            "scalability_notes": scal_notes,
            "integration_matrix": A.integration_matrix(self.root, core_clean),
            "analysis_seconds": round(time.perf_counter() - started, 2),
            **perf_stats,
        }
        return report

    # ---------------------------------------------------------- performance

    def _performance(self) -> Tuple[List[Finding], dict]:
        """Startup + resource snapshot. Cheap, best-effort, never fatal."""
        findings: List[Finding] = []
        stats: dict = {}

        try:
            import psutil  # optional
            proc = psutil.Process(os.getpid())
            stats["memory_mb"] = round(proc.memory_info().rss / 1_048_576, 1)
            vm = psutil.virtual_memory()
            stats["ram_free_gb"] = round(vm.available / 1_073_741_824, 2)
            if vm.available < 700_000_000:
                findings.append(Finding(
                    "performance", "warning",
                    f"low free RAM ({stats['ram_free_gb']}GB)", "",
                    "Close apps or use a smaller local model; the brain downgrades "
                    "to the fast tier under pressure."))
        except Exception:
            pass

        # disk footprint of the local stores
        data_dir = Path.home() / ".origami"
        if data_dir.exists():
            size = sum(p.stat().st_size for p in data_dir.glob("*") if p.is_file())
            stats["data_kb"] = round(size / 1024, 1)

        return findings, stats

    # -------------------------------------------------------------- render

    def render(self, report: HealthReport, detail: str = "summary") -> str:
        s = report.scores
        bar = lambda v: "█" * int(v // 10) + "░" * (10 - int(v // 10))  # noqa: E731
        lines = [
            f"🩺 ORIGAMI Project Health — {report.overall}%",
        ]
        if not self.analyzing_source:
            lines.append(f"   ⚠️  analysing {self.root} (not a source checkout — "
                         f"set ORIGAMI_ROOT for accurate results)")
        lines += [
            "",
            f"  Architecture   {bar(s['architecture'])} {s['architecture']:5.1f}%",
            f"  Integration    {bar(s['integration'])} {s['integration']:5.1f}%",
            f"  Structure      {bar(s['structure'])} {s['structure']:5.1f}%",
            f"  Quality        {bar(s['quality'])} {s['quality']:5.1f}%",
            f"  Documentation  {bar(s['docs'])} {s['docs']:5.1f}%",
            f"  Dependencies   {bar(s['dependencies'])} {s['dependencies']:5.1f}%",
            f"  Scalability    {bar(s['scalability'])} {s['scalability']:5.1f}%",
            f"  Performance    {bar(s['performance'])} {s['performance']:5.1f}%",
            "",
            f"  {report.stats.get('capabilities', 0)} capabilities · "
            f"{report.stats.get('tools', 0)} tools · "
            f"{report.stats.get('python_files', 0)} files · "
            f"{report.stats.get('test_files', 0)} test files "
            f"({report.stats.get('analysis_seconds', 0)}s)",
        ]

        criticals = report.by_severity("critical")
        warnings = report.by_severity("warning")
        if criticals:
            lines += ["", "🔴 Critical:"] + [f"   {f.line()}" for f in criticals[:6]]
        if warnings:
            lines += ["", f"🟡 Warnings ({len(warnings)}):"] + \
                     [f"   {f.line()}" for f in warnings[:6]]
        if not criticals and not warnings:
            lines += ["", "✅ No critical issues or warnings."]

        recs = report.recommendations()
        if recs:
            lines += ["", "💡 Recommendations:"] + [f"   {i}. {r}" for i, r in
                                                    enumerate(recs[:5], 1)]

        if detail == "full":
            lines += ["", "🔌 Integration readiness (can it plug in without core edits?):"]
            for label, ok, why in report.stats.get("integration_matrix", []):
                lines.append(f"   {'✅' if ok else '⚠️ '} {label} — {why}")
            lines += ["", "📈 Scalability:"] + \
                     [f"   • {n}" for n in report.stats.get("scalability_notes", [])]
            lines += ["", "🧩 Capabilities (📄docs 🧪tests 🔌registered 📐contract):"] + \
                     [f"   {c.line()}" for c in report.capabilities]
        return "\n".join(lines)

    def render_capabilities(self, report: HealthReport) -> str:
        rows = sorted(report.capabilities, key=lambda c: c.score)
        out = ["🧩 Capability health (📄docs 🧪tests 🔌registered 📐contract):"]
        out += [f"   {c.line()}" for c in rows]
        flagged = [c for c in rows if c.warnings]
        if flagged:
            out.append("")
            out.append("⚠️  Needs attention:")
            for c in flagged[:6]:
                out.append(f"   {c.name}: {'; '.join(c.warnings)}")
        return "\n".join(out)
