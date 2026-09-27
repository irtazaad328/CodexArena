"""
CodexArena Challenge 3 — Self-Transfer Zero-Sum Glitch
=====================================================
Vulnerability: from_account == to_account is not prohibited.
Adversary: Transfers funds to oneself, bypassing transaction fees or triggering balance duplication bugs.

Run to test vulnerability:
    python challenge_3_self_transfer.py
"""

import sqlite3

def get_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE accounts (id INT PRIMARY KEY, name TEXT, balance REAL)")
    conn.execute("CREATE TABLE audit_log (tx_id INTEGER PRIMARY KEY AUTOINCREMENT, acc_id INT, delta REAL)")
    conn.execute("INSERT INTO accounts VALUES (1, 'User', 1000.0)")
    conn.commit()
    return conn

# ── VULNERABLE FUNCTION (To be patched by IBM Bob / Blue Agent) ───────────────
def process_transfer(conn: sqlite3.Connection, from_id: int, to_id: int, amount: float) -> bool:
    """
    [VULNERABLE]: Does not check if from_id == to_id.
    """
    cur = conn.cursor()
    cur.execute("SELECT balance FROM accounts WHERE id = ?", (from_id,))
    row = cur.fetchone()
    if not row or row[0] < amount:
        return False

    cur.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
    cur.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
    cur.execute("INSERT INTO audit_log (acc_id, delta) VALUES (?, ?)", (from_id, -amount))
    cur.execute("INSERT INTO audit_log (acc_id, delta) VALUES (?, ?)", (to_id, amount))
    conn.commit()
    return True

# ── TEST HARNESS ─────────────────────────────────────────────────────────────
def run_test():
    print("=" * 60)
    print("  CodexArena Challenge 3: Self-Transfer Invariant Test")
    print("=" * 60)
    conn = get_db()
    print("[*] Firing 10 self-transfers (from_id=1 to to_id=1, $100 each)...")

    accepted = 0
    for _ in range(10):
        if process_transfer(conn, 1, 1, 100.0):
            accepted += 1

    print(f"[*] Self-transfers accepted: {accepted}/10")
    if accepted > 0:
        print("\n[EXPLOITED] System allowed meaningless self-transfers.")
        print("   Status: VULNERABLE (Needs from_id != to_id guard)")
        return False
    else:
        print("\n[RESILIENT] IMMUNE! Self-transfers strictly rejected.")
        print("   Status: RESILIENT (Patch verified)")
        return True

if __name__ == "__main__":
    run_test()
