"""Create demo source + target SQLite databases with realistic, known defects.

Source defects (caught by row-level checks):
  duplicate order ids, missing customer ids, negative totals, invalid status,
  delivered orders with no ship date, ship-before-order dates, orphan customer
  references, a malformed email, a duplicated email.
Target (warehouse) defects (caught by reconciliation):
  dropped rows, an extra row, amount drift, a changed status.
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def build(n_customers=500, n_orders=3000, seed=11, clean=False):
    rng = np.random.default_rng(seed)
    cust = pd.DataFrame({
        "customer_id": [f"C{i:05d}" for i in range(1, n_customers + 1)],
        "email": [f"user{i}@example.test" for i in range(1, n_customers + 1)],
        "country": rng.choice(["US", "UK", "IN", "DE", "CA"], n_customers),
    })
    od = pd.Timestamp("2026-01-01") + pd.to_timedelta(rng.integers(0, 200, n_orders), unit="D")
    status = rng.choice(["pending", "shipped", "delivered", "cancelled"], n_orders, p=[.1, .2, .6, .1])
    ship = od + pd.to_timedelta(rng.integers(1, 6, n_orders), unit="D")
    ship = pd.Series(ship).where(np.isin(status, ["shipped", "delivered"]))
    orders = pd.DataFrame({
        "order_id": [f"O{i:06d}" for i in range(1, n_orders + 1)],
        "customer_id": rng.choice(cust.customer_id, n_orders),
        "order_date": od.strftime("%Y-%m-%d"),
        "shipped_date": ship.dt.strftime("%Y-%m-%d"),
        "order_total": rng.lognormal(4.3, .6, n_orders).round(2),
        "status": status,
    })
    if not clean:
        orders = pd.concat([orders, orders.sample(12, random_state=1)], ignore_index=True)    # dup order ids
        orders.loc[orders.sample(18, random_state=2).index, "customer_id"] = None             # missing FK
        orders.loc[orders.sample(9, random_state=3).index, "order_total"] *= -1               # negative totals
        orders.loc[orders.sample(7, random_state=4).index, "status"] = "returned"             # invalid status
        i = orders[orders.status == "delivered"].sample(11, random_state=5).index
        orders.loc[i, "shipped_date"] = None                                                  # delivered, no ship date
        j = orders[orders.shipped_date.notna()].sample(6, random_state=6).index
        orders.loc[j, "shipped_date"] = "2025-12-01"                                          # ship before order
        orders.loc[orders.sample(5, random_state=7).index, "customer_id"] = "C99999"          # orphan FK
        orders.loc[orders.sample(3, random_state=8).index, "order_total"] = 25000.0           # large (warn)
        cust.loc[3, "email"] = "not-an-email"
        cust.loc[10, "email"] = cust.loc[11, "email"]                                         # dup email
    # Warehouse = what the ETL loaded from source (deduplicated on key), then load drift is applied
    dw_orders = orders.drop_duplicates("order_id").copy()
    dw_cust = cust.copy()
    if not clean:
        dw_orders = dw_orders.drop(dw_orders.sample(15, random_state=9).index)                # dropped rows
        dw_orders.loc[dw_orders.sample(8, random_state=10).index, "order_total"] += 12.5      # amount drift
        dw_orders.loc[dw_orders.sample(4, random_state=11).index, "status"] = "cancelled"     # status drift
        dw_orders = pd.concat([dw_orders, pd.DataFrame([{"order_id": "O999999", "customer_id": "C00001",
            "order_date": "2026-03-01", "shipped_date": None, "order_total": 50.0, "status": "pending"}])],
            ignore_index=True)                                                                # extra row
        dw_cust = dw_cust.drop(dw_cust.sample(3, random_state=12).index)                      # dropped customers
    return orders, cust, dw_orders, dw_cust


def write(db_path: Path, tables: dict):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    for name, df in tables.items():
        df.to_sql(name, con, index=False)
    con.close()


def main(clean=False):
    orders, cust, dw_orders, dw_cust = build(clean=clean)
    write(ROOT / "demo" / "source.db", {"orders": orders, "customers": cust})
    write(ROOT / "demo" / "target.db", {"dw_orders": dw_orders, "dw_customers": dw_cust})
    print(f"source.db: orders={len(orders):,} customers={len(cust):,} | "
          f"target.db: dw_orders={len(dw_orders):,} dw_customers={len(dw_cust):,}")


if __name__ == "__main__":
    import sys
    main(clean="--clean" in sys.argv)
