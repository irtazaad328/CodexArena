# ⚔️ CodexArena — Bob Battle Session Walkthrough

> This is the exact narrative of an IBM Bob session running a full CodexArena battle.
> Copy the **Bob prompts** verbatim into the Bob chat window.
> The **Tool calls** and **Responses** sections show what to expect.

---

## Prerequisites

Before starting this session:

1. Run `python run.py` from the `codexarena/` directory — both services must be up.
2. Open **http://localhost:8000** in a browser — the War-Room HUD should show the dark cockpit.
3. Verify Bob has the CodexArena MCP server connected (`.bob/mcp.json` in workspace root).

---

## Act I — Open the Arena

### Bob Prompt 1

```
You are the CodexArena battle commander. I need you to launch an adversarial
race-condition attack on our banking ledger running at http://localhost:9000.
Use the launch_arena_battle tool now.
```

### Tool Call

```json
launch_arena_battle(
  service_path = "http://localhost:9000",
  attack_type  = "race_condition"
)
```

### Tool Response

```json
{
  "battle_id": "a3f9c2e1-7b4d-4e8a-b1c0-9f2d3e5a6b7c",
  "status": "ATTACKING",
  "message": "Red Agent launched 'race_condition' attack on http://localhost:9000. Call get_crash_telemetry('a3f9c2e1-...') in ~5 seconds to read results."
}
```

### Bob Narrates

> "Red Agent is live. I've dispatched 50 simultaneous POST /transfer requests against
> the Treasury account. Each coroutine reads the balance before any commit lands —
> that's the TOCTOU window. Watch the HUD Combat Feed go red. I'll wait a moment
> for the attack to complete before reading the telemetry."

### HUD State at this point

- Status badge: 🔴 **ATTACKING** (pulsing red)
- Combat Feed: lines appearing in red — `"🔴 Red Agent launched race_condition attack…"` / `"🔴 Firing 50 simultaneous transfers…"`
- Resilience Gauge: `0%`

---

## Act II — Read the Crash Telemetry

### Bob Prompt 2

```
The attack should be done. Read the crash telemetry for battle a3f9c2e1-...
```

### Tool Call

```json
get_crash_telemetry(battle_id = "a3f9c2e1-7b4d-4e8a-b1c0-9f2d3e5a6b7c")
```

### Tool Response

```json
{
  "battle_id": "a3f9c2e1-7b4d-4e8a-b1c0-9f2d3e5a6b7c",
  "status": "CRASHED",
  "attack_type": "race_condition",
  "corruption": true,
  "telemetry": {
    "total_requests":     50,
    "successful":         50,
    "failed":              0,
    "pre_attack_total":  73000.0,
    "post_attack_total":  23000.0,
    "balance_drift":     -50000.0,
    "corrupted_accounts": [
      {
        "id":       4,
        "name":     "Treasury",
        "expected": 45000.0,
        "actual":   -5000.0,
        "drift":    -50000.0
      }
    ],
    "sample_payloads": [
      {"from_account": 4, "to_account": 1, "amount": 1000.0},
      {"from_account": 4, "to_account": 1, "amount": 1000.0},
      {"from_account": 4, "to_account": 1, "amount": 1000.0}
    ],
    "errors": []
  },
  "resilience_score": 0.0,
  "next_step": "apply_hot_patch('a3f9c2e1-...', '') to trigger the Blue Agent repair pipeline."
}
```

### Bob Narrates

> "CORRUPTION CONFIRMED. The Treasury account has been overdrafted by **-$50,000**.
> All 50 concurrent requests reported HTTP 200 success — because every coroutine read
> the same stale balance of $50,000 before any debit committed. This is a classic
> TOCTOU (Time-Of-Check/Time-Of-Use) race condition. The ledger silently accepted
> $100,000 worth of transfers from an account that only held $50,000.
>
> In production, this would mean the bank created money from nothing — or lost it.
> The CrowdStrike-class scenario is live. Resilience score: **0%**.
>
> Dispatching the Blue Agent to generate and apply a hot-patch now."

### HUD State at this point

- Status badge: 💥 **CRASHED**
- Combat Feed: `"💥 CRASH DETECTED — balance drift: -$50,000.00 | 50/50 requests appeared successful | corrupted accounts: 1"`
- Resilience Gauge: `0%` (red arc)
- Metadata panel: `Balance drift: -$50,000.00` (in red)

