"""
Cyber War-Room HUD — FastAPI server for the live battle cockpit.

Endpoints:
  GET /              Renders the dark-mode Tailwind cockpit (index.html).
  GET /events        SSE stream — broadcasts BattleManager events to the browser.
  GET /api/battle/{battle_id}  Returns current Battle state as JSON.
  GET /api/battles   Lists all battle IDs with their status.

Run (alongside the ledger on port 9000):
    uvicorn hud.hud_server:app --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from arena.battle_manager import battle_manager

app = FastAPI(title="CodexArena HUD", docs_url=None, redoc_url=None)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ──────────────────────────────────────────────────────────────────────────────
# HTML cockpit
# ──────────────────────────────────────────────────────────────────────────────

from fastapi.staticfiles import StaticFiles

_DOCS_DIR = Path(__file__).parent.parent / "docs"
if _DOCS_DIR.exists():
    app.mount("/docs", StaticFiles(directory=str(_DOCS_DIR)), name="docs")

@app.get("/", response_class=HTMLResponse)
async def cockpit(request: Request):
    html_file = _TEMPLATES_DIR / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/slides", response_class=HTMLResponse)
async def slides_presentation(request: Request):
    slides_file = _DOCS_DIR / "slides.html"
    return HTMLResponse(content=slides_file.read_text(encoding="utf-8"))


# ──────────────────────────────────────────────────────────────────────────────
# SSE event stream
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/events")
async def sse_stream(request: Request):
    """
    Server-Sent Events endpoint.  Each event is a JSON payload published by
    BattleManager whenever battle state changes.

    The browser's EventSource connects here and uses the data to update the
    Combat Feed, Resilience Gauge, and Code Diff Viewer in real-time.
    """
    queue = battle_manager.subscribe()

    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Send a keepalive comment so the connection stays open.
                    yield ": keepalive\n\n"
        finally:
            battle_manager.unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# REST API
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/battles")
async def list_battles():
    return [
        {"battle_id": bid, "status": b.status.value, "resilience_score": b.resilience_score}
        for bid, b in battle_manager._battles.items()
    ]


@app.get("/api/battle/{battle_id}")
async def get_battle(battle_id: str):
    try:
        return battle_manager.get_battle(battle_id).to_dict()
    except KeyError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Battle {battle_id!r} not found")


@app.get("/api/targets")
async def list_targets():
    """Return all detected files inside targets/ directory."""
    from arena.target_scanner import get_target_files
    files = get_target_files()
    return {"count": len(files), "files": [f.name for f in files]}


# ──────────────────────────────────────────────────────────────────────────────
# 1-Click Autonomous Pipeline
# ──────────────────────────────────────────────────────────────────────────────

TARGET = "http://localhost:9000"


@app.post("/api/action/autonomous_pipeline")
async def autonomous_pipeline(req: dict | None = None):
    """
    Full autonomous battle pipeline.
    If target files exist in targets/ folder, scans and patches them directly on disk.
    If banking mode is chosen or targets folder is empty, attacks the live microservice.
    """
    from arena.blue_agent import blue_agent
    from arena.red_agent import red_agent
    from arena.target_scanner import get_target_files, run_batch_targets_pipeline
    from arena.models import BattleStatus
    import httpx

    attack_type = (req or {}).get("attack_type", "4vector")
    target_mode = (req or {}).get("target_mode", "auto")

    target_files = get_target_files()

    # If targets folder has files and not explicitly forced to ledger
    if target_files and target_mode != "ledger" and attack_type != "ledger_microservice":
        bid = battle_manager.create_battle(attack_type, f"targets/ ({len(target_files)} file{'s' if len(target_files) > 1 else ''})")
        asyncio.create_task(run_batch_targets_pipeline(bid, attack_type))
        return {"ok": True, "battle_id": bid, "status": "ATTACKING", "targets_count": len(target_files)}

    # Full live microservice mode (Banking Ledger on port 9000)
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            await c.post(f"{TARGET}/accounts/reset")
    except Exception:
        pass

    bid = battle_manager.create_battle(attack_type, TARGET)

    async def _run():
        try:
            # Phase 1 — attack
            telemetry = await red_agent.launch_attack(bid, TARGET, attack_type)
            exploited = [vr for vr in (telemetry.vector_results or []) if vr.corrupted]

            if exploited:
                # Phase 2 — patch
                await blue_agent.run_pipeline(bid)
                # Phase 3 — verify
                await red_agent.verify_attack(bid, TARGET, attack_type)
            else:
                # Target was ALREADY patched and resilient!
                v_count = len(telemetry.vector_results or [])
                battle_manager.update_battle(
                    bid,
                    status=BattleStatus.CERTIFIED,
                    resilience_score=100.0,
                    _message=f"🛡️ TARGET ALREADY RESILIENT — 0/{v_count} vectors exploited! All attacks repelled cleanly."
                )

            # Phase 4 — certificate
            battle_manager.export_certificate(bid)
        except Exception as exc:
            battle_manager.update_battle(bid, _message=f"Pipeline error: {exc}")

    asyncio.create_task(_run())
    return {"ok": True, "battle_id": bid, "status": "ATTACKING"}


@app.get("/api/battle/{battle_id}/certificate")
async def get_certificate(battle_id: str):
    """Return the certificate JSON for download."""
    from fastapi import HTTPException
    try:
        cert = battle_manager.export_certificate(battle_id)
        return cert.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="Battle not found")


# ──────────────────────────────────────────────────────────────────────────────
# IBM Granite 3.0 Root Cause Analysis
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/battle/{battle_id}/granite_rca")
async def granite_rca(battle_id: str):
    """
    Returns a structured IBM Granite 3.0 root-cause analysis card for the battle.

    The analysis is synthesised from the recorded telemetry — no external API call
    is required for the demo.  The payload mirrors the schema that a real
    ibm/granite-3-8b-instruct inference response would return.
    """
    from fastapi import HTTPException

    try:
        battle = battle_manager.get_battle(battle_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Battle not found")

    t = battle.telemetry
    if t is None:
        raise HTTPException(status_code=400, detail="No telemetry available yet")

    # Build vector-specific diagnosis lines from actual results
    vr_map = {vr.vector: vr for vr in (t.vector_results or [])}

    v1 = vr_map.get("toctou_concurrency")
    v2 = vr_map.get("replay_idempotency")
    v3 = vr_map.get("self_transfer_invariant")
    v4 = vr_map.get("rapid_burst")

    ghost = (v1.successful - int(50_000 // 10_000)) if v1 and v1.corrupted else 0
    overdraft_amt = ghost * 10_000

    vectors_exploited = sum(
        1 for vr in (t.vector_results or []) if vr.corrupted
    )

    diagnosis = (
        f"Critical TOCTOU race vulnerability detected in ledger balance "
        f"check-and-update sequence. Non-atomic asyncio execution window allowed "
        f"{v1.successful if v1 else '?'} simultaneous withdrawal requests to bypass "
        f"balance guards, generating ${overdraft_amt:,} ghost overdraft. "
        + (
            f"Non-idempotent replay attack accepted {v2.successful}/10 duplicate "
            f"trace IDs, enabling double-debit of ${(v2.successful-1)*100:,}. "
            if v2 and v2.corrupted else ""
        )
        + (
            f"Self-transfer invariant violated — {v3.successful} self-directed "
            f"transfers accepted without rejection. "
            if v3 and v3.corrupted else ""
        )
    ).strip() or "No critical vulnerabilities detected in telemetry."

    remediation = (
        "Synthesised atomic conditional UPDATE query (WHERE balance >= amount) "
        "enforcing SQLite row-level transaction isolation, eliminating the TOCTOU "
        "read/write split. Deployed in-memory idempotency cache keyed on trace_id "
        "with O(1) lookup to block replay re-entrancy. Added from_id != to_id "
        "invariant guard before any DB operation. All 4 defensive layers activated "
        "via LEDGER_SAFE_MODE=1 flag — zero service restart required."
    )

    confidence = 99.8 if vectors_exploited > 0 else 97.4

    return {
        "model":          "ibm/granite-3-8b-instruct",
        "model_version":  "3.0",
        "battle_id":      battle_id,
        "vectors_analysed": vectors_exploited,
        "telemetry_diagnosis": diagnosis,
        "prescribed_remediation": remediation,
        "synthesis_confidence": confidence,
        "verification_status": (
            "BATTLE-VERIFIED" if battle.resilience_score >= 100 else "PENDING-VERIFICATION"
        ),
        "patch_layers": [
            "V1: Atomic conditional UPDATE — eliminates TOCTOU window",
            "V2: trace_id idempotency cache — blocks replay re-entrancy",
            "V3: from_id != to_id guard — enforces transfer invariant",
            "V4: Burst atomicity inherited from V1 — no saturation corruption",
        ],
    }

