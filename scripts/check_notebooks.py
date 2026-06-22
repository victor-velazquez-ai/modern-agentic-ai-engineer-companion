#!/usr/bin/env python
"""Fast static gate for the companion notebooks (no execution, no installs).

For every notebook it checks: valid JSON, and every code cell compiles as
Python (top-level ``await`` allowed, IPython line/cell magics skipped). Exits
non-zero on the first structural problem. Cheap enough to run on every push
before the heavier execution job.

    python scripts/check_notebooks.py            # all of learn/
    python scripts/check_notebooks.py learn
"""
from __future__ import annotations
import ast, json, sys, pathlib

FLAG = ast.PyCF_ALLOW_TOP_LEVEL_AWAIT


def main() -> int:
    roots = sys.argv[1:] or ["learn"]
    nbs: list[pathlib.Path] = []
    for a in roots:
        p = pathlib.Path(a)
        nbs += sorted(p.rglob("*.ipynb")) if p.is_dir() else [p]
    nbs = [n for n in nbs if ".ipynb_checkpoints" not in str(n)]

    cells = 0
    bad: list[tuple[str, int, str]] = []
    for nb in nbs:
        try:
            data = json.loads(nb.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            bad.append((str(nb), -1, f"JSON: {e}"))
            continue
        for i, cell in enumerate(data.get("cells", [])):
            if cell.get("cell_type") != "code":
                continue
            src = "".join(cell.get("source", []))
            lines = src.splitlines()
            first = next((l for l in lines if l.strip()), "")
            if first.lstrip().startswith("%%"):  # cell magic => not Python
                continue
            code = "\n".join(l for l in lines if not l.lstrip().startswith(("!", "%", "?")))
            cells += 1
            try:
                compile(code, f"{nb.name}:cell{i}", "exec", flags=FLAG)
            except SyntaxError as e:
                bad.append((str(nb), i, f"{e.msg} (L{e.lineno})"))

    print(f"notebooks: {len(nbs)}   code cells: {cells}   syntax errors: {len(bad)}")
    for f, i, m in bad:
        print(f"  {f}  cell {i}  ->  {m}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
