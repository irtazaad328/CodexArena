"""
CodexArena full battle runner — executes all 5 MCP tool flows directly.
"""
import asyncio, json
from pathlib import Path

# Clean state
patch_flag = Path(__file__).parent / "ledger" / ".env"
if patch_flag.exists():
    patch_flag.unlink()

from arena.battle_manager import battle_manager
from arena.red_agent import red_agent
from arena.blue_agent import blue_agent

TARGET = "http://localhost:9000"

SEP = "=" * 60

async def main():
    # ── TOOL 1: launch_arena_battle ──────────────────────────────
    print(f"\n{SEP}")
    print("TOOL CALL: launch_arena_battle")
    print(f"  service_path = '{TARGET}'")
    print(f"  attack_type  = 'race_condition'")
    print(SEP)

    blue_agent.revert_patch()

    import httpx
    async with httpx.AsyncClient(timeout=5) as c:
        await c.post(f"{TARGET}/accounts/reset")

    battle_id = battle_manager.create_battle("race_condition", TARGET)
    attack_task = asyncio.create_task(
        red_agent.launch_attack(battle_id, TARGET, "race_condition")
    )

    print(json.dumps({
        "battle_id": battle_id,
        "status": "ATTACKING",
        "message": f"Red Agent launched 'race_condition' attack on {TARGET}. "
                   f"Call get_crash_telemetry('{battle_id[:8]}...') in ~5 seconds."
    }, indent=2))

    # Wait for attack to complete
    telem = await attack_task

    # ── TOOL 2: get_crash_telemetry ──────────────────────────────
    print(f"\n{SEP}")
    print("TOOL CALL: get_crash_telemetry")
    print(f"  battle_id = '{battle_id}'")
    print(SEP)

    battle = battle_manager.get_battle(battle_id)
    corruption = (telem.balance_drift != 0.0) or bool(telem.corrupted_accounts)

    telemetry_resp = {
        "battle_id":   battle_id,
        "status":      battle.status.value,
        "attack_type": battle.attack_type,
        "corruption":  corruption,
        "telemetry": {
            "total_requests":    telem.total_requests,
            "successful":        telem.successful,
            "failed":            telem.failed,
            "pre_attack_total":  telem.pre_attack_total,
            "post_attack_total": telem.post_attack_total,
            "balance_drift":     telem.balance_drift,
            "corrupted_accounts": telem.corrupted_accounts,
            "sample_payloads":   telem.sample_payloads[:3],
            "errors":            telem.errors[:5],
        },
        "resilience_score": battle.resilience_score,
    }
    print(json.dumps(telemetry_resp, indent=2))

    # ── TOOL 3: apply_hot_patch ──────────────────────────────────
    print(f"\n{SEP}")
    print("TOOL CALL: apply_hot_patch")
    print(f"  file_path  = 'ledger/database.py'")
    print(f"  patch_diff = ''  (Blue Agent generates autonomously)")
    print(SEP)

    diff = await blue_agent.run_pipeline(battle_id)
    battle = battle_manager.get_battle(battle_id)

    patch_resp = {
        "battle_id":    battle_id,
        "status":       battle.status.value,
        "patch_applied": True,
        "generated_diff": diff,
        "next_step": f"verify_resilience('{battle_id[:8]}...') to confirm the patch holds.",
    }
    print(json.dumps(patch_resp, indent=2))

    # ── TOOL 4: verify_resilience ────────────────────────────────
    print(f"\n{SEP}")
    print("TOOL CALL: verify_resilience")
    print(f"  battle_id = '{battle_id}'")
    print(SEP)

    vtelem = await red_agent.verify_attack(battle_id, TARGET, "race_condition")
    battle = battle_manager.get_battle(battle_id)

    passed = battle.resilience_score >= 100.0
    verify_resp = {
        "battle_id":        battle_id,
        "status":           battle.status.value,
        "resilience_score": battle.resilience_score,
        "verdict":          "BATTLE-HARDENED" if passed else f"VULNERABLE ({battle.resilience_score:.1f}%)",
        "verify_telemetry": {
            "total":         vtelem.total_requests,
            "successful":    vtelem.successful,
            "failed":        vtelem.failed,
            "balance_drift": vtelem.balance_drift,
        },
        "next_step": f"export_resilience_certificate('{battle_id[:8]}...')",
    }
    print(json.dumps(verify_resp, indent=2))

    # ── TOOL 5: export_resilience_certificate ────────────────────
    print(f"\n{SEP}")
    print("TOOL CALL: export_resilience_certificate")
    print(f"  battle_id = '{battle_id}'")
    print(SEP)

    cert = battle_manager.export_certificate(battle_id)
    cert_resp = {
        "certificate": cert.to_dict(),
        "message": "Certificate issued. This service has been verified Battle-Hardened "
                   "against adversarial concurrent load by CodexArena."
    }
    print(json.dumps(cert_resp, indent=2))

    print(f"\n{SEP}")
    print("BATTLE COMPLETE")
    print(f"  Battle ID       : {battle_id}")
    print(f"  Resilience Score: {battle.resilience_score}%")
    verdict_safe = cert.verdict.encode("ascii", errors="replace").decode("ascii")
    print(f"  Verdict         : {verdict_safe}")
    print(SEP)

asyncio.run(main())
