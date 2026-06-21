import json, sys, io
from contextlib import redirect_stdout

def run_nb(path):
    nb = json.load(open(path, encoding="utf-8"))
    g = {"__name__": "__main__"}
    buf = io.StringIO()
    n_code = 0
    for i, c in enumerate(nb["cells"]):
        if c["cell_type"] != "code":
            continue
        src = "".join(c["source"])
        if src.strip() == "" or src.strip().startswith("# Exercise"):
            continue  # skip empty exercise placeholders
        n_code += 1
        try:
            with redirect_stdout(buf):
                exec(compile(src, f"{path}:cell{i}", "exec"), g)
        except Exception as e:
            print(f"FAIL {path} cell#{i}: {type(e).__name__}: {e}")
            print("----- offending cell -----")
            print(src)
            return False
    print(f"PASS run: {path}  ({n_code} code cells executed, MOCK=1)")
    return True

import os
os.environ["COMPANION_MOCK"] = "1"
ok = True
for p in sys.argv[1:]:
    ok = run_nb(p) and ok
sys.exit(0 if ok else 1)
