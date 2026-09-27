"""
CodexArena FastMCP Server — exposes 5 tools IBM Bob calls to run the battle.

Transport: stdio (Bob connects via .bob/mcp.json)

Tools:
  1. launch_arena_battle(service_path, attack_type)
  2. get_crash_telemetry(battle_id)
  3. apply_hot_patch(file_path, patch_diff)
  4. verify_resilience(battle_id)
  5. export_resilience_certificate(battle_id)

Run:
    python -m mcp_server.server
"""

from __future__ import annotations

import asyncio
import json
import textwrap
from typing import Any

from fastmcp import FastMCP

from arena.battle_manager import battle_manager
from arena.blue_agent import blue_agent
from arena.models import BattleStatus
from arena.red_agent import red_agent

mcp = FastMCP(
    name="CodexArena",
    instructions=textwrap.dedent(
        """
        You are connected to CodexArena — an adversarial chaos and self-healing
        engine for mission-critical microservices.

        Workflow:
          1. Call launch_arena_battle() to start a Red Agent attack on the target service.
          2. Call get_crash_telemetry() to read the failure dump once the battle completes.
          3. Call apply_hot_patch() to trigger the autonomous Blue Agent repair pipeline.
          4. Call verify_resilience() to re-run the attack and confirm the patch holds.
          5. Call export_resilience_certificate() to retrieve the signed battle certificate.
        """
    ),
)


