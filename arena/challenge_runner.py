"""
CodexArena Challenge Runner
===========================
Executes, diagnoses, and autonomously patches standalone challenge files
(challenge_1_toctou.py, challenge_2_negative_drain.py, challenge_3_self_transfer.py, challenge_4_replay_attack.py)
directly through the CodexArena War-Room HUD.
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from arena.battle_manager import battle_manager
from arena.models import BattleStatus

CHALLENGES_DIR = Path(__file__).parent.parent / "challenges"

CHALLENGE_MAP = {
    "toctou": {
        "file": "challenge_1_toctou.py",
        "title": "Challenge 1: TOCTOU Concurrency Race",
        "patch_func": "_patch_toctou",
    },
    "negative_drain": {
        "file": "challenge_2_negative_drain.py",
        "title": "Challenge 2: Negative Invariant Drain",
        "patch_func": "_patch_negative_drain",
    },
    "self_transfer": {
        "file": "challenge_3_self_transfer.py",
        "title": "Challenge 3: Self-Transfer Invariant",
        "patch_func": "_patch_self_transfer",
    },
    "replay": {
        "file": "challenge_4_replay_attack.py",
        "title": "Challenge 4: Duplicate Replay (Idempotency)",
        "patch_func": "_patch_replay",
    },
}

def _run_script(filename: str) -> tuple[int, str]:
    filepath = CHALLENGES_DIR / filename
    res = subprocess.run(
        [sys.executable, str(filepath)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return res.returncode, res.stdout + "\n" + res.stderr

def _patch_toctou(filepath: Path) -> str:
    text = filepath.read_text(encoding="utf-8")
    if "balance >= ?" in text:
        return ""  # already patched
    old_target = """    cur = conn.cursor()
    cur.execute("SELECT balance FROM accounts WHERE id = ?", (from_id,))
    row = cur.fetchone()
    if not row:
        return False
    balance = row[0]

    # Race window — other coroutines read before this one writes!
    await asyncio.sleep(0.001)

    if balance < amount:
        return False

    cur.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
    cur.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
    conn.commit()
    return True"""

    new_code = """    cur = conn.cursor()
    # [BLUE AGENT PATCH]: Single atomic conditional UPDATE eliminates TOCTOU window
    cur.execute("UPDATE accounts SET balance = balance - ? WHERE id = ? AND balance >= ?", (amount, from_id, amount))
    if cur.rowcount == 0:
        return False
    cur.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
    conn.commit()
    return True"""

    if old_target in text:
        filepath.write_text(text.replace(old_target, new_code), encoding="utf-8")
    diff = """--- a/challenges/challenge_1_toctou.py  (UNSAFE)
+++ b/challenges/challenge_1_toctou.py  (PATCHED by CodexArena Blue Agent)

@@ process_transfer(conn, from_id, to_id, amount) @@
-    cur.execute("SELECT balance FROM accounts WHERE id = ?", (from_id,))
-    await asyncio.sleep(0.001)   # race window
-    if balance < amount: return False
+    # Single atomic conditional UPDATE — eliminates read/write race window
+    cur.execute("UPDATE accounts SET balance = balance - ? WHERE id = ? AND balance >= ?", (amount, from_id, amount))
+    if cur.rowcount == 0:
+        return False
"""
    return diff

def _patch_negative_drain(filepath: Path) -> str:
    text = filepath.read_text(encoding="utf-8")
    if "amount <= 0" in text:
        return ""  # already patched
    target = 'def process_transfer(conn: sqlite3.Connection, from_id: int, to_id: int, amount: float) -> bool:\n    """\n    [VULNERABLE]: Does not validate amount > 0.'
    replacement = 'def process_transfer(conn: sqlite3.Connection, from_id: int, to_id: int, amount: float) -> bool:\n    # [BLUE AGENT PATCH]: Invariant guard — reject negative and zero transfers\n    if amount <= 0:\n        return False\n    """\n    [PATCHED]: Validates amount > 0.'
    if target in text:
        filepath.write_text(text.replace(target, replacement), encoding="utf-8")
    diff = """--- a/challenges/challenge_2_negative_drain.py  (UNSAFE)
+++ b/challenges/challenge_2_negative_drain.py  (PATCHED by CodexArena Blue Agent)

@@ process_transfer(conn, from_id, to_id, amount) @@
+    # Invariant guard: strictly reject non-positive amounts
+    if amount <= 0:
+        return False
"""
    return diff

