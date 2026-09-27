# ⚔️ CodexArena — IBM Bob 2.0 Session Summary
## Official Hackathon Submission Artifact

> **Project:** CodexArena — Autonomous Adversarial Chaos & Self-Healing Engine  
> **Model / Assistant:** IBM Bob 2.0 (Powered by IBM Granite & FastMCP)  
> **Hackathon Track:** Grand Prize / Autonomous DevSecOps & Self-Healing Microservices  
> **Live HUD:** `http://localhost:8000`  
> **Target Microservice:** `http://localhost:9000`  

---

## 📸 Cyber War-Room HUD Overview

![CodexArena War-Room HUD](docs/screenshots/war_room_certified.png)

*Figure 1: CodexArena Cyber War-Room HUD at `http://localhost:8000` showing 100% certified resilience, live 4-layer hot-patch diff, IBM Granite 3.0 incident synthesis, and tamper-proof cryptographic certificate.*

---

## 1. Executive Summary

In mission-critical financial ledgers and microservices, **concurrency race conditions (TOCTOU)** and **balance invariant violations** cause catastrophic, irreversible losses (ghost overdrafts, infinite money glitch, replay attacks). Traditional unit tests and static linters (flake8, pylint) fail completely because these bugs only manifest under multi-threaded runtime burst contention.

**CodexArena** solves this by establishing an autonomous adversarial loop:
1. **Adversarial Red Agent:** Fires high-velocity concurrent HTTP bursts (TOCTOU read/write race, negative balance drains, duplicate transaction replays, and self-transfers).
2. **Autonomous Blue Agent:** Captures live crash telemetry, diagnoses root causes via **IBM Granite 3.0**, synthesizes permanent source code patches directly to disk, and re-executes tests to verify immunity.
3. **Dynamic Target Scanning (`targets/`):** Judges and developers can drop ANY custom Python script into `targets/` — CodexArena dynamically detects, probes, exploits, patches on disk, and certifies it.
4. **Cryptographic Resilience Certificate:** Issues a tamper-proof SHA-256 signed audit certificate printable as PDF or exportable as raw JSON.

---

## 2. IBM Bob Session Transcript & Tool Interaction

The entire end-to-end battle can be driven either via the **1-Click Cyber War-Room HUD** (`localhost:8000`) or autonomously through **IBM Bob** using the official FastMCP tool suite (`.bob/mcp.json`):

### Phase 1: Launch Adversarial Assault
* **Bob Prompt:**  
  `"You are the CodexArena battle commander. Launch an adversarial race-condition assault on our banking ledger API at http://localhost:9000."`
* **MCP Tool Called:**  
  `launch_arena_battle(service_path="http://localhost:9000", attack_type="4vector")`
* **Result:**  
  Battle UUID `6d72fc59...` initialized. Red Agent dispatches 50 concurrent requests.
  - Treasury Balance: $50,000.00
  - Completed: 50/50 requests slipped past stale balance check!
  - Final Treasury Balance: -$450,000.00 (Ghost Overdraft confirmed).
  - Resilience Gauge: **0%** | Status: **CRASHED**.

---

### Phase 2: Telemetry Capture & IBM Granite 3.0 Diagnosis
* **Bob Prompt:**  
  `"Read the crash telemetry for battle 6d72fc59..."`
* **MCP Tool Called:**  
  `get_crash_telemetry(battle_id="6d72fc59...")`
* **IBM Granite 3.0 Synthesis:**  
  Model: `ibm/granite-3-8b-instruct v3.0`  
  - **Telemetry Diagnosis:** Critical TOCTOU race vulnerability detected in ledger balance check-and-update sequence. Non-atomic asyncio execution window allowed simultaneous withdrawal requests to bypass balance guards, generating ghost overdraft.
  - **Prescribed Remediation:** Synthesised atomic conditional UPDATE query (`WHERE balance >= amount`) enforcing SQLite row-level transaction isolation, eliminating read/write split. Deployed in-memory idempotency cache keyed on `trace_id` with O(1) lookup.

---

### Phase 3: Autonomous Disk-Patching (Blue Agent)
* **Bob Prompt:**  
  `"Trigger the Blue Agent autonomous patch pipeline to heal the vulnerabilities."`
* **MCP Tool Called:**  
  `apply_hot_patch(file_path="targets/", patch_diff="")`
* **Code Modification:**  
  Blue Agent synthesizes the fix and **writes it directly to disk** on the target files:
  ```diff
  @@ TOCTOU Concurrency Race @@
  -    cur.execute("SELECT balance FROM accounts WHERE id = ?", (from_id,))
  -    await asyncio.sleep(0.001)   # race window
  -    if balance < amount: return False
  +    # Single atomic conditional UPDATE eliminates TOCTOU window
  +    cur.execute("UPDATE accounts SET balance = balance - ? WHERE id = ? AND balance >= ?", (amount, from_id, amount))
  +    if cur.rowcount == 0: return False
  ```
  Status: **HEALED** | Status Diff populated in War-Room HUD.

---

### Phase 4: Verification & Cryptographic Certification
* **Bob Prompt:**  
  `"Re-attack the service to verify resilience and export the certificate."`
* **MCP Tool Called:**  
  `verify_resilience(battle_id="6d72fc59...")`  
  `export_resilience_certificate(battle_id="6d72fc59...")`
* **Outcome:**  
  - 50 repeat concurrent requests fired.
  - Exactly 5 legit transfers approved ($50,000.00 exhausted), 45 ghost overdrafts rejected.
  - Final Balance: $0.00 (Zero data corruption, zero drift).
  - Resilience Score: **100% IMMUNE** | Status: **CERTIFIED**.
  - All 4 Vector cards turn **GREEN (NEUTRALISED)**.
  - Golden Certificate unlocked with SHA-256 digest: `c2e17b4d...`.

---

## 3. Verified Attack Vectors

| # | Attack Vector | Adversarial Technique | Autonomous Defense | Verification Status |
|---|---|---|---|---|
| **V1** | **TOCTOU Race Condition** | 50 concurrent async coroutines reading stale balance | Atomic conditional `UPDATE ... WHERE balance >= ?` | ✅ **100% IMMUNE** |
| **V2** | **Duplicate Replay Attack** | Replaying identical transaction trace 10 times | Deduplication cache keyed on `trace_id` (O(1)) | ✅ **100% IMMUNE** |
| **V3** | **Self-Transfer Invariant** | Account sending funds to itself (`from_id == to_id`) | Pre-DB invariant check (`from_id != to_id`) | ✅ **100% IMMUNE** |
| **V4** | **Negative Drain Invariant** | Negative transfer (`amount < 0`) stealing funds from victim | Strict invariant boundary (`amount <= 0` rejected) | ✅ **100% IMMUNE** |

---

## 4. Key Highlights for Hackathon Judges

1. **Not a Mock:** Real SQLite in-memory DB, real FastAPI microservice, real HTTP sockets over `httpx`, and real concurrent async coroutines.
2. **Permanent Source Code Repair:** Blue Agent doesn't just toggle a memory variable — it actively writes patches into Python source files on disk.
3. **Pluggable Test Directory (`targets/`):** Anyone can test their own microservice code by simply dropping files into `codexarena/targets/`.
4. **IBM Ecosystem Native:** Deep integration with IBM Bob via FastMCP tools and IBM Granite 3.0 instruct models.
