#!/usr/bin/env python
"""Execute every companion notebook in MOCK mode and report pass/fail.

Runs each notebook top-to-bottom in a fresh kernel, from the notebook's own
directory (so relative ``data/`` paths resolve), with ``COMPANION_MOCK=1`` so
nothing hits a real API. Exits non-zero if any notebook fails — used as the
CI gate (see .github/workflows/notebooks.yml) and runnable locally:

    python scripts/verify_notebooks.py            # all of learn/
    python scripts/verify_notebooks.py learn/part-04-building-blocks-of-agents
    python scripts/verify_notebooks.py path/to/one.ipynb

Env:
    COMPANION_MOCK   forced to "1" here (cost-free, deterministic).
    COMPANION_KERNEL kernel name to launch (default "python3").
"""
from __future__ import annotations
import os, sys, pathlib, collections

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

os.environ["COMPANION_MOCK"] = "1"
KERNEL = os.environ.get("COMPANION_KERNEL", "python3")

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError


def collect(args: list[str]) -> list[pathlib.Path]:
    roots = args or ["learn"]
    nbs: list[pathlib.Path] = []
    for a in roots:
        p = pathlib.Path(a)
        if p.is_dir():
            nbs += sorted(p.rglob("*.ipynb"))
        elif p.suffix == ".ipynb":
            nbs.append(p)
    return [n for n in nbs if ".ipynb_checkpoints" not in str(n)]


def main() -> int:
    nbs = collect(sys.argv[1:])
    if not nbs:
        print("no notebooks found", flush=True)
        return 0
    passed = 0
    failed: list[tuple[str, str]] = []
    for nb_path in nbs:
        nb = nbformat.read(nb_path, as_version=4)
        client = NotebookClient(
            nb, timeout=240, kernel_name=KERNEL,
            resources={"metadata": {"path": str(nb_path.parent)}},
            allow_errors=False,
        )
        name = str(nb_path)
        try:
            client.execute()
            passed += 1
            print("PASS  " + name, flush=True)
        except CellExecutionError as e:
            err = ""
            for line in reversed(str(e).splitlines()):
                s = line.strip()
                if s and ("Error" in s or "Exception" in s):
                    err = s
                    break
            failed.append((name, err[:220]))
            print("FAIL  " + name + "  ::  " + err[:160], flush=True)
        except Exception as e:  # noqa: BLE001 -- report, never abort the sweep
            failed.append((name, f"{type(e).__name__}: {e}"[:220]))
            print("ERR   " + name + "  ::  " + (f"{type(e).__name__}: {e}")[:160], flush=True)

    print("\n==== SUMMARY ====", flush=True)
    print(f"PASS {passed} / {len(nbs)}   FAIL {len(failed)}", flush=True)
    if failed:
        buckets = collections.Counter(err.split(":")[0][:48] for _, err in failed)
        print("\nfailure types:", flush=True)
        for k, v in buckets.most_common():
            print(f"  {v:3}  {k}", flush=True)
        print("\nfailures:", flush=True)
        for name, err in failed:
            print(f"  {name}\n      {err}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
