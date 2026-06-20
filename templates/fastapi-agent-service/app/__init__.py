"""FastAPI agent service — copyable template.

This package is the API shell that sits in front of *your* agent. The transport
layer (`api/`) talks to an orchestration layer (`services/`) that, in turn, calls
the agent you build (the part the book teaches). `core/` holds settings, DI
providers, and the auth stub.

Copy this folder into your project, fill every ``TODO`` / ``▢`` marker, and wire
your agent in ``services/agent_service.py``. There is no business logic here.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
