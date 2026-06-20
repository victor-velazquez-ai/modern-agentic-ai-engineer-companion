import json, sys
path = sys.argv[1]
nb = json.load(open(path, encoding="utf-8"))
src = []
for c in nb["cells"]:
    if c["cell_type"] == "code":
        s = "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
        # skip the empty exercise cells (just a comment)
        src.append(s)
glob = {}
code = "\n\n".join(src)
exec(compile(code, path, "exec"), glob)
print("=== RAN CLEAN:", path)
