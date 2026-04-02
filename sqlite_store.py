from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd

from config import SETTINGS


SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_state (
  source TEXT PRIMARY KEY,
  last_mtime REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
  time TEXT,
  symbol TEXT,
  action TEXT,
  price REAL,
  qty REAL,
  regime TEXT,
  prob_up REAL,
  imbalance REAL,
  profit_pct REAL
);

CREATE TABLE IF NOT EXISTS alerts (
  time TEXT,
  level TEXT,
  category TEXT,
  symbol TEXT,
  message TEXT,
  details TEXT
);

CREATE TABLE IF NOT EXISTS equity (
  time TEXT,
  equity_usdt REAL,
  daily_pnl_pct REAL,
  symbol TEXT,
  position_side TEXT,
  position_qty REAL,
  position_entry REAL
);

CREATE TABLE IF NOT EXISTS order_audit (
  time TEXT,
  symbol TEXT,
  action TEXT,
  order_id TEXT,
  status TEXT,
  requested_qty REAL,
  executed_qty REAL,
  filled_ratio REAL,
  fill_count REAL,
  avg_price REAL,
  slippage_bps REAL,
  estimated_fee_quote REAL,
  dry_run TEXT,
  details TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
  time TEXT,
  channel TEXT,
  level TEXT,
  category TEXT,
  title TEXT,
  message TEXT,
  delivered TEXT,
  details TEXT
);

CREATE TABLE IF NOT EXISTS shadow_trades (
  time TEXT,
  symbol TEXT,
  action TEXT,
  price REAL,
  qty REAL,
  profit_pct REAL,
  reason TEXT
);

CREATE TABLE IF NOT EXISTS websocket_ticks (
  symbol TEXT,
  event_time TEXT,
  price REAL,
  bid REAL,
  ask REAL,
  source TEXT
);
"""


def _csv_tables() -> dict[str, str]:
    return {
        SETTINGS.trade_log_path: "trades",
        SETTINGS.alerts_log_path: "alerts",
        SETTINGS.equity_log_path: "equity",
        SETTINGS.order_audit_log_path: "order_audit",
        SETTINGS.notification_log_path: "notifications",
        SETTINGS.shadow_trade_log_path: "shadow_trades",
    }


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(SETTINGS.sqlite_db_path), exist_ok=True)
    conn = sqlite3.connect(SETTINGS.sqlite_db_path)
    conn.executescript(SCHEMA)
    return conn


def _last_ingested_mtime(conn: sqlite3.Connection, source: str) -> float:
    row = conn.execute("SELECT last_mtime FROM ingestion_state WHERE source = ?", (source,)).fetchone()
    return float(row[0]) if row else 0.0


def _mark_ingested(conn: sqlite3.Connection, source: str, mtime: float) -> None:
    conn.execute(
        """
        INSERT INTO ingestion_state(source, last_mtime)
        VALUES(?, ?)
        ON CONFLICT(source) DO UPDATE SET last_mtime=excluded.last_mtime
        """,
        (source, mtime),
    )


def ingest_csv_file(path: str, table: str) -> int:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return 0
    conn = _connect()
    try:
        mtime = p.stat().st_mtime
        if _last_ingested_mtime(conn, str(p)) >= mtime:
            return 0
        df = pd.read_csv(p)
        if df.empty:
            _mark_ingested(conn, str(p), mtime)
            conn.commit()
            return 0
        df.to_sql(table, conn, if_exists="replace", index=False)
        _mark_ingested(conn, str(p), mtime)
        conn.commit()
        return len(df)
    finally:
        conn.close()


def sync_sqlite_store() -> dict[str, int]:
    results: dict[str, int] = {}
    for path, table in _csv_tables().items():
        results[table] = ingest_csv_file(path, table)
    ws_path = Path(SETTINGS.websocket_cache_path)
    if ws_path.exists() and ws_path.stat().st_size > 0:
        conn = _connect()
        try:
            mtime = ws_path.stat().st_mtime
            if _last_ingested_mtime(conn, str(ws_path)) < mtime:
                payload = json.loads(ws_path.read_text())
                rows = []
                for symbol, item in payload.items():
                    rows.append(
                        {
                            "symbol": symbol,
                            "event_time": item.get("event_time", ""),
                            "price": float(item.get("price", 0.0)),
                            "bid": float(item.get("bid", 0.0)),
                            "ask": float(item.get("ask", 0.0)),
                            "source": item.get("source", "websocket"),
                        }
                    )
                conn.execute("DELETE FROM websocket_ticks")
                if rows:
                    pd.DataFrame(rows).to_sql("websocket_ticks", conn, if_exists="append", index=False)
                _mark_ingested(conn, str(ws_path), mtime)
                conn.commit()
                results["websocket_ticks"] = len(rows)
            else:
                results["websocket_ticks"] = 0
        finally:
            conn.close()
    return results


def load_table(table: str) -> pd.DataFrame:
    conn = _connect()
    try:
        return pd.read_sql_query(f"SELECT * FROM {table}", conn)
    finally:
        conn.close()


if __name__ == "__main__":
    print(sync_sqlite_store())
