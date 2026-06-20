"""Shared helpers to emit valid nbformat-4 notebooks with cleared outputs.

Build artifact for chapter 14. Cell-source strings use the sentinel `Q3`
(a module constant) wherever a Python triple-quote (\"\"\") is needed, so the
generator source itself never has to nest triple-quotes. `_lines` expands the
sentinel and splits the text the way Jupyter stores `source`.

May be deleted after the notebooks are generated.
"""
import json

Q3 = '"' '"' '"'  # the sentinel callers spell as the name `Q3` in f-strings


def _lines(text: str):
    """Split into Jupyter `source` form: each line (but the last) ends in \\n."""
    text = text.strip("\n")
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]] if parts else [""]


def md(text: str):
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def code(text: str):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _lines(text),
    }


def write_nb(path: str, cells: list):
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return path
