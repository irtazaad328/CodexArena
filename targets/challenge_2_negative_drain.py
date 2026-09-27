"""
CodexArena Challenge 2 — Negative Amount Invariant Drain
========================================================
Vulnerability: Lack of validation that transfer amount must be strictly positive (amount > 0).
Adversary: Sends a negative transfer (e.g. -$10,000) from Attacker to Victim.
Effect: Attacker balance increases (+10k) while Victim balance drops (-10k)!

Run to test vulnerability:
    python challenge_2_negative_drain.py
"""

import sqlite3

def get_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE accounts (id INT PRIMARY KEY, name TEXT, balance REAL)")
    conn.execute("INSERT INTO accounts VALUES (1, 'Alice (Victim)', 10000.0)")
    conn.execute("INSERT INTO accounts VALUES (2, 'Attacker', 0.0)")
    conn.commit()
    return conn

# ── VULNERABLE FUNCTION (To be patched by IBM Bob / Blue Agent) ───────────────
def process_transfer(conn: sqlite3.Connection, from_id: int, to_id: int, amount: float) -> bool:
    # [BLUE AGENT PATCH]: Invariant guard — reject negative and zero transfers
    if amount <= 0:
        return False
    """
    [PATCHED]: Validates amount > 0.
    amount = -10,000 causes:
       from_balance - (-10000) => +10,000 (Victim gets drained!)
       to_balance + (-10000)   => -10,000
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
    print("  CodexArena Challenge 2: Negative Invariant Drain Test")
    print("=" * 60)
    conn = get_db()
    print("[*] Initial Balances: Alice (Victim) = $10,000 | Attacker = $0")
    print("[*] Firing exploit: Attacker transfers -$5,000 to Alice...")

    success = process_transfer(conn, 2, 1, -5000.0)

    cur = conn.cursor()
    cur.execute("SELECT name, balance FROM accounts")
    balances = {name: bal for name, bal in cur.fetchall()}

    print(f"[*] Attacker balance: ${balances['Attacker']:,.2f}")
    print(f"[*] Alice balance: ${balances['Alice (Victim)']:,.2f}")

    if balances['Attacker'] > 0:
        print("\n[EXPLOITED] Attacker generated free money via negative drain!")
        print("   Status: VULNERABLE (Needs amount > 0 invariant check)")
        return False
    else:
        print("\n[RESILIENT] IMMUNE! Negative transfer was rejected.")
        print("   Status: RESILIENT (Patch verified)")
        return True

if __name__ == "__main__":
    run_test()
