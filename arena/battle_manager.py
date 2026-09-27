"""
BattleManager — singleton registry for all active and past battles.

Responsibilities:
  - Create, retrieve, and update Battle records (keyed by UUID).
  - Publish structured SSE events to a shared asyncio.Queue consumed by the HUD.
  - Issue ResilienceCertificates once a battle reaches CERTIFIED status.

Usage:
    from arena.battle_manager import battle_manager   # import the singleton

    battle_id = battle_manager.create_battle("race_condition")
    battle_manager.update_battle(battle_id, status=BattleStatus.ATTACKING)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from arena.models import Battle, BattleStatus, ResilienceCertificate, TelemetryRecord


class BattleManager:
    def __init__(self) -> None:
        self._battles: dict[str, Battle] = {}
        # Unbounded queue; HUD drains it via SSE.  Multiple consumers each get
        # their own queue — see subscribe() / unsubscribe().
        self._subscribers: list[asyncio.Queue[str]] = []

    # ------------------------------------------------------------------
    # Battle lifecycle
    # ------------------------------------------------------------------

    def create_battle(self, attack_type: str, service_url: str = "") -> str:
        """Create a new battle and return its UUID."""
        battle_id = str(uuid.uuid4())
        battle = Battle(id=battle_id, attack_type=attack_type, service_url=service_url)
        self._battles[battle_id] = battle
        self._publish_event(
            event_type="BATTLE_CREATED",
            battle_id=battle_id,
            resilience_score=0.0,
            message=f"Battle {battle_id[:8]}… created | attack: {attack_type}",
        )
        return battle_id

    def get_battle(self, battle_id: str) -> Battle:
        battle = self._battles.get(battle_id)
        if battle is None:
            raise KeyError(f"No battle found with id={battle_id!r}")
        return battle

    def update_battle(self, battle_id: str, **kwargs: Any) -> Battle:
        """
        Update one or more fields of a Battle and publish an SSE event.

        Recognised kwargs: status, resilience_score, telemetry, verify_telemetry,
                           patch_diff, certificate, service_url.
        """
        battle = self.get_battle(battle_id)
        # _message is a sentinel — extract before iterating field kwargs
        message = kwargs.pop("_message", None)
        for key, value in kwargs.items():
            if hasattr(battle, key):
                setattr(battle, key, value)
            else:
                raise AttributeError(f"Battle has no attribute {key!r}")
        battle.updated_at = datetime.now(timezone.utc).isoformat()

        # Derive a meaningful SSE event_type from the new status when provided.
        event_type = kwargs.get("status", BattleStatus.PENDING)
        if isinstance(event_type, BattleStatus):
            event_type = event_type.value

        if message is None:
            message = f"Battle {battle_id[:8]}… → {event_type}"
        diff     = battle.patch_diff if battle.patch_diff else ""

        self._publish_event(
            event_type=event_type,
            battle_id=battle_id,
            resilience_score=battle.resilience_score,
            message=message,
            diff=diff,
        )
        return battle

    # ------------------------------------------------------------------
    # Certificate
    # ------------------------------------------------------------------

    def export_certificate(self, battle_id: str) -> ResilienceCertificate:
        battle = self.get_battle(battle_id)
        if battle.certificate is not None:
            return battle.certificate

        score = battle.resilience_score
        verdict = (
            "✅ BATTLE-HARDENED — system withstood full adversarial assault"
            if score >= 100.0
            else f"⚠️  PARTIAL RESILIENCE — score {score:.1f}%"
        )
        target_scope = battle.service_url or "Banking Ledger Microservice (Port 9000)"
        target_files = []
        if "targets/" in str(target_scope).lower():
            try:
                from arena.target_scanner import get_target_files
                target_files = [f.name for f in get_target_files()]
            except Exception:
                pass

        patch_summary = (
            battle.patch_diff.splitlines()[0] if battle.patch_diff else "Autonomous patch applied"
        )
        cert = ResilienceCertificate(
            battle_id=battle_id,
            issued_at=datetime.now(timezone.utc).isoformat(),
            attack_type=battle.attack_type,
            resilience_score=score,
            patch_summary=patch_summary,
            verdict=verdict,
            target_scope=target_scope,
            target_files=target_files,
        )
        battle.certificate = cert
        battle.updated_at  = datetime.now(timezone.utc).isoformat()
        self._publish_event(
            event_type="CERTIFIED",
            battle_id=battle_id,
            resilience_score=score,
            message=f"🏅 Certificate issued — {verdict}",
        )
        return cert

    # ------------------------------------------------------------------
    # SSE pub/sub
    # ------------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue[str]:
        """Register a new HUD subscriber and return its dedicated queue."""
        q: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def _publish_event(
        self,
        event_type: str,
        battle_id: str,
        resilience_score: float = 0.0,
        message: str = "",
        diff: str = "",
    ) -> None:
        payload = json.dumps(
            {
                "event_type":      event_type,
                "battle_id":       battle_id,
                "resilience_score": resilience_score,
                "message":         message,
                "diff":            diff,
            }
        )
        for q in list(self._subscribers):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # slow consumer — drop rather than block


# Module-level singleton — import this everywhere.
battle_manager = BattleManager()
