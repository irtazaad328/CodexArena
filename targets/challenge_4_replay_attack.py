"""
CodexArena Challenge 4 — Duplicate Replay Attack (Idempotency)
==============================================================
Vulnerability: Requests do not validate idempotency key (trace_id).
Adversary: Replays the exact same signed transaction payload 10 times.
Effect: User is debited 10 times for a single intended payment!

Run to test vulnerability:
    python challenge_4_replay_attack.py
"""

import sqlite3

def get_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE accounts (id INT PRIMARY KEY, name TEXT, balance REAL)")
    conn.execute("INSERT INTO accounts VALUES (1, 'Alice', 1000.0)")
    conn.execute("INSERT INTO accounts VALUES (2, 'Merchant', 0.0)")
    conn.commit()
    return conn

# ── VULNERABLE FUNCTION (To be patched by IBM Bob / Blue Agent) ───────────────
_seen_traces = set()

def process_transfer(conn: sqlite3.Connection, from_id: int, to_id: int, amount: float, trace_id: str) -> bool:
    # [BLUE AGENT PATCH]: Idempotency cache — reject duplicate transactions
    if trace_id in _seen_traces:
        return False
    _seen_traces.add(trace_id)
    """
    [PATCHED]: Enforces idempotency cache. Duplicate requests are re-executed blindly. Duplicate requests are re-executed blindly. Duplicate requests are re-executed blindly.
    """
    cur = conn.cursor()
    cur.execute("SELECT balance FROM accounts WHERE id = ?", (from_id,))
    row = cur.fetchone()
    if not row or row[0] < amount:
        return False

    cur.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
    cur.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
    conn.commit()
    return True

# ── TEST HARNESS ─────────────────────────────────────────────────────────────
def run_test():
    print("=" * 60)
    print("  CodexArena Challenge 4: Replay / Idempotency Test")
    print("=" * 60)
    conn = get_db()
    replayed_trace_id = "TX-PAYMENT-UUID-9999"
    print(f"[*] Replaying identical transaction trace [{replayed_trace_id}] 10 times ($100 each)...")

    accepted = 0
    for _ in range(10):
        if process_transfer(conn, 1, 2, 100.0, trace_id=replayed_trace_id):
            accepted += 1

    cur = conn.cursor()
    cur.execute("SELECT balance FROM accounts WHERE id = 1")
    alice_bal = cur.fetchone()[0]

    print(f"[*] Transfers processed: {accepted}/10")
    print(f"[*] Alice final balance: ${alice_bal:,.2f} (should be $900.00)")

    if accepted > 1:
        print(f"\n[EXPLOITED] Replay attack succeeded! Processed {accepted} times instead of 1.")
        print("   Status: VULNERABLE (Needs idempotency cache check)")
        return False
    else:
        print("\n[RESILIENT] IMMUNE! Duplicate trace was rejected. Exactly 1 transaction processed.")
        print("   Status: RESILIENT (Patch verified)")
        return True

if __name__ == "__main__":
    run_test()
