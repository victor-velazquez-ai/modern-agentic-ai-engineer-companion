"""Resources exposed over MCP — read-only, addressable context.

Where a *tool* is a verb the model can invoke (and may have side effects), a **resource** is a
noun the model can *read*: a document, a config blob, a row of reference data, addressed by a
URI. MCP resources are deliberately read-only — exposing them never lets a client mutate state.

A :class:`Resource` here is content held in memory and addressed by a ``uri`` (e.g.
``mem://readme``). A real server would back these with files, a database, or an API; the
``read()`` seam is identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Resource:
    """A single read-only resource addressed by ``uri``."""

    uri: str
    name: str
    description: str
    mime_type: str
    text: str

    def describe(self) -> dict[str, Any]:
        """The discovery payload a client sees from ``resources/list``."""
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }

    def read(self) -> dict[str, Any]:
        """The payload returned by ``resources/read`` — MCP's ``contents`` shape."""
        return {
            "contents": [
                {
                    "uri": self.uri,
                    "mimeType": self.mime_type,
                    "text": self.text,
                }
            ]
        }


def build_default_resources() -> list[Resource]:
    """The example resources the default server exposes."""
    return [
        Resource(
            uri="mem://readme",
            name="readme",
            description="A short note describing this demo MCP server.",
            mime_type="text/markdown",
            text=(
                "# Demo MCP Server\n\n"
                "Exposes the `add`, `echo`, and `now` tools and this resource. "
                "Runs in-process with no network and no keys.\n"
            ),
        ),
        Resource(
            uri="mem://limits",
            name="limits",
            description="Operational limits a client should respect.",
            mime_type="application/json",
            text='{"max_echo_chars": 280, "tools": ["add", "echo", "now"]}',
        ),
    ]
