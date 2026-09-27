"""
Ledger database layer.

UNSAFE path (LEDGER_SAFE_MODE=0):
  - transfer_funds_unsafe: TOCTOU race, no idempotency check, self-transfers allowed.

SAFE path (LEDGER_SAFE_MODE=1) — defends all 4 attack vectors:
  V1 TOCTOU          Atomic conditional UPDATE — no read/write split.
  V2 Replay          In-memory idempotency cache: trace_id seen → reject duplicate.
  V3 Self-transfer   Explicit from_id != to_id guard before any DB work.
  V4 Burst           Inherits from V1 atomicity; no extra code needed.

The .env file in this directory is read on every request (no restart required).
"""

import asyncio
from pathlib import Path

import aiosqlite

DB_PATH = str(Path(__file__).parent / "ledger.db")

# ── Idempotency cache (V2 defence) ────────────────────────────────────────────
# Maps trace_id -> True.  In-memory only; cleared on reset. Good enough for demo.
_seen_trace_ids: set[str] = set()


def clear_idempotency_cache() -> None:
    _seen_trace_ids.clear()


async def _open() -> aiosqlite.Connection:
    """Open a fresh per-request connection with proper busy timeout."""
    conn = await aiosqlite.connect(DB_PATH, timeout=30.0)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=30000")
    await conn.execute("PRAGMA synchronous=NORMAL")
    return conn


async def init_db() -> None:
    """Create and seed the database. Also clears the idempotency cache."""
    clear_idempotency_cache()
    conn = await _open()
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id      INTEGER PRIMARY KEY,
            name    TEXT    NOT NULL,
            balance REAL    NOT NULL DEFAULT 0.0
        )
        """
    )
    await conn.execute("DELETE FROM accounts")
    await conn.executemany(
        "INSERT INTO accounts (id, name, balance) VALUES (?, ?, ?)",
        [
            (1, "Alice",    10_000.0),
            (2, "Bob",       5_000.0),
            (3, "Charlie",   8_000.0),
            (4, "Treasury", 50_000.0),
        ],
    )
    await conn.commit()
    await conn.close()


async def get_accounts() -> list[dict]:
    conn = await _open()
    async with conn.execute("SELECT id, name, balance FROM accounts ORDER BY id") as cur:
        rows = await cur.fetchall()
    await conn.close()
    return [{"id": r[0], "name": r[1], "balance": r[2]} for r in rows]


# ── UNSAFE (all 4 vectors exploitable) ────────────────────────────────────────

async def transfer_funds_unsafe(
    from_id: int, to_id: int, amount: float, trace_id: str | None = None
) -> dict:
    """
    VULNERABLE path — exposes all 4 attack vectors:

    V1 TOCTOU:         asyncio.sleep(0) between READ and WRITE creates race window.
    V2 Replay:         trace_id is ignored — identical transactions are re-processed.
    V3 Self-transfer:  No from_id != to_id check — self-transfer allowed.
    V4 Burst:          No rate limiting; event loop can be saturated.
    """
    conn = await _open()
    try:
        # V1 — READ (race window opens)
        async with conn.execute(
            "SELECT balance FROM accounts WHERE id = ?", (from_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return {"ok": False, "error": f"Account {from_id} not found"}

        balance = row[0]

        # ← YIELD: other coroutines read the same stale balance ←
        await asyncio.sleep(0)

        if balance < amount:
            return {"ok": False, "error": "Insufficient funds", "balance": balance}

        # V1 — WRITE (overdraft possible)
        await conn.execute(
            "UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id)
        )
        await conn.execute(
            "UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id)
        )
        await conn.commit()
        return {"ok": True, "transferred": amount}
    finally:
        await conn.close()


# ── SAFE (all 4 vectors defended) ─────────────────────────────────────────────

async def transfer_funds_safe(
    from_id: int, to_id: int, amount: float, trace_id: str | None = None
) -> dict:
    """
    PATCHED path — defends all 4 attack vectors:

    V1 TOCTOU:        Single atomic UPDATE with WHERE balance >= amount.
    V2 Replay:        trace_id checked against in-memory cache; duplicates rejected.
    V3 Self-transfer: from_id != to_id enforced before any DB work.
    V4 Burst:         Inherits atomicity of V1; no extra overhead.
    """
    # V3 — Self-transfer guard
    if from_id == to_id:
        return {"ok": False, "error": "Self-transfers are not permitted"}

    # V2 — Idempotency check
    if trace_id:
        if trace_id in _seen_trace_ids:
            return {"ok": False, "error": f"Duplicate transaction trace_id={trace_id!r} rejected"}
        _seen_trace_ids.add(trace_id)

    # V1 — Atomic check-and-debit (no race window)
    conn = await _open()
    try:
        result = await conn.execute(
            """
            UPDATE accounts
               SET balance = balance - ?
             WHERE id = ?
               AND balance >= ?
            """,
            (amount, from_id, amount),
        )
        if result.rowcount == 0:
            async with conn.execute(
                "SELECT balance FROM accounts WHERE id = ?", (from_id,)
            ) as cur:
                row = await cur.fetchone()
            balance = row[0] if row else None
            return {
                "ok": False,
                "error": "Insufficient funds or account not found",
                "balance": balance,
            }
        await conn.execute(
            "UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id)
        )
        await conn.commit()
        return {"ok": True, "transferred": amount}
    finally:
        await conn.close()
