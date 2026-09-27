"""
Sub-Task 2 smoke test — runs full battle lifecycle against a live ledger.
Usage:  python test_arena.py
Requires ledger running on port 9000.
"""
import asyncio

from arena.battle_manager import battle_manager
from arena.blue_agent import blue_agent
from arena.red_agent import red_agent

TARGET = "http://localhost:9000"


async def main() -> None:
    # Ensure ledger starts in UNSAFE mode
    blue_agent.revert_patch()

    # ── Phase 1: Attack ───────────────────────────────────────────────
    bid = battle_manager.create_battle("race_condition", TARGET)
    print(f"Battle created: {bid[:8]}...")

    telem = await red_agent.launch_attack(bid, TARGET, "race_condition")
    print()
    print("=== RED AGENT TELEMETRY ===")
    print(f"  Total requests : {telem.total_requests}")
    print(f"  Successful     : {telem.successful}")
    print(f"  Failed         : {telem.failed}")
    print(f"  Pre-atk total  : ${telem.pre_attack_total:,.2f}")
    print(f"  Post-atk total : ${telem.post_attack_total:,.2f}")
    drift = telem.balance_drift
    print(f"  Balance drift  : ${drift:+.2f}  <-- NON-ZERO = CORRUPTION CONFIRMED")
    print(f"  Corrupted accs : {telem.corrupted_accounts}")
    battle = battle_manager.get_battle(bid)
    print(f"  Battle status  : {battle.status}")

    # ── Phase 2: Patch ────────────────────────────────────────────────
    print()
    print("=== BLUE AGENT PATCHING ===")
    diff = await blue_agent.run_pipeline(bid)
    print(diff[:600])
    battle = battle_manager.get_battle(bid)
    print(f"  Battle status  : {battle.status}")

    # ── Phase 3: Verify ───────────────────────────────────────────────
    print()
    print("=== VERIFY RESILIENCE ===")
    vtelem = await red_agent.verify_attack(bid, TARGET, "race_condition")
    print(f"  Total requests : {vtelem.total_requests}")
    print(f"  Successful     : {vtelem.successful}")
    print(f"  Failed         : {vtelem.failed}")
    print(f"  Pre-atk total  : ${vtelem.pre_attack_total:,.2f}")
    print(f"  Post-atk total : ${vtelem.post_attack_total:,.2f}")
    vdrift = vtelem.balance_drift
    print(f"  Balance drift  : ${vdrift:+.2f}  <-- MUST BE 0.00")
    battle = battle_manager.get_battle(bid)
    print(f"  Resilience     : {battle.resilience_score}%")
    print(f"  Battle status  : {battle.status}")

    # ── Phase 4: Certificate ──────────────────────────────────────────
    cert = battle_manager.export_certificate(bid)
    print()
    print("=== RESILIENCE CERTIFICATE ===")
    print(cert.to_json())


if __name__ == "__main__":
    asyncio.run(main())