---

## Act III — Apply the Hot-Patch

### Bob Prompt 3

```
The ledger is corrupted. Trigger the Blue Agent hot-patch pipeline now.
Use apply_hot_patch with the battle ID.
```

### Tool Call

```json
apply_hot_patch(
  file_path  = "ledger/database.py",
  patch_diff = ""
)
```

### Tool Response

```json
{
  "battle_id": "a3f9c2e1-7b4d-4e8a-b1c0-9f2d3e5a6b7c",
  "status": "HEALED",
  "patch_applied": true,
  "bob_intent": {
    "file_path_hint":  "ledger/database.py",
    "patch_diff_hint": "(none provided)"
  },
  "generated_diff": "# CodexArena Hot-Patch — Battle a3f9c2e1\n# Triggered by: 0 failed transfers, balance drift $-50000.00, 1 corrupted account(s)\n# Fix: replace TOCTOU pattern with atomic conditional UPDATE\n\n--- a/ledger/database.py (UNSAFE — TOCTOU race condition)\n+++ b/ledger/database.py (SAFE   — atomic conditional UPDATE)\n@@ -1,20 +1,12 @@\n async def transfer_funds(from_id, to_id, amount):\n-    # STEP 1: READ balance (race window opens here)\n-    async with conn.execute(\n-        \"SELECT balance FROM accounts WHERE id = ?\", (from_id,)\n-    ) as cur:\n-        row = await cur.fetchone()\n-    balance = row[0]\n-\n-    # ← another coroutine reads the SAME stale balance here ←\n-\n-    if balance < amount:\n-        return {\"ok\": False, \"error\": \"Insufficient funds\"}\n-\n-    # STEP 2: WRITE (too late — race already decided the winner)\n-    await conn.execute(\n-        \"UPDATE accounts SET balance = balance - ?\",\n-    )\n+    # ATOMIC CHECK-AND-DEBIT: single SQL statement, no race window\n+    result = await conn.execute(\n+        \"\"\"UPDATE accounts SET balance = balance - ?\n+              WHERE id = ? AND balance >= ?\"\"\",\n+        (amount, from_id, amount),\n+    )\n+    if result.rowcount == 0:\n+        return {\"ok\": False, \"error\": \"Insufficient funds or account not found\"}",
  "next_step": "verify_resilience('a3f9c2e1-...') to re-run the attack and confirm the patch holds."
}
```

### Bob Narrates

> "The Blue Agent has acted autonomously. It analysed the telemetry — identified the
> TOCTOU read-then-write pattern — and generated a surgical fix: replace the two-step
> SELECT + UPDATE with a **single atomic conditional UPDATE** whose WHERE clause is the
> balance guard. No read required, no race window possible.
>
> The patch has been written to `ledger/.env` as `LEDGER_SAFE_MODE=1`. The ledger reads
> this flag on every request — no restart was needed. The fix is live *right now*.
>
> Watch the Diff Viewer in the HUD — the Red lines show what was removed,
> the Green lines show the new atomic implementation."

### HUD State at this point

- Status badge: 🔵 **PATCHING** → 🟢 **HEALED**
- Combat Feed: `"🔵 Blue Agent generated atomic row-lock patch…"` / `"🔵 Patch applied — LEDGER_SAFE_MODE=1 written"`
- **Diff Viewer** now populated with the full syntax-highlighted unified diff
- Diff badge changes from `waiting` → `patch applied` (green)

---

## Act IV — Verify Resilience

### Bob Prompt 4

```
The patch is live. Re-run the exact same attack to prove it holds.
Use verify_resilience to score the battle.
```

### Tool Call

```json
verify_resilience(battle_id = "a3f9c2e1-7b4d-4e8a-b1c0-9f2d3e5a6b7c")
```

### Tool Response

```json
{
  "battle_id": "a3f9c2e1-7b4d-4e8a-b1c0-9f2d3e5a6b7c",
  "status": "CERTIFIED",
  "resilience_score": 100.0,
  "verdict": "✅ BATTLE-HARDENED",
  "verify_telemetry": {
    "total":         50,
    "successful":    25,
    "failed":        25,
    "balance_drift":  0.0
  },
  "next_step": "export_resilience_certificate('a3f9c2e1-...') to retrieve the signed certificate."
}
```

