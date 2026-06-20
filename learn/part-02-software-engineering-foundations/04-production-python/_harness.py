import json, sys, io, contextlib, traceback
def run(path):
    nb = json.load(open(path, encoding="utf-8"))
    g = {"__name__":"__main__"}
    for i, c in enumerate(nb["cells"]):
        if c["cell_type"] != "code":
            continue
        src = "".join(c["source"])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(src, f"{path}:cell{i}", "exec"), g)
        except Exception:
            print(f"FAIL {path} nb-cell {i}")
            traceback.print_exc()
            print("----\n"+src)
            return False
    print(f"CLEAN: {path}")
    return True
if __name__ == "__main__":
    ok = run(sys.argv[1])
    sys.exit(0 if ok else 1)