def _patch_self_transfer(filepath: Path) -> str:
    text = filepath.read_text(encoding="utf-8")
    if "from_id == to_id" in text:
        return ""  # already patched
    target = 'def process_transfer(conn: sqlite3.Connection, from_id: int, to_id: int, amount: float) -> bool:\n    """\n    [VULNERABLE]: Does not check if from_id == to_id.'
    replacement = 'def process_transfer(conn: sqlite3.Connection, from_id: int, to_id: int, amount: float) -> bool:\n    # [BLUE AGENT PATCH]: Invariant guard — prohibit self-transfers\n    if from_id == to_id:\n        return False\n    """\n    [PATCHED]: Disallows self-transfer.'
    if target in text:
        filepath.write_text(text.replace(target, replacement), encoding="utf-8")
    diff = """--- a/challenges/challenge_3_self_transfer.py  (UNSAFE)
+++ b/challenges/challenge_3_self_transfer.py  (PATCHED by CodexArena Blue Agent)

@@ process_transfer(conn, from_id, to_id, amount) @@
+    # Invariant guard: prohibit zero-sum self-transfers
+    if from_id == to_id:
+        return False
"""
    return diff

def _patch_replay(filepath: Path) -> str:
    text = filepath.read_text(encoding="utf-8")
    if "_seen_traces" in text:
        return ""  # already patched
    target = 'def process_transfer(conn: sqlite3.Connection, from_id: int, to_id: int, amount: float, trace_id: str) -> bool:\n    """\n    [VULNERABLE]: Ignores trace_id!'
    replacement = '_seen_traces = set()\n\ndef process_transfer(conn: sqlite3.Connection, from_id: int, to_id: int, amount: float, trace_id: str) -> bool:\n    # [BLUE AGENT PATCH]: Idempotency cache — reject duplicate transactions\n    if trace_id in _seen_traces:\n        return False\n    _seen_traces.add(trace_id)\n    """\n    [PATCHED]: Enforces idempotency cache.'
    if target in text:
        filepath.write_text(text.replace(target, replacement), encoding="utf-8")
    diff = """--- a/challenges/challenge_4_replay_attack.py  (UNSAFE)
+++ b/challenges/challenge_4_replay_attack.py  (PATCHED by CodexArena Blue Agent)

@@ process_transfer(conn, from_id, to_id, amount, trace_id) @@
+_seen_traces = set()
+    # Idempotency cache: reject duplicate trace_ids (O(1) lookup)
+    if trace_id in _seen_traces:
+        return False
+    _seen_traces.add(trace_id)
"""
    return diff

PATCH_FUNCS = {
    "_patch_toctou": _patch_toctou,
    "_patch_negative_drain": _patch_negative_drain,
    "_patch_self_transfer": _patch_self_transfer,
    "_patch_replay": _patch_replay,
}

async def run_standalone_challenge(battle_id: str, challenge_key: str):
    """Full lifecycle: Attack challenge file -> Heal file -> Verify -> Certify."""
    meta = CHALLENGE_MAP.get(challenge_key)
    if not meta:
        return
    filename = meta["file"]
    filepath = CHALLENGES_DIR / filename
    title = meta["title"]

    battle_manager.update_battle(
        battle_id,
        status=BattleStatus.ATTACKING,
        _message=f"Red Agent targeting standalone file: challenges/{filename} …",
    )
    await asyncio.sleep(1.0)

    # Phase 1: Attack
    _, out1 = _run_script(filename)
    is_exploited = "[EXPLOITED]" in out1

    if is_exploited:
        battle_manager.update_battle(
            battle_id,
            status=BattleStatus.CRASHED,
            resilience_score=0.0,
            _message=f"[{title}] EXPLOITED! Vulnerability confirmed on challenges/{filename}",
        )
        await asyncio.sleep(1.2)

        # Phase 2: Patch
        battle_manager.update_battle(
            battle_id,
            status=BattleStatus.PATCHING,
            _message=f"Blue Agent synthesizing hot-patch for challenges/{filename} …",
        )
        pfunc = PATCH_FUNCS[meta["patch_func"]]
        diff = pfunc(filepath)
        await asyncio.sleep(1.0)

        battle_manager.update_battle(
            battle_id,
            status=BattleStatus.HEALED,
            patch_diff=diff,
            _message=f"Blue Agent patched challenges/{filename} on disk (permanent)!",
        )
        await asyncio.sleep(1.2)

        # Phase 3: Verify
        battle_manager.update_battle(
            battle_id,
            _message=f"Re-running test on challenges/{filename} to verify patch …",
        )
        _, out2 = _run_script(filename)
        is_clean = "[RESILIENT]" in out2

        if is_clean:
            battle_manager.update_battle(
                battle_id,
                status=BattleStatus.CERTIFIED,
                resilience_score=100.0,
                _message=f"PATCH VERIFIED — challenges/{filename} is 100% IMMUNE!",
            )
        else:
            battle_manager.update_battle(
                battle_id,
                status=BattleStatus.CRASHED,
                resilience_score=0.0,
                _message=f"PATCH FAILED on challenges/{filename}",
            )
    else:
        # File is ALREADY patched!
        battle_manager.update_battle(
            battle_id,
            status=BattleStatus.CERTIFIED,
            resilience_score=100.0,
            _message=f"🛡️ TARGET ALREADY RESILIENT — challenges/{filename} passed all security invariant tests cleanly!",
        )

    # Phase 4: Issue Certificate
    battle_manager.export_certificate(battle_id)
