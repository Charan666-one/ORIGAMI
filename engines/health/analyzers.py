"""Analyzers — the actual checks the Project Health Engine runs.

Every analyzer is a pure function over the repo (AST + filesystem). None of them
import or execute project code, so analysis can never disturb a running ORIGAMI.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from engines.health.report import Capability, Finding

# ORIGAMI's layers, inner-most first. A layer may import itself and anything
# ABOVE it in this list (dependencies point inward, toward abstractions).
LAYERS = ["core", "engines", "skills", "adapters", "interfaces", "agents", "storage"]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist",
             "platforms", "assets", "docs", "docker", ".github", ".vscode"}
LARGE_FILE_LINES = 400
LARGE_FUNC_LINES = 80
TODO = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)


# --------------------------------------------------------------------- helpers

def python_files(root: Path, sub: str = "") -> List[Path]:
    base = root / sub if sub else root
    if not base.exists():
        return []
    return [p for p in base.rglob("*.py")
            if not any(part in SKIP_DIRS for part in p.parts)]


def _parse(path: Path):
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="ignore")), None
    except SyntaxError as exc:
        return None, f"{exc.msg} line {exc.lineno}"
    except Exception as exc:  # unreadable file
        return None, str(exc)


def _imports(tree: ast.AST) -> List[Tuple[str, bool]]:
    """(module, is_type_checking_guarded) for every internal-looking import."""
    guarded: Set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = ast.dump(node.test)
            if "TYPE_CHECKING" in test:
                for child in ast.walk(node):
                    guarded.add(id(child))
    out = []
    for node in ast.walk(tree):
        mod = None
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mod = node.module
        elif isinstance(node, ast.Import):
            mod = node.names[0].name if node.names else None
        if mod:
            out.append((mod, id(node) in guarded))
    return out


def _layer_of(module: str) -> str:
    return module.split(".", 1)[0]


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------- architecture

def analyze_architecture(root: Path) -> List[Finding]:
    """The core law: adding a capability must never require editing core/.

    Verifies core/ holds no concrete skill/provider imports, dependency direction
    is inward, and there are no circular imports between internal modules.
    """
    findings: List[Finding] = []

    # 1. core must not import concrete capabilities (TYPE_CHECKING hints are fine)
    for path in python_files(root, "core"):
        tree, err = _parse(path)
        if tree is None:
            continue
        for mod, guarded in _imports(tree):
            layer = _layer_of(mod)
            if guarded:
                continue
            if layer == "skills" or mod.startswith("engines.reasoning.providers"):
                findings.append(Finding(
                    "architecture", "critical",
                    f"core imports a concrete capability: {mod}",
                    _rel(root, path),
                    "Inject it instead (duck-typed parameter + TYPE_CHECKING hint) so "
                    "adding a capability never edits core/."))
            elif layer in ("interfaces", "agents"):
                findings.append(Finding(
                    "architecture", "critical",
                    f"core imports an outer layer: {mod}", _rel(root, path),
                    "Dependencies must point inward; invert this."))

    # 2. adapters/engines must not depend on skills or interfaces
    for sub in ("adapters", "engines"):
        for path in python_files(root, sub):
            tree, err = _parse(path)
            if tree is None:
                continue
            for mod, guarded in _imports(tree):
                if guarded:
                    continue
                if _layer_of(mod) in ("skills", "interfaces"):
                    findings.append(Finding(
                        "architecture", "warning",
                        f"{sub} depends on {_layer_of(mod)}: {mod}", _rel(root, path),
                        f"Keep {sub}/ independent of outer layers."))

    # 3. circular imports between internal modules
    for cycle in _find_cycles(_module_graph(root)):
        findings.append(Finding(
            "architecture", "critical",
            "circular import: " + " → ".join(cycle), "",
            "Break the cycle by extracting the shared piece or injecting it."))

    return findings


def _module_graph(root: Path) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = {}
    internal = set(LAYERS)
    for layer in LAYERS:
        for path in python_files(root, layer):
            tree, _ = _parse(path)
            if tree is None:
                continue
            name = _rel(root, path).replace("/", ".").removesuffix(".py").removesuffix(".__init__")
            deps = {mod for mod, guarded in _imports(tree)
                    if not guarded and _layer_of(mod) in internal}
            graph[name] = deps
    return graph


def _find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Detect cycles at module-prefix level (cheap DFS; reports the first few)."""
    cycles, seen = [], set()

    def visit(node: str, stack: List[str]) -> None:
        if len(cycles) >= 3:
            return
        for dep in graph.get(node, ()):  # dep is a module path like "core.planner"
            target = dep if dep in graph else None
            if target is None:
                continue
            if target in stack:
                cycle = stack[stack.index(target):] + [target]
                key = tuple(sorted(cycle))
                if key not in seen:
                    seen.add(key)
                    cycles.append(cycle)
                continue
            visit(target, stack + [target])

    for node in list(graph):
        visit(node, [node])
    return cycles


