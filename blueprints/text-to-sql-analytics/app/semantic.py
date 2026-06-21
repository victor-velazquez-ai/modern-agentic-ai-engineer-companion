"""Load the semantic layer (``semantic/metrics.yaml``) — the make-or-break asset.

The PLAN is blunt about it: *"Invest in ``semantic/metrics.yaml`` — the semantic layer is the
make-or-break, not the prompt."* This module turns that YAML contract into typed objects the rest
of the app grounds on:

* the **schema** (tables + columns + plain-English docs) that nl_to_sql validates against and the
  rag-pipeline indexes, and
* the **metrics / dimensions** (each pinned to one canonical SQL expression) so "revenue" resolves
  to the same refund-correct expression every time.

PyYAML is used when present; a tiny, dependency-free fallback parser handles *this* file's simple
shape otherwise, so the demo runs free and offline even without PyYAML installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

SEMANTIC_PATH = Path(__file__).resolve().parent.parent / "semantic" / "metrics.yaml"


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    description: str


@dataclass(frozen=True)
class Table:
    name: str
    grain: str
    description: str
    columns: tuple[Column, ...]

    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


@dataclass(frozen=True)
class Metric:
    name: str
    label: str
    description: str
    expression: str
    requires_tables: tuple[str, ...]
    synonyms: tuple[str, ...]


@dataclass(frozen=True)
class Dimension:
    name: str
    description: str
    synonyms: tuple[str, ...]
    column: str = ""
    expression: str = ""

    def sql(self) -> str:
        """The SQL fragment to group/slice by (a column reference or an expression)."""
        return self.expression or self.column


@dataclass(frozen=True)
class SemanticLayer:
    """The whole contract: schema + metrics + dimensions, ready to ground generation on."""

    dialect: str
    tables: tuple[Table, ...]
    metrics: tuple[Metric, ...]
    dimensions: tuple[Dimension, ...]

    # --- lookups the generator and retriever use --------------------------------
    def table(self, name: str) -> Table | None:
        return next((t for t in self.tables if t.name == name), None)

    def metric(self, name: str) -> Metric | None:
        return next((m for m in self.metrics if m.name == name), None)

    def dimension(self, name: str) -> Dimension | None:
        return next((d for d in self.dimensions if d.name == name), None)

    def known_tables(self) -> set[str]:
        return {t.name for t in self.tables}

    def known_columns(self) -> set[str]:
        """Every column as both ``col`` and ``table.col`` so schema checks accept either form."""
        cols: set[str] = set()
        for t in self.tables:
            for c in t.columns:
                cols.add(c.name)
                cols.add(f"{t.name}.{c.name}")
        return cols

    def schema_docs(self) -> list[tuple[str, str]]:
        """``(doc_id, text)`` rows describing each table/column/metric.

        These are exactly what the rag-pipeline ingests: one human-readable doc per schema
        element so a question's words retrieve the *right* tables, joins, and metrics.
        """
        docs: list[tuple[str, str]] = []
        for t in self.tables:
            cols = "; ".join(f"{c.name} ({c.type}): {c.description}" for c in t.columns)
            docs.append(
                (
                    f"table:{t.name}",
                    f"Table {t.name} — {t.grain}. {t.description} Columns: {cols}",
                )
            )
        for m in self.metrics:
            syn = ", ".join(m.synonyms)
            docs.append(
                (
                    f"metric:{m.name}",
                    f"Metric {m.label} ({m.name}) — {m.description} "
                    f"SQL: {m.expression}. Also called: {syn}.",
                )
            )
        for d in self.dimensions:
            syn = ", ".join(d.synonyms)
            docs.append(
                (
                    f"dimension:{d.name}",
                    f"Dimension {d.name} — group/slice by {d.sql()}. {d.description} "
                    f"Also called: {syn}.",
                )
            )
        return docs


# ---------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------
def _load_raw(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return _fallback_parse(text)


def load_semantic_layer(path: str | Path | None = None) -> SemanticLayer:
    """Read and validate the semantic layer from ``metrics.yaml``."""
    p = Path(path) if path is not None else SEMANTIC_PATH
    if not p.exists():
        raise FileNotFoundError(f"semantic layer not found: {p}")
    raw = _load_raw(p)

    tables: list[Table] = []
    for t in raw.get("tables", []) or []:
        cols = tuple(
            Column(
                name=str(c.get("name", "")),
                type=str(c.get("type", "")),
                description=str(c.get("description", "")).strip(),
            )
            for c in (t.get("columns", []) or [])
        )
        tables.append(
            Table(
                name=str(t.get("name", "")),
                grain=str(t.get("grain", "")).strip(),
                description=str(t.get("description", "")).strip(),
                columns=cols,
            )
        )

    metrics = tuple(
        Metric(
            name=str(m.get("name", "")),
            label=str(m.get("label", m.get("name", ""))),
            description=str(m.get("description", "")).strip(),
            expression=str(m.get("expression", "")).strip(),
            requires_tables=tuple(m.get("requires_tables", []) or []),
            synonyms=tuple(str(s) for s in (m.get("synonyms", []) or [])),
        )
        for m in (raw.get("metrics", []) or [])
    )

    dimensions = tuple(
        Dimension(
            name=str(d.get("name", "")),
            description=str(d.get("description", "")).strip(),
            synonyms=tuple(str(s) for s in (d.get("synonyms", []) or [])),
            column=str(d.get("column", "")).strip(),
            expression=str(d.get("expression", "")).strip(),
        )
        for d in (raw.get("dimensions", []) or [])
    )

    layer = SemanticLayer(
        dialect=str(raw.get("dialect", "sqlite")),
        tables=tuple(tables),
        metrics=metrics,
        dimensions=dimensions,
    )
    if not layer.tables:
        raise ValueError("semantic layer has no tables; cannot ground generation")
    if not layer.metrics:
        raise ValueError("semantic layer has no metrics; the metric registry is the point")
    return layer


# ---------------------------------------------------------------------------------
# Dependency-free fallback parser (only needs to handle THIS file's simple shape).
# ---------------------------------------------------------------------------------
def _fallback_parse(text: str) -> dict:
    """A minimal YAML-subset parser for ``metrics.yaml`` when PyYAML is unavailable.

    Supports exactly what this file uses: top-level ``key: value`` scalars, nested mappings,
    lists of mappings (``- key: value``), inline ``[a, b]`` lists, and folded ``>`` blocks.
    It is intentionally small — not a general YAML engine — so the demo never hard-depends on
    a third-party package. PyYAML is always preferred when installed.
    """
    root: dict = {}
    # Stack of (indent, container, container_kind) where kind is 'map' or 'list'.
    stack: list[tuple[int, object, str]] = [(-1, root, "map")]
    lines = text.splitlines()
    i = 0

    def parent_for(indent: int):
        while stack and stack[-1][0] >= indent:
            stack.pop()
        return stack[-1]

    while i < len(lines):
        raw = lines[i]
        i += 1
        stripped = raw.split("#", 1)[0].rstrip() if not _in_quotes(raw) else raw.rstrip()
        if not stripped.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        content = stripped.strip()

        is_item = content.startswith("- ")
        if content == "-":
            is_item = True
            content = ""
        elif is_item:
            content = content[2:].strip()

        _, container, kind = parent_for(indent if not is_item else indent + 1)

        if is_item:
            # A new list item. Ensure the nearest container is (or becomes) a list.
            list_parent = _ensure_list(stack, indent, root)
            if ":" in content and not content.startswith("["):
                item: dict = {}
                list_parent.append(item)
                stack.append((indent, item, "map"))
                key, val = _split_kv(content)
                val_obj, folded = _scalar_or_block(val, indent, lines, i)
                i = folded
                item[key] = val_obj
            else:
                list_parent.append(_coerce(content))
            continue

        # key: value at this indent inside the current map container.
        if ":" not in content:
            continue
        key, val = _split_kv(content)
        if not isinstance(container, dict):
            continue
        if val == "":
            # Could open a nested map or a list; decide by peeking the next non-blank line.
            nxt = _peek_indent(lines, i)
            if nxt is not None and nxt[1].lstrip().startswith("- "):
                new_list: list = []
                container[key] = new_list
                stack.append((indent, new_list, "list"))
            else:
                new_map: dict = {}
                container[key] = new_map
                stack.append((indent, new_map, "map"))
        else:
            val_obj, folded = _scalar_or_block(val, indent, lines, i)
            i = folded
            container[key] = val_obj

    return root


def _ensure_list(stack: list, indent: int, root: dict) -> list:
    """Return the list that items at ``indent`` belong to, creating none (parent made it)."""
    for ind, container, kind in reversed(stack):
        if kind == "list" and ind <= indent:
            return container  # type: ignore[return-value]
    # Fallback: a stray list with no parent key — attach under '_' (shouldn't happen here).
    lst: list = root.setdefault("_", [])  # type: ignore[assignment]
    return lst


def _split_kv(content: str) -> tuple[str, str]:
    key, _, val = content.partition(":")
    return key.strip().strip('"'), val.strip()


def _scalar_or_block(val: str, indent: int, lines: list[str], i: int) -> tuple[object, int]:
    """Parse a scalar, an inline list, or open a ``>`` folded block; return (value, new_i)."""
    if val == ">" or val == ">-" or val == "|":
        collected: list[str] = []
        while i < len(lines):
            nxt = lines[i]
            if nxt.strip() == "":
                i += 1
                continue
            nxt_indent = len(nxt) - len(nxt.lstrip(" "))
            if nxt_indent <= indent:
                break
            collected.append(nxt.strip())
            i += 1
        return " ".join(collected), i
    return _coerce(val), i


def _coerce(val: str) -> object:
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_coerce(p.strip()) for p in _split_inline(inner)]
    if len(val) >= 2 and val[0] in "'\"" and val[-1] == val[0]:
        return val[1:-1]
    return val


def _split_inline(inner: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quote = ""
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def _peek_indent(lines: list[str], i: int):
    while i < len(lines):
        line = lines[i]
        if line.split("#", 1)[0].strip():
            return (len(line) - len(line.lstrip(" ")), line)
        i += 1
    return None


def _in_quotes(line: str) -> bool:
    # Heuristic: don't strip '#' inside a quoted scalar. Our file has none, but be safe.
    return line.count("'") % 2 == 1 or line.count('"') % 2 == 1
