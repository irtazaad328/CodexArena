"""
CodexArena Unified Launcher
============================
Starts both services in the same process using uvicorn's programmatic API:
  - Banking Ledger API  →  http://localhost:9000
  - Cyber War-Room HUD  →  http://localhost:8000

Usage:
    python run.py

Press Ctrl+C to stop everything cleanly.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ensure codexarena/ is on sys.path when run.py is invoked from the repo root.
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import uvicorn


async def _serve(app_import: str, port: int, label: str) -> None:
    config = uvicorn.Config(
        app_import,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        # Reload is off — both apps share arena singletons in this process.
        reload=False,
    )
    server = uvicorn.Server(config)
    print(f"[CodexArena] {label}  ->  http://localhost:{port}")
    await server.serve()


async def main() -> None:
    print()
    print("  === CodexArena -- Adversarial Chaos & Self-Healing Engine ===")
    print("  " + "=" * 54)
    print()

    # Remove any leftover patch flag so the ledger starts VULNERABLE.
    patch_flag = _ROOT / "ledger" / ".env"
    if patch_flag.exists():
        patch_flag.unlink()
        print("[CodexArena] Cleared previous patch — ledger starting in UNSAFE mode")

    # Remove stale SQLite db so every run begins from a clean seed.
    ledger_db = _ROOT / "ledger" / "ledger.db"
    if ledger_db.exists():
        ledger_db.unlink()
        print("[CodexArena] Cleared stale ledger.db — fresh seed will be created")

    print()

    tasks = [
        asyncio.create_task(
            _serve("ledger.app:app",      9000, "Banking Ledger API  (vulnerable target)")
        ),
        asyncio.create_task(
            _serve("hud.hud_server:app",  8000, "Cyber War-Room HUD  (open in browser)  ")
        ),
    ]

    print()
    print("[CodexArena] Both services running. Open http://localhost:8000 in your browser.")
    print("[CodexArena] Then ask IBM Bob to: 'Launch a race_condition battle on http://localhost:9000'")
    print("[CodexArena] Press Ctrl+C to stop.\n")

    # Propagate Ctrl+C to both tasks.
    loop = asyncio.get_running_loop()

    def _shutdown(*_):
        print("\n[CodexArena] Shutting down …")
        for t in tasks:
            t.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except (NotImplementedError, OSError):
            # Windows does not support add_signal_handler for all signals.
            signal.signal(sig, _shutdown)

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass

    print("[CodexArena] Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
