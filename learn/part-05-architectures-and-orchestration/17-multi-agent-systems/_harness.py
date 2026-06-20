import json, sys, os
os.environ.setdefault("COMPANION_MOCK", "1")  # force offline path

def run_nb(fn):
    nb = json.load(open(fn, encoding="utf-8"))
    # structural nbformat-4 checks
    assert nb.get("nbformat") == 4, "nbformat must be 4"
    assert "cells" in nb and "metadata" in nb, "missing top-level keys"
    for i, c in enumerate(nb["cells"]):
        assert c["cell_type"] in ("markdown", "code"), c["cell_type"]
        assert isinstance(c["source"], list), f"cell {i} source not a list"
        assert "metadata" in c, f"cell {i} missing metadata"
        if c["cell_type"] == "code":
            assert c["outputs"] == [], f"cell {i} outputs not empty"
            assert c["execution_count"] is None, f"cell {i} execution_count not null"
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    print(f"  structure OK: {len(nb['cells'])} cells, {len(code_cells)} code cells")
    # execute code cells in one shared namespace, top to bottom (skip pure-comment exercise stubs are fine)
    ns = {"__name__": "__main__"}
    for i, c in enumerate(code_cells):
        src = "".join(c["source"])
        try:
            exec(compile(src, f"{fn}#code{i}", "exec"), ns)
        except SystemExit as e:
            raise AssertionError(f"code cell {i} raised SystemExit: {e}")
        except Exception as e:
            print(f"  !! code cell {i} FAILED: {type(e).__name__}: {e}")
            print("---- cell source ----")
            print(src)
            raise
    print("  EXECUTED top-to-bottom with no errors (MOCK=1)")

for fn in sys.argv[1:]:
    print(f"== {fn} ==")
    run_nb(fn)
print("ALL OK")
