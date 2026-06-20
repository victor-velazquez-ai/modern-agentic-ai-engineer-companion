"""CLI entrypoint: load .env, run the agent on a prompt, print the answer.

Run it (after ``make install``):

    uv run agent "What is 21 + 21?"
    # or, equivalently:
    python -m app.main "What is 21 + 21?"

With ``COMPANION_MOCK=1`` (the default) this prints a canned reply and spends nothing.
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from app.agent import run
from app.config import get_settings


def main(argv: list[str] | None = None) -> int:
    """Parse args, run the agent, print the result. Returns a process exit code."""
    # Load .env into the environment before settings are read.
    load_dotenv()

    argv = sys.argv[1:] if argv is None else argv
    prompt = " ".join(argv).strip() or "Say hello in one short sentence."

    try:
        settings = get_settings()  # validates config; fails fast with a readable error
        answer = run(prompt, settings=settings)
    except RuntimeError as exc:  # e.g. missing key on the live path
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
