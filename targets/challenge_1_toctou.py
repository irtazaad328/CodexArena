"""
CodexArena Challenge 1 — Concurrency Race Condition (TOCTOU)
============================================================
Vulnerability: Time-of-Check / Time-of-Use race window between balance read and write.
Target: Account #4 (Treasury) with $50,000 balance.
Adversary: Fires 50 simultaneous transfers of $10,000 each.

Run to test vulnerability:
    python challenge_1_toctou.py
"""

import asyncio
import sqlite3

INITIAL_TREASURY_BALANCE = 50_000.0
TRANSFER_AMOUNT = 10_000.0
CONCURRENT_REQUESTS = 50

def get_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE accounts (id INT PRIMARY KEY, name TEXT, balance REAL)")
    conn.execute("INSERT INTO accounts VALUES (4, 'Treasury', ?)", (INITIAL_TREASURY_BALANCE,))
    conn.execute("INSERT INTO accounts VALUES (1, 'Alice', 0.0)")
    conn.commit()
    return conn

# ── VULNERABLE FUNCTION (To be patched by IBM Bob / Blue Agent) ───────────────
async def process_transfer(conn: sqlite3.Connection, from_id: int, to_id: int, amount: float) -> bool:
    """
    [VULNERABLE]: Reads balance, yields to event loop (asyncio.sleep), then updates.
    Multiple concurrent coroutines see the same stale balance!
    """
    cur = conn.cursor()
    # [BLUE AGENT PATCH]: Single atomic conditional UPDATE eliminates TOCTOU window
    cur.execute("UPDATE accounts SET balance = balance - ? WHERE id = ? AND balance >= ?", (amount, from_id, amount))
    if cur.rowcount == 0:
        return False
    cur.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
    conn.commit()
    return True

# ── TEST HARNESS (Verifies if file is vulnerable or healed) ────────────────────
async def run_test():
    print("=" * 60)
    print("  CodexArena Challenge 1: TOCTOU Race Condition Test")
    print("=" * 60)
    conn = get_db()
    print(f"[*] Initial Treasury Balance: ${INITIAL_TREASURY_BALANCE:,.2f}")
    print(f"[*] Firing {CONCURRENT_REQUESTS} simultaneous transfers of ${TRANSFER_AMOUNT:,.2f}...")

    tasks = [process_transfer(conn, 4, 1, TRANSFER_AMOUNT) for _ in range(CONCURRENT_REQUESTS)]
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r)
    cur = conn.cursor()
    cur.execute("SELECT balance FROM accounts WHERE id = 4")
    final_balance = cur.fetchone()[0]

    print(f"[*] Completed: {success_count}/{CONCURRENT_REQUESTS} transfers approved.")
    print(f"[*] Final Treasury Balance: ${final_balance:,.2f}")

    if final_balance < 0:
        print("\n[EXPLOITED] Treasury overdraft detected!")
        print(f"   Ghost transfers allowed: {success_count - int(INITIAL_TREASURY_BALANCE / TRANSFER_AMOUNT)}")
        print("   Status: VULNERABLE (Needs atomic conditional patch)")
        return False
    else:
        print("\n[RESILIENT] IMMUNE! No overdraft occurred.")
        print(f"   Max legit transfers allowed: {int(INITIAL_TREASURY_BALANCE / TRANSFER_AMOUNT)}")
        print("   Status: RESILIENT (Patch verified)")
        return True

if __name__ == "__main__":
    asyncio.run(run_test())