# ------------------------------------------------------------------- structure

#: importing any of these from the repo root would shadow the standard library
STDLIB_NAMES = {"platform", "types", "json", "time", "select", "signal", "socket",
                "string", "queue", "copy", "io", "abc", "code", "email", "logging",
                "math", "random", "secrets", "shutil", "test", "typing", "uuid"}


def analyze_structure(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    empty_pkgs: List[str] = []

    # Top-level packages/modules that shadow the stdlib break third-party imports
    # (e.g. onnxruntime calling platform.system()) whenever cwd is the repo root.
    for entry in root.iterdir():
        name = entry.name[:-3] if entry.suffix == ".py" else entry.name
        if name in STDLIB_NAMES and (entry.is_dir() and (entry / "__init__.py").exists()
                                     or entry.suffix == ".py"):
            findings.append(Finding(
                "structure", "critical",
                f"'{name}' shadows the Python standard library", _rel(root, entry),
                f"Rename {name}/ (e.g. {name}s/) — while it exists, any dependency "
                f"doing `import {name}` gets this package instead and breaks."))

    for layer in LAYERS:
        for path in python_files(root, layer):
            rel = _rel(root, path)
            text = path.read_text(encoding="utf-8", errors="ignore")
            lines = text.count("\n") + 1

            tree, err = _parse(path)
            if tree is None:
                findings.append(Finding("structure", "critical",
                                        f"file does not parse: {err}", rel,
                                        "Fix the syntax error — it breaks imports."))
                continue

            if lines > LARGE_FILE_LINES:
                findings.append(Finding("structure", "warning",
                                        f"large file ({lines} lines)", rel,
                                        f"Split {rel} into focused modules (>{LARGE_FILE_LINES} lines)."))

            if path.name != "__init__.py" and not text.strip():
                empty_pkgs.append(rel)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    span = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno
                    if span > LARGE_FUNC_LINES:
                        findings.append(Finding(
                            "structure", "warning",
                            f"long function '{node.name}' ({span} lines)", rel,
                            f"Extract helpers from {node.name}()."))

    if empty_pkgs:
        findings.append(Finding(
            "structure", "info",
            f"{len(empty_pkgs)} empty placeholder file(s)", ", ".join(empty_pkgs[:4]),
            "Delete unused placeholders — empty files are the debt this project "
            "already learned about (231 empty files)."))
    return findings


# --------------------------------------------------------------------- quality

def analyze_quality(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    todos: List[str] = []

    for layer in LAYERS:
        for path in python_files(root, layer):
            for i, line in enumerate(path.read_text(encoding="utf-8",
                                                    errors="ignore").splitlines(), 1):
                if TODO.search(line):
                    todos.append(f"{_rel(root, path)}:{i}")

    if todos:
        findings.append(Finding("quality", "info", f"{len(todos)} TODO/FIXME marker(s)",
                                ", ".join(todos[:3]),
                                "Convert TODOs into tracked issues or resolve them."))

    tests = python_files(root, "tests")
    if not tests:
        findings.append(Finding("quality", "critical", "no tests found", "tests/",
                                "Every capability needs a keyless test."))
    return findings


# ------------------------------------------------------------------------ docs

def analyze_docs(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    undocumented: List[str] = []

    for layer in LAYERS:
        for path in python_files(root, layer):
            if path.name == "__init__.py":
                continue
            tree, _ = _parse(path)
            if tree is None:
                continue
            if not ast.get_docstring(tree):
                undocumented.append(_rel(root, path))

    if undocumented:
        sev = "warning" if len(undocumented) > 3 else "info"
        findings.append(Finding("docs", sev,
                                f"{len(undocumented)} module(s) without a docstring",
                                ", ".join(undocumented[:4]),
                                "Add a one-paragraph module docstring: purpose + usage."))
    for doc in ("README.md", "docs/PURPOSE.md", "docs/CHECKPOINTS.md", "docs/JOURNAL.md"):
        if not (root / doc).exists():
            findings.append(Finding("docs", "warning", f"missing {doc}", doc,
                                    f"Restore {doc} — it anchors the project."))
    return findings


# ---------------------------------------------------------------- capabilities

def analyze_capabilities(root: Path) -> Tuple[List[Capability], List[Finding]]:
    """Per-skill health cards + findings. Skills are ORIGAMI's capabilities."""
    caps: List[Capability] = []
    findings: List[Finding] = []

    main_text = (root / "main.py").read_text(encoding="utf-8", errors="ignore") \
        if (root / "main.py").exists() else ""
    tests_text = "\n".join(p.read_text(encoding="utf-8", errors="ignore")
                           for p in python_files(root, "tests"))

    skills_dir = root / "skills"
    if not skills_dir.exists():
        return caps, findings

    for pkg in sorted(p for p in skills_dir.iterdir() if p.is_dir()
                      and p.name not in SKIP_DIRS):
        skill_file = pkg / "skill.py"
        if not skill_file.exists():
            continue
        tree, err = _parse(skill_file)
        text = skill_file.read_text(encoding="utf-8", errors="ignore")

        # An empty/stub folder is dormant scaffold, not a broken capability.
        if not text.strip() or (tree is not None and not any(
                isinstance(n, ast.ClassDef) for n in ast.walk(tree))):
            findings.append(Finding(
                "structure", "info", f"'{pkg.name}' is an empty capability placeholder",
                _rel(root, skill_file),
                f"Delete skills/{pkg.name}/ until it's built (empty scaffold is debt)."))
            continue

        cap = Capability(name=pkg.name, lines=text.count("\n") + 1)

        if tree is not None:
            cap.documented = bool(ast.get_docstring(tree))
            cap.tools = text.count("ToolSpec(")
            methods = {n.name for node in ast.walk(tree)
                       if isinstance(node, ast.ClassDef)
                       for n in node.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            cap.contract_ok = {"specs", "execute"} <= methods

        cap.registered = f"skills.{pkg.name}.skill" in main_text
        cap.tested = pkg.name in tests_text

        if not cap.contract_ok:
            cap.warnings.append("does not implement the Skill contract (specs + execute)")
            findings.append(Finding("integration", "critical",
                                    f"capability '{pkg.name}' breaks the Skill contract",
                                    _rel(root, skill_file),
                                    f"Implement specs() and execute() in {pkg.name} so the "
                                    "registry can plug it in."))
        if not cap.registered:
            cap.warnings.append("not registered in the composition root")
            findings.append(Finding("integration", "warning",
                                    f"capability '{pkg.name}' is not registered",
                                    "main.py",
                                    f"Register {pkg.name} in main.py or remove the folder."))
        if not cap.tested:
            cap.warnings.append("no test references it")
            findings.append(Finding("quality", "warning",
                                    f"capability '{pkg.name}' has no test",
                                    _rel(root, skill_file),
                                    f"Add a keyless test for {pkg.name}."))
        if not cap.documented:
            cap.warnings.append("no module docstring")
        if cap.lines > 300:
            cap.warnings.append(f"large ({cap.lines} lines)")
            findings.append(Finding("structure", "warning",
                                    f"capability '{pkg.name}' is large ({cap.lines} lines)",
                                    _rel(root, skill_file),
                                    f"Split {pkg.name} into sub-modules."))
        caps.append(cap)

    return caps, findings


# --------------------------------------------------------------- dependencies

def analyze_dependencies(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return [Finding("dependencies", "warning", "no pyproject.toml", "",
                        "Declare dependencies so installs are reproducible.")]

    declared = set(re.findall(r'"([A-Za-z0-9_.-]+)(?:[<>=\[].*?)?"',
                              pyproject.read_text(encoding="utf-8", errors="ignore")))
    declared = {d.lower().replace("-", "_") for d in declared}

    used: Set[str] = set()
    stdlib_ish = {"os", "sys", "re", "json", "time", "pathlib", "typing", "dataclasses",
                  "abc", "enum", "asyncio", "subprocess", "urllib", "uuid", "datetime",
                  "collections", "itertools", "shlex", "logging", "ast", "html", "base64",
                  "hashlib", "secrets", "shutil", "math", "random", "functools", "contextlib",
                  "__future__", "ctypes", "tempfile", "threading", "platform", "socket",
                  "io", "csv", "sqlite3", "textwrap", "traceback", "warnings", "glob",
                  "string", "copy", "signal", "queue", "unittest", "importlib", "inspect"}
    internal = set(LAYERS) | {"main", "tests"}
    # Third-party used only by dormant/optional code paths (Windows adapter, Google
    # calendar OAuth, robot heritage). These are lazily imported by design.
    optional_ok = {"google", "google_auth_oauthlib", "googleapiclient", "jwt", "pyautogui",
                   "win32api", "win32clipboard", "win32con", "win32gui", "win32process",
                   "win10toast", "websockets", "playwright", "psutil", "pytest", "cv2",
                   "numpy", "serial"}
    for layer in LAYERS:
        for path in python_files(root, layer):
            tree, _ = _parse(path)
            if tree is None:
                continue
            for mod, _guarded in _imports(tree):
                top = _layer_of(mod).lower()
                if top not in stdlib_ish and top not in internal:
                    used.add(top.replace("-", "_"))

    missing = {u for u in used if u not in declared and u not in optional_ok}
    # dotenv->python-dotenv style aliases are common; only report clear gaps
    aliases = {"dotenv": "python_dotenv", "yaml": "pyyaml", "jwt": "pyjwt",
               "sklearn": "scikit_learn"}
    missing = {m for m in missing if aliases.get(m, m) not in declared}
    if missing:
        findings.append(Finding("dependencies", "warning",
                                f"imported but not declared: {', '.join(sorted(missing))}", "",
                                "Add them to pyproject.toml (or make the import lazy/optional)."))
    return findings


# --------------------------------------------------------- integration readiness

INTEGRATION_TARGETS = [
    ("a new capability (e.g. Resume Optimizer)", "skills"),
    ("CodeLens / an external service", "skills"),
    ("a Study Engine", "engines"),
    ("a Vision Engine", "engines"),
    ("Robotics (Stage 5)", "platforms"),
    ("an external plugin (no core edit)", "skills"),
]


def analyze_integration(root: Path, arch_findings: List[Finding]) -> List[Finding]:
    """Can future work plug in WITHOUT touching core? That is ORIGAMI's promise."""
    findings: List[Finding] = []

    core_clean = not any(f.category == "architecture" and f.severity == "critical"
                         for f in arch_findings)
    registry = root / "skills" / "registry.py"
    base = root / "skills" / "base.py"
    brain = root / "engines" / "reasoning" / "llm.py"
    events = root / "core" / "events.py"

    if not registry.exists():
        findings.append(Finding("integration", "critical", "no capability registry",
                                "skills/registry.py",
                                "The registry is the plug-in seam — restore it."))
    if not base.exists():
        findings.append(Finding("integration", "critical", "no Skill contract",
                                "skills/base.py", "Restore the Skill ABC."))
    if not brain.exists():
        findings.append(Finding("integration", "warning", "no Brain interface",
                                "engines/reasoning/llm.py",
                                "Keep models behind one interface so they stay swappable."))
    if not events.exists():
        findings.append(Finding("integration", "warning", "no event bus",
                                "core/events.py",
                                "Events are the seam for proactive//distributed work."))
    if not core_clean:
        findings.append(Finding("integration", "critical",
                                "core is coupled to a concrete capability", "core/",
                                "Decouple core before adding more capabilities."))
    return findings


def integration_matrix(root: Path, ok: bool) -> List[Tuple[str, bool, str]]:
    """Simulated answers to 'can X be plugged in without redesign?'"""
    rows = []
    for label, layer in INTEGRATION_TARGETS:
        exists = (root / layer).exists()
        rows.append((label, ok and exists,
                     "registry + Skill contract" if layer == "skills"
                     else "engine slot present" if exists else f"{layer}/ missing"))
    return rows


# ------------------------------------------------------------------ scalability

def analyze_scalability(root: Path, n_caps: int) -> Tuple[List[Finding], List[str]]:
    """Project behaviour at 10 / 50 / 100 capabilities and large stores."""
    findings: List[Finding] = []
    notes: List[str] = []

    planner = root / "engines" / "reasoning" / "llm.py"
    text = planner.read_text(encoding="utf-8", errors="ignore") if planner.exists() else ""
    keyword_routing = "keyword_match_plan" in text

    notes.append(f"{n_caps} capabilities today — registry lookup is O(1) by name.")
    if keyword_routing:
        notes.append("Routing scans keywords linearly: fine to ~50 capabilities; "
                     "collisions (not speed) bite first.")
        if n_caps >= 15:
            findings.append(Finding(
                "scalability", "warning",
                f"keyword routing with {n_caps} capabilities is collision-prone", "",
                "Plan an intent classifier (or per-skill namespaces) before ~50 "
                "capabilities; keep the routing-regression tests growing."))

    for store, label in ((Path.home() / ".origami" / "memory.json", "memory"),
                         (Path.home() / ".origami" / "codebases.json", "codebases")):
        if store.exists() and store.stat().st_size > 2_000_000:
            findings.append(Finding("scalability", "warning",
                                    f"{label} store is {store.stat().st_size//1_000_000}MB", str(store),
                                    f"Move {label} to SQLite/vectors — JSON is loaded wholly in RAM."))
    notes.append("JSON stores load fully into RAM: fine to ~10k records, then move to "
                 "SQLite + embeddings (the interface already allows swapping).")
    return findings, notes
