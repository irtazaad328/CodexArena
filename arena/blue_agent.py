"""
BlueAgent — autonomous 4-vector self-healing pipeline.

Generates a multi-layer patch diff covering all four attack vectors and
activates it by writing LEDGER_SAFE_MODE=1 to ledger/.env.
"""

from __future__ import annotations

from pathlib import Path

from arena.battle_manager import battle_manager
from arena.models import BattleStatus

_LEDGER_ENV = Path(__file__).parent.parent / "ledger" / ".env"

_PATCH_DIFF = """\
--- a/ledger/database.py  (UNSAFE — 4 vectors exploitable)
+++ b/ledger/database.py  (SAFE  — all 4 vectors neutralised)

@@ VECTOR 1 — TOCTOU Concurrency Race @@
-async def transfer_funds_unsafe(from_id, to_id, amount):
-    # READ balance (race window opens)
-    balance = await SELECT balance WHERE id=from_id
-    await asyncio.sleep(0)          # ← other coroutines read same stale balance
-    if balance >= amount:
-        await UPDATE balance - amount  # all 50 coroutines reach here → overdraft!
+async def transfer_funds_safe(from_id, to_id, amount, trace_id):
+    # ATOMIC: single conditional UPDATE — no read/write split, no race window
+    result = await UPDATE accounts SET balance=balance-?
+             WHERE id=? AND balance>=?
+    if result.rowcount == 0:
+        return {"ok": False, "error": "Insufficient funds"}  # atomically rejected

@@ VECTOR 2 — Replay / Idempotency Attack @@
-    # trace_id IGNORED — identical requests re-processed every time
-    pass
+    if trace_id in _seen_trace_ids:
+        return {"ok": False, "error": "Duplicate trace_id rejected"}
+    _seen_trace_ids.add(trace_id)    # idempotency cache — O(1) lookup

@@ VECTOR 3 — Self-Transfer Invariant @@
-    # No validation — from_id == to_id silently accepted
-    pass
+    if from_id == to_id:
+        return {"ok": False, "error": "Self-transfers are not permitted"}

@@ VECTOR 4 — Rapid Burst Saturation @@
-    # No connection pooling — each burst request opens a new SQLite connection
+    # Atomicity from V1 serialises writes at the DB level;
+    # burst throughput is absorbed without data corruption.
+    # (connection-pool hardening left for production hardening phase)
"""


class BlueAgent:

    async def run_pipeline(self, battle_id: str) -> str:
        """
        4-vector self-healing pipeline:
          1. Analyse all vector results from telemetry.
          2. Generate multi-layer diff.
          3. Apply LEDGER_SAFE_MODE=1.
          4. Update BattleManager to HEALED.
        """
        battle = battle_manager.get_battle(battle_id)
        t = battle.telemetry

        # 1. Analyse -----------------------------------------------------------
        vectors_hit = (
            [vr.vector for vr in t.vector_results if vr.corrupted]
            if t and t.vector_results else ["unknown"]
        )
        battle_manager.update_battle(
            battle_id,
            status=BattleStatus.PATCHING,
            _message=(
                f"Blue Agent analysing {len(vectors_hit)} exploited vector(s): "
                f"{', '.join(vectors_hit)} …"
            ),
        )

        # 2. Generate diff -----------------------------------------------------
        diff = self._generate_diff(battle_id)
        battle_manager.update_battle(
            battle_id,
            patch_diff=diff,
            _message=(
                "Blue Agent generated 4-layer hot-patch: "
                "atomic UPDATE (V1) + idempotency cache (V2) + "
                "self-transfer guard (V3) + burst atomicity (V4) …"
            ),
        )

        # 3. Apply patch -------------------------------------------------------
        self._apply_patch()

        # 4. Mark HEALED -------------------------------------------------------
        battle_manager.update_battle(
            battle_id,
            status=BattleStatus.HEALED,
            _message=(
                "LEDGER_SAFE_MODE=1 written to ledger/.env — "
                "all 4 defensive layers active (no restart required)"
            ),
        )
        return diff

    def _generate_diff(self, battle_id: str) -> str:
        battle = battle_manager.get_battle(battle_id)
        header = ""
        if battle.telemetry:
            t = battle.telemetry
            exploited = sum(1 for vr in t.vector_results if vr.corrupted) if t.vector_results else "?"
            header = (
                f"# CodexArena Multi-Vector Hot-Patch — Battle {battle_id[:8]}\n"
                f"# Vectors exploited: {exploited}/4\n"
                f"# Layers applied: atomic-UPDATE | idempotency-cache | "
                f"self-transfer-guard | burst-atomicity\n\n"
            )
        return header + _PATCH_DIFF

    def _apply_patch(self) -> None:
        _LEDGER_ENV.parent.mkdir(parents=True, exist_ok=True)
        _LEDGER_ENV.write_text("LEDGER_SAFE_MODE=1\n", encoding="utf-8")

    def revert_patch(self) -> None:
        if _LEDGER_ENV.exists():
            _LEDGER_ENV.write_text("LEDGER_SAFE_MODE=0\n", encoding="utf-8")


blue_agent = BlueAgent()