# ──────────────────────────────────────────────────────────────────────────────
# Tool 1: launch_arena_battle
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def launch_arena_battle(service_path: str, attack_type: str) -> str:
    """
    Launch an adversarial battle against the target microservice.

    Args:
        service_path: Base URL of the target service (e.g. 'http://localhost:9000').
        attack_type:  Type of attack to execute. Currently supported: 'race_condition'.

    Returns:
        A status message with the battle_id. Poll get_crash_telemetry() after calling this.
    """
    # Revert any previous patch so the attack hits the vulnerable code path.
    blue_agent.revert_patch()

    # Create battle record.
    battle_id = battle_manager.create_battle(attack_type, service_path)

    # Reset ledger to a known clean state before the attack.
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{service_path.rstrip('/')}/accounts/reset")
    except Exception:
        pass  # Non-fatal — ledger may already be at seed state.

    # Fire the attack as a background task so this tool call returns immediately.
    asyncio.create_task(
        red_agent.launch_attack(battle_id, service_path, attack_type)
    )

    return json.dumps(
        {
            "battle_id":  battle_id,
            "status":     "ATTACKING",
            "message":    (
                f"Red Agent launched {attack_type!r} attack on {service_path}. "
                f"Call get_crash_telemetry('{battle_id}') in ~5 seconds to read results."
            ),
        },
        indent=2,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 2: get_crash_telemetry
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_crash_telemetry(battle_id: str) -> str:
    """
    Retrieve the crash telemetry for a battle.

    Args:
        battle_id: UUID returned by launch_arena_battle().

    Returns:
        JSON with failure counts, balance drift, corrupted accounts, and sample payloads.
        If the attack is still running, status will be ATTACKING — retry in a moment.
    """
    try:
        battle = battle_manager.get_battle(battle_id)
    except KeyError:
        return json.dumps({"error": f"No battle found with id={battle_id!r}"})

    if battle.status == BattleStatus.ATTACKING:
        return json.dumps(
            {
                "battle_id": battle_id,
                "status":    "ATTACKING",
                "message":   "Attack still in progress — retry in 3 seconds.",
            }
        )

    t = battle.telemetry
    if t is None:
        return json.dumps(
            {"battle_id": battle_id, "status": battle.status.value, "telemetry": None}
        )

    corruption_confirmed = (t.balance_drift != 0.0) or bool(t.corrupted_accounts)

    return json.dumps(
        {
            "battle_id":          battle_id,
            "status":             battle.status.value,
            "attack_type":        battle.attack_type,
            "corruption":         corruption_confirmed,
            "telemetry": {
                "total_requests":     t.total_requests,
                "successful":         t.successful,
                "failed":             t.failed,
                "pre_attack_total":   t.pre_attack_total,
                "post_attack_total":  t.post_attack_total,
                "balance_drift":      t.balance_drift,
                "corrupted_accounts": t.corrupted_accounts,
                "sample_payloads":    t.sample_payloads[:3],
                "errors":             t.errors[:5],
            },
            "resilience_score":   battle.resilience_score,
            "next_step": (
                f"apply_hot_patch('{battle_id}', '') to trigger the Blue Agent repair pipeline."
                if corruption_confirmed
                else "Corruption not confirmed — consider a larger attack volume."
            ),
        },
        indent=2,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 3: apply_hot_patch
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def apply_hot_patch(file_path: str, patch_diff: str) -> str:
    """
    Trigger the autonomous Blue Agent pipeline to analyse telemetry and apply a fix.

    The Blue Agent generates the canonical patch independently. The file_path and
    patch_diff arguments are logged as intent but the agent's analysis takes precedence.

    Args:
        file_path:  (Intent) Path of the file to patch (e.g. 'ledger/database.py').
        patch_diff: (Intent) Suggested patch diff from Bob. May be empty string.

    Returns:
        JSON with the generated diff, patch status, and next steps.
    """
    # Find the most recent CRASHED battle to patch, or accept explicit battle_id
    # embedded as the first word of file_path (convenience for Bob).
    battle_id: str | None = None

    # Allow Bob to pass battle_id as file_path for direct targeting.
    for bid, b in battle_manager._battles.items():
        if b.status in (BattleStatus.CRASHED, BattleStatus.ATTACKING):
            battle_id = bid
            break

    if battle_id is None:
        return json.dumps(
            {"error": "No CRASHED battle found. Run launch_arena_battle() first."}
        )

    # Log Bob's intent.
    intent: dict[str, Any] = {
        "file_path_hint":  file_path,
        "patch_diff_hint": patch_diff[:200] if patch_diff else "(none provided)",
    }

    diff = await blue_agent.run_pipeline(battle_id)
    battle = battle_manager.get_battle(battle_id)

    return json.dumps(
        {
            "battle_id":    battle_id,
            "status":       battle.status.value,
            "patch_applied": True,
            "bob_intent":   intent,
            "generated_diff": diff,
            "next_step":    f"verify_resilience('{battle_id}') to re-run the attack and confirm the patch holds.",
        },
        indent=2,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 4: verify_resilience
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def verify_resilience(battle_id: str) -> str:
    """
    Re-run the original attack against the patched service and compute the resilience score.

    A score of 100% means zero balance drift and zero corruption across all concurrent
    requests — the service is Battle-Hardened.

    Args:
        battle_id: UUID of the battle to verify.

    Returns:
        JSON with the resilience score (0–100), pass/fail verdict, and verification telemetry.
    """
    try:
        battle = battle_manager.get_battle(battle_id)
    except KeyError:
        return json.dumps({"error": f"No battle found with id={battle_id!r}"})

    if battle.status not in (BattleStatus.HEALED, BattleStatus.PATCHING, BattleStatus.CERTIFIED):
        return json.dumps(
            {
                "error":  f"Battle is in status {battle.status.value}. Apply the patch first.",
                "hint":   f"apply_hot_patch('{battle_id}', '')",
            }
        )

    vt = await red_agent.verify_attack(battle_id, battle.service_url)
    battle = battle_manager.get_battle(battle_id)

    passed = battle.resilience_score >= 100.0
    return json.dumps(
        {
            "battle_id":        battle_id,
            "status":           battle.status.value,
            "resilience_score": battle.resilience_score,
            "verdict":          "✅ BATTLE-HARDENED" if passed else f"❌ VULNERABLE (score={battle.resilience_score:.1f}%)",
            "verify_telemetry": {
                "total":         vt.total_requests,
                "successful":    vt.successful,
                "failed":        vt.failed,
                "balance_drift": vt.balance_drift,
            },
            "next_step": (
                f"export_resilience_certificate('{battle_id}') to retrieve the signed certificate."
                if passed
                else "The patch did not achieve full resilience — review the telemetry."
            ),
        },
        indent=2,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 5: export_resilience_certificate
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def export_resilience_certificate(battle_id: str) -> str:
    """
    Export the signed ResilienceCertificate for a completed battle.

    Args:
        battle_id: UUID of the battle to certify.

    Returns:
        JSON certificate with battle metadata, resilience score, patch summary, and verdict.
    """
    try:
        cert = battle_manager.export_certificate(battle_id)
    except KeyError:
        return json.dumps({"error": f"No battle found with id={battle_id!r}"})

    return json.dumps(
        {
            "certificate": cert.to_dict(),
            "message": (
                "🏅 Certificate issued. This service has been verified Battle-Hardened "
                "against adversarial concurrent load by CodexArena."
            ),
        },
        indent=2,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
