"""Build the tiny mock warehouse (``data/warehouse.sqlite``) the demo and evals query.

A text-to-SQL copilot needs a database to talk to. This script deterministically (re)builds a
*small, read-only-shaped* SQLite warehouse whose schema matches ``semantic/metrics.yaml`` exactly:
two tables — ``customers`` (one row per account, with region + plan) and ``orders`` (one row per
order, with status + amount) — joined on ``customer_id``. The numbers are hand-picked and fixed
(no randomness) so every question in the golden set has one *known* answer; an eval set is only
trustworthy if the warehouse it runs against is reproducible.

Run it once before the demo::

    python data/build_warehouse.py

It is idempotent: it drops and recreates the tables, so re-running gives byte-identical data.
The committed ``warehouse.sqlite`` is the output of this script; deleting it and re-running this
file regenerates the same warehouse (Golden rule #4 — assets are generated from source).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "warehouse.sqlite"

# --- fixed seed data (deterministic; every golden answer is computed from THIS) --------------
# customer_id, name, region, plan, signup_date
CUSTOMERS: tuple[tuple[int, str, str, str, str], ...] = (
    (1, "Acme Corp", "AMER", "enterprise", "2023-11-04"),
    (2, "Beacon Labs", "AMER", "pro", "2024-01-15"),
    (3, "Cobalt GmbH", "EMEA", "enterprise", "2024-01-22"),
    (4, "Delta SARL", "EMEA", "free", "2024-02-09"),
    (5, "Eos KK", "APAC", "pro", "2024-02-18"),
    (6, "Fjord AS", "EMEA", "pro", "2024-03-03"),
    (7, "Ginkgo Pte", "APAC", "free", "2024-03-27"),
    (8, "Helio Inc", "AMER", "enterprise", "2024-04-11"),
)

# order_id, customer_id, order_date, amount_usd, status
# Revenue counts ONLY status='completed' (refunds are excluded — see metrics.yaml).
ORDERS: tuple[tuple[int, int, str, float, str], ...] = (
    (101, 1, "2024-01-05", 1200.0, "completed"),
    (102, 1, "2024-02-12", 800.0, "completed"),
    (103, 2, "2024-02-20", 300.0, "completed"),
    (104, 3, "2024-02-28", 1500.0, "completed"),
    (105, 3, "2024-03-04", 250.0, "refunded"),   # refunded -> excluded from revenue
    (106, 4, "2024-03-09", 90.0, "completed"),
    (107, 5, "2024-03-15", 600.0, "completed"),
    (108, 5, "2024-03-22", 600.0, "refunded"),   # refunded -> excluded from revenue
    (109, 6, "2024-03-25", 450.0, "completed"),
    (110, 8, "2024-04-02", 2000.0, "completed"),
    (111, 8, "2024-04-18", 1000.0, "completed"),
    (112, 2, "2024-04-20", 300.0, "completed"),
)

_SCHEMA = """
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    region       TEXT    NOT NULL,
    plan         TEXT    NOT NULL,
    signup_date  TEXT    NOT NULL
);

CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date   TEXT    NOT NULL,
    amount_usd   REAL    NOT NULL,
    status       TEXT    NOT NULL
);
"""


def build(db_path: str | Path = DB_PATH) -> Path:
    """(Re)create the warehouse at ``db_path`` and return its path."""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    try:
        conn.executescript(_SCHEMA)
        conn.executemany(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?)", CUSTOMERS
        )
        conn.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?)", ORDERS
        )
        conn.commit()
    finally:
        conn.close()
    return p


def main() -> None:
    p = build()
    print(f"built mock warehouse: {p}")
    print(f"  customers: {len(CUSTOMERS)} rows")
    print(f"  orders   : {len(ORDERS)} rows "
          f"({sum(1 for o in ORDERS if o[4] == 'completed')} completed, "
          f"{sum(1 for o in ORDERS if o[4] == 'refunded')} refunded)")


if __name__ == "__main__":
    main()
