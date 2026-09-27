"""
Arena data models — shared types used by BattleManager, RedAgent, and BlueAgent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class BattleStatus(str, Enum):
    PENDING   = "PENDING"
    ATTACKING = "ATTACKING"
    CRASHED   = "CRASHED"
    PATCHING  = "PATCHING"
    HEALED    = "HEALED"
    CERTIFIED = "CERTIFIED"


# Known attack vector names
ATTACK_VECTORS = [
    "toctou_concurrency",
    "replay_idempotency",
    "self_transfer_invariant",
    "rapid_burst",
]


@dataclass
class VectorResult:
    """Result of a single attack vector within a multi-vector assault."""
    vector:      str
    label:       str
    total:       int   = 0
    successful:  int   = 0
    failed:      int   = 0
    corrupted:   bool  = False
    detail:      str   = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "vector":     self.vector,
            "label":      self.label,
            "total":      self.total,
            "successful": self.successful,
            "failed":     self.failed,
            "corrupted":  self.corrupted,
            "detail":     self.detail,
        }


@dataclass
class TelemetryRecord:
    """Captured evidence from one Red Agent attack run."""
    total_requests:      int   = 0
    successful:          int   = 0
    failed:              int   = 0
    # Balance totals before / after the attack.
    pre_attack_total:    float = 0.0
    post_attack_total:   float = 0.0
    # Accounts whose balance deviated from expected.
    corrupted_accounts:  list[dict[str, Any]] = field(default_factory=list)
    # A small sample of the raw HTTP payloads sent.
    sample_payloads:     list[dict[str, Any]] = field(default_factory=list)
    # Error messages collected from failed responses.
    errors:              list[str]            = field(default_factory=list)
    # Per-vector breakdown (populated by 4-vector assault)
    vector_results:      list[VectorResult]   = field(default_factory=list)

    @property
    def balance_drift(self) -> float:
        """Non-zero means money was created or destroyed — proof of corruption."""
        return round(self.post_attack_total - self.pre_attack_total, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests":     self.total_requests,
            "successful":         self.successful,
            "failed":             self.failed,
            "pre_attack_total":   self.pre_attack_total,
            "post_attack_total":  self.post_attack_total,
            "balance_drift":      self.balance_drift,
            "corrupted_accounts": self.corrupted_accounts,
            "sample_payloads":    self.sample_payloads[:5],
            "errors":             self.errors[:10],
            "vector_results":     [v.to_dict() for v in self.vector_results],
        }


@dataclass
class ResilienceCertificate:
    """Issued after a battle is fully healed and verified."""
    battle_id:        str
    issued_at:        str
    attack_type:      str
    resilience_score: float
    patch_summary:    str
    verdict:          str
    target_scope:     str       = ""
    target_files:     list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "battle_id":        self.battle_id,
            "issued_at":        self.issued_at,
            "attack_type":      self.attack_type,
            "resilience_score": self.resilience_score,
            "patch_summary":    self.patch_summary,
            "verdict":          self.verdict,
            "target_scope":     self.target_scope,
            "target_files":     self.target_files,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class Battle:
    """Complete state of one CodexArena battle."""
    id:               str
    attack_type:      str
    status:           BattleStatus              = BattleStatus.PENDING
    resilience_score: float                     = 0.0
    service_url:      str                       = ""
    telemetry:        TelemetryRecord | None    = None
    verify_telemetry: TelemetryRecord | None    = None   # post-patch re-test
    patch_diff:       str                       = ""
    certificate:      ResilienceCertificate | None = None
    created_at:       str                       = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at:       str                       = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":               self.id,
            "attack_type":      self.attack_type,
            "status":           self.status.value,
            "resilience_score": self.resilience_score,
            "service_url":      self.service_url,
            "telemetry":        self.telemetry.to_dict() if self.telemetry else None,
            "verify_telemetry": self.verify_telemetry.to_dict() if self.verify_telemetry else None,
            "patch_diff":       self.patch_diff,
            "certificate":      self.certificate.to_dict() if self.certificate else None,
            "created_at":       self.created_at,
            "updated_at":       self.updated_at,
        }