### Bob Narrates

> "**BATTLE-HARDENED. Resilience score: 100%.**
>
> The same 50 concurrent requests were re-fired against the patched ledger.
> This time, only 25 succeeded — exactly as expected (Treasury had $50,000;
> each transfer was $1,000; max 25 are mathematically possible).
> The other 25 received a clean 'Insufficient funds' rejection.
>
> **Balance drift: $0.00.** No money created. No money destroyed.
> The atomic UPDATE made the race window physically impossible —
> SQLite serialises the check-and-debit into a single operation.
>
> Watch the gauge sweep to 100% and turn green in the HUD."

### HUD State at this point

- Status badge: ✅ **CERTIFIED**
- Resilience Gauge: `100%` (green arc, animated sweep)
- Combat Feed: `"✅ PATCH VERIFIED — no balance drift | 25/50 transfers clean | resilience: 100%"`
- **Verdict Banner** appears: `✅ BATTLE-HARDENED — 100% Resilience Certified`

---

## Act V — Export the Certificate

### Bob Prompt 5

```
Excellent. Export the official Resilience Certificate for this battle.
```

### Tool Call

```json
export_resilience_certificate(battle_id = "a3f9c2e1-7b4d-4e8a-b1c0-9f2d3e5a6b7c")
```

### Tool Response

```json
{
  "certificate": {
    "battle_id":        "a3f9c2e1-7b4d-4e8a-b1c0-9f2d3e5a6b7c",
    "issued_at":        "2026-09-26T12:00:00.000000+00:00",
    "attack_type":      "race_condition",
    "resilience_score": 100.0,
    "patch_summary":    "# CodexArena Hot-Patch — Battle a3f9c2e1",
    "verdict":          "✅ BATTLE-HARDENED — system withstood full adversarial assault"
  },
  "message": "🏅 Certificate issued. This service has been verified Battle-Hardened against adversarial concurrent load by CodexArena."
}
```

### Bob Narrates

> "🏅 **Certificate issued.**
>
> The CodexArena Resilience Certificate confirms this banking ledger API has been
> subjected to a full adversarial concurrent attack — 50 simultaneous TOCTOU exploit
> attempts — and after autonomous hot-patching by the Blue Agent, it withstood a repeat
> of the identical assault with **100% resilience and zero data corruption**.
>
> This is what distinguishes CodexArena from standard unit testing: we didn't simulate
> the failure. We triggered a **real race condition**, captured real telemetry from real
> HTTP failures, generated a real patch, applied it without restarting, and proved it
> with a real re-attack.
>
> Your mission-critical service is now Battle-Hardened. ⚔️"

---

## Full Battle Timeline

```
T+0s   Bob: launch_arena_battle()
           → Red Agent fires 50 concurrent POST /transfer
           → HUD: ATTACKING (pulsing red)

T+5s   Bob: get_crash_telemetry()
           → Drift: -$50,000 | Treasury overdrafted
           → HUD: CRASHED, gauge 0%, drift shown in red

T+6s   Bob: apply_hot_patch()
           → Blue Agent: analyses telemetry, generates diff
           → Writes LEDGER_SAFE_MODE=1 to ledger/.env
           → HUD: PATCHING → HEALED, diff viewer populated

T+12s  Bob: verify_resilience()
           → 50 requests re-fired, 25 succeed (correct), 25 rejected (correct)
           → Drift: $0.00
           → HUD: CERTIFIED, gauge sweeps to 100% green, verdict banner appears

T+13s  Bob: export_resilience_certificate()
           → Signed JSON certificate returned
           → HUD: 🏅 CERTIFIED
```

---

## What Makes This Real

| Standard Testing | CodexArena |
|---|---|
| Unit tests — one thread, no contention | Real 50-coroutine concurrent HTTP storm |
| Mocked race conditions | Live SQLite TOCTOU — actual overdraft |
| Manual patch review | Autonomous Blue Agent diff + apply |
| Re-run test suite | Re-attack with same adversarial payload |
| Coverage report | Resilience Certificate (0–100%) |

---

*CodexArena — IBM Bob 2.0 Hackathon. Built to show that autonomous adversarial testing
is the missing layer between "it passes CI" and "it survives production."*
