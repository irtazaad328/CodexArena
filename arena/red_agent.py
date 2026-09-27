"""
RedAgent — 4-Vector adversarial attack engine.

Attack vectors:
  V1  toctou_concurrency    — 50 simultaneous transfers overdraft Treasury (TOCTOU race)
  V2  replay_idempotency    — Duplicate transactions with same trace-id exploit double-debit
  V3  self_transfer_invariant — from_account == to_account tests state duplication
  V4  rapid_burst            — 200-request high-frequency burst tests event-loop saturation
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx

from arena.battle_manager import battle_manager
from arena.models import BattleStatus, TelemetryRecord, VectorResult

# ── Attack parameters ─────────────────────────────────────────────────────────
CONCURRENCY_WORKERS  = 50
TRANSFER_AMOUNT      = 10_000.0   # 50 × $10k = $500k >> Treasury $50k → overdraft
FROM_ACCOUNT_ID      = 4          # Treasury (seed: $50,000)
TO_ACCOUNT_ID        = 1          # Alice
BURST_WORKERS        = 200        # V4 burst size
BURST_AMOUNT         = 50.0       # small amount — goal is throughput saturation


class RedAgent:
    """Adversarial HTTP attacker — dispatches one or all 4 attack vectors."""

    # ── Public entry points ───────────────────────────────────────────────────

    async def launch_attack(
        self,
        battle_id: str,
        target_url: str,
        attack_type: str = "4vector",
    ) -> TelemetryRecord:
        """Dispatch the requested attack type."""
        battle_manager.update_battle(
            battle_id,
            status=BattleStatus.ATTACKING,
            service_url=target_url,
            _message=f"Red Agent launched [{attack_type}] assault on {target_url}",
        )

        return await self._full_assault(battle_id, target_url, attack_type=attack_type)

    async def verify_attack(
        self,
        battle_id: str,
        target_url: str,
        attack_type: str = "4vector",
    ) -> TelemetryRecord:
        """Re-run vectors after the patch and score resilience."""
        base = target_url.rstrip("/")

        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"{base}/accounts/reset")

        battle_manager.update_battle(
            battle_id,
            _message=f"Ledger reset — re-running [{attack_type}] assault to verify patch …",
        )

        return await self._full_assault(battle_id, target_url, attack_type=attack_type, is_verify=True)

    # ── Combined / Selective Vector Assault ───────────────────────────────────

    async def _full_assault(
        self, battle_id: str, target_url: str, attack_type: str = "4vector", is_verify: bool = False
    ) -> TelemetryRecord:
        base   = target_url.rstrip("/")
        master = TelemetryRecord()

        # Snapshot pre-attack balances
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{base}/accounts")
            r.raise_for_status()
            pre_accounts: list[dict[str, Any]] = r.json()
        master.pre_attack_total = round(sum(a["balance"] for a in pre_accounts), 4)

        pre_treasury = next(
            (a["balance"] for a in pre_accounts if a["id"] == FROM_ACCOUNT_ID), 50_000.0
        )

        # Run selected vector(s)
        results: list[VectorResult] = []
        if attack_type in ("4vector", "all", "toctou", "toctou_concurrency", "v1", "race_condition"):
            v1 = await self._v1_toctou(battle_id, base, pre_treasury)
            results.append(v1)

        if attack_type in ("4vector", "all", "replay", "replay_idempotency", "v2"):
            v2 = await self._v2_replay(battle_id, base)
            results.append(v2)

        if attack_type in ("4vector", "all", "self_transfer", "self_transfer_invariant", "v3"):
            v3 = await self._v3_self_transfer(battle_id, base)
            results.append(v3)

        if attack_type in ("4vector", "all", "burst", "rapid_burst", "v4"):
            v4 = await self._v4_burst(battle_id, base)
            results.append(v4)

        master.vector_results = results

        # Aggregate totals
        for vr in master.vector_results:
            master.total_requests += vr.total
            master.successful     += vr.successful
            master.failed         += vr.failed
            if vr.corrupted:
                master.corrupted_accounts.append({
                    "vector":  vr.vector,
                    "detail":  vr.detail,
                })

        # Post-attack balances
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{base}/accounts")
            r.raise_for_status()
            post_accounts: list[dict[str, Any]] = r.json()
        master.post_attack_total = round(sum(a["balance"] for a in post_accounts), 4)

        post_treasury = next(
            (a["balance"] for a in post_accounts if a["id"] == FROM_ACCOUNT_ID), 0.0
        )

        has_v1 = any(vr.vector == "toctou_concurrency" for vr in master.vector_results)
        any_corrupted = any(vr.corrupted for vr in master.vector_results) or (post_treasury < 0 if has_v1 else False)

        if is_verify:
            is_clean = not any_corrupted and master.balance_drift == 0.0
            resilience = 100.0 if is_clean else 0.0
            new_status = BattleStatus.CERTIFIED if is_clean else BattleStatus.CRASHED

            battle_manager.update_battle(
                battle_id,
                status=new_status,
                verify_telemetry=master,
                resilience_score=resilience,
                _message=(
                    f"PATCH VERIFIED — {len(master.vector_results)} vector(s) neutralised | resilience: 100%"
                    if is_clean else
                    f"PATCH INCOMPLETE — vector(s) still exploitable | resilience: 0%"
                ),
            )
        else:
            battle_manager.update_battle(
                battle_id,
                status=BattleStatus.CRASHED if any_corrupted else BattleStatus.HEALED,
                telemetry=master,
                resilience_score=0.0 if any_corrupted else 100.0,
                _message=(
                    f"ASSAULT COMPLETE — "
                    f"{sum(1 for vr in master.vector_results if vr.corrupted)}/{len(master.vector_results)} vector(s) exploited"
                    if any_corrupted else
                    f"Assault: target withstood all tested vectors (0/{len(master.vector_results)} exploited)"
                ),
            )

        return master

    # ── V1: TOCTOU Concurrency Race ───────────────────────────────────────────

    async def _v1_toctou(
        self, battle_id: str, base: str, pre_treasury: float
    ) -> VectorResult:
        vr = VectorResult(
            vector="toctou_concurrency",
            label="V1: TOCTOU Concurrency Race",
            total=CONCURRENCY_WORKERS,
        )
        battle_manager.update_battle(
            battle_id,
            _message=(
                f"[V1] Firing {CONCURRENCY_WORKERS} simultaneous transfers "
                f"(${TRANSFER_AMOUNT:,.0f} each from Treasury) …"
            ),
        )

        payload = {
            "from_account": FROM_ACCOUNT_ID,
            "to_account":   TO_ACCOUNT_ID,
            "amount":       TRANSFER_AMOUNT,
        }

        async def _post(client: httpx.AsyncClient) -> dict:
            try:
                r = await client.post(f"{base}/transfer", json=payload)
                return {"ok": r.status_code == 200, "status": r.status_code,
                        "body": r.json() if r.status_code != 200 else {}}
            except Exception as exc:
                return {"ok": False, "status": 0, "error": str(exc)}

        async with httpx.AsyncClient(timeout=20.0) as client:
            results = await asyncio.gather(*[_post(client) for _ in range(CONCURRENCY_WORKERS)])

        for res in results:
            if res["ok"]:
                vr.successful += 1
            else:
                vr.failed += 1

        max_legit = int(pre_treasury // TRANSFER_AMOUNT)
        vr.corrupted = vr.successful > max_legit
        vr.detail = (
            f"{vr.successful}/{CONCURRENCY_WORKERS} accepted (max legit: {max_legit}) — "
            f"{max(0, vr.successful - max_legit)} ghost transfer(s)"
            if vr.corrupted else
            f"{vr.successful}/{CONCURRENCY_WORKERS} ok — no overdraft"
        )
        battle_manager.update_battle(
            battle_id,
            _message=f"[V1] {('EXPLOITED' if vr.corrupted else 'CLEAN')} — {vr.detail}",
        )
        return vr

    # ── V2: Non-Idempotent Replay Attack ──────────────────────────────────────

    async def _v2_replay(self, battle_id: str, base: str) -> VectorResult:
        vr = VectorResult(
            vector="replay_idempotency",
            label="V2: Replay / Idempotency Attack",
            total=10,
        )
        battle_manager.update_battle(
            battle_id,
            _message="[V2] Replaying 10 duplicate transactions with identical trace IDs …",
        )

        # Same trace-id sent 10 times — a patched system must reject duplicates
        # Use Account 1 (Alice, $10,000) so V2 has funds even if V1 drained Treasury
        trace_id = str(uuid.uuid4())
        payload  = {
            "from_account": 1,
            "to_account":   2,
            "amount":       100.0,
            "trace_id":     trace_id,
        }

        async def _post(client: httpx.AsyncClient) -> dict:
            try:
                r = await client.post(f"{base}/transfer", json=payload)
                return {"ok": r.status_code == 200}
            except Exception:
                return {"ok": False}

        async with httpx.AsyncClient(timeout=15.0) as client:
            results = await asyncio.gather(*[_post(client) for _ in range(10)])

        for res in results:
            if res["ok"]:
                vr.successful += 1
            else:
                vr.failed += 1

        # If all 10 succeed, the server has no idempotency guard — double-debit
        vr.corrupted = vr.successful > 1
        vr.detail = (
            f"{vr.successful}/10 duplicate traces accepted — "
            f"${(vr.successful - 1) * 100:,.0f} double-debited"
            if vr.corrupted else
            f"1/10 accepted, {vr.failed} duplicate traces rejected — idempotency OK"
        )
        battle_manager.update_battle(
            battle_id,
            _message=f"[V2] {('EXPLOITED' if vr.corrupted else 'CLEAN')} — {vr.detail}",
        )
        return vr

    # ── V3: Self-Transfer Invariant ───────────────────────────────────────────

    async def _v3_self_transfer(self, battle_id: str, base: str) -> VectorResult:
        vr = VectorResult(
            vector="self_transfer_invariant",
            label="V3: Self-Transfer Invariant",
            total=20,
        )
        battle_manager.update_battle(
            battle_id,
            _message="[V3] Sending 20 self-transfers (from_account == to_account) …",
        )

        # Use Account 2 (Bob, $5,000) for self-transfer testing
        payload = {
            "from_account": 2,
            "to_account":   2,   # self-transfer
            "amount":       100.0,
        }

        async def _post(client: httpx.AsyncClient) -> dict:
            try:
                r = await client.post(f"{base}/transfer", json=payload)
                return {"ok": r.status_code == 200}
            except Exception:
                return {"ok": False}

        async with httpx.AsyncClient(timeout=15.0) as client:
            results = await asyncio.gather(*[_post(client) for _ in range(20)])

        for res in results:
            if res["ok"]:
                vr.successful += 1
            else:
                vr.failed += 1

        # Any accepted self-transfer is a logic error (state can be duplicated)
        vr.corrupted = vr.successful > 0
        vr.detail = (
            f"{vr.successful}/20 self-transfers accepted — invariant violated"
            if vr.corrupted else
            f"0/20 self-transfers accepted — invariant holds"
        )
        battle_manager.update_battle(
            battle_id,
            _message=f"[V3] {('EXPLOITED' if vr.corrupted else 'CLEAN')} — {vr.detail}",
        )
        return vr

    # ── V4: Rapid Concurrency Burst ───────────────────────────────────────────

    async def _v4_burst(self, battle_id: str, base: str) -> VectorResult:
        vr = VectorResult(
            vector="rapid_burst",
            label="V4: Rapid Concurrency Burst",
            total=BURST_WORKERS,
        )
        battle_manager.update_battle(
            battle_id,
            _message=(
                f"[V4] High-frequency burst: {BURST_WORKERS} requests "
                f"(${BURST_AMOUNT} each) testing event-loop saturation …"
            ),
        )

        payload = {
            "from_account": FROM_ACCOUNT_ID,
            "to_account":   TO_ACCOUNT_ID,
            "amount":       BURST_AMOUNT,
        }

        async def _post(client: httpx.AsyncClient) -> dict:
            try:
                r = await client.post(f"{base}/transfer", json=payload)
                return {"ok": r.status_code == 200, "status": r.status_code}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        async with httpx.AsyncClient(timeout=30.0) as client:
            results = await asyncio.gather(*[_post(client) for _ in range(BURST_WORKERS)])

        errors = [r.get("error", "") for r in results if not r["ok"] and r.get("error")]
        for res in results:
            if res["ok"]:
                vr.successful += 1
            else:
                vr.failed += 1

        # V4 is about saturation — not financial corruption.
        # Flag if >10% of requests errored (connection drop / 500s), not just 400 rejections.
        error_rate = len(errors) / BURST_WORKERS
        vr.corrupted = error_rate > 0.10
        vr.detail = (
            f"{vr.successful}/{BURST_WORKERS} ok | "
            f"error rate: {error_rate*100:.1f}% — event loop saturation detected"
            if vr.corrupted else
            f"{vr.successful}/{BURST_WORKERS} processed | "
            f"error rate: {error_rate*100:.1f}% — burst absorbed cleanly"
        )
        battle_manager.update_battle(
            battle_id,
            _message=f"[V4] {('EXPLOITED' if vr.corrupted else 'CLEAN')} — {vr.detail}",
        )
        return vr


# Module-level singleton
red_agent = RedAgent()
