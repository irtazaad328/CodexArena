"""
Banking Ledger API — CodexArena demo target.

Run on port 9000:
    uvicorn ledger.app:app --port 9000 --reload

Environment variable:
    LEDGER_SAFE_MODE=1   Switch from the vulnerable to the patched transfer handler.
                         Checked on every request — no restart required.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

from ledger.database import get_accounts, init_db, transfer_funds_safe, transfer_funds_unsafe
from ledger.schemas import Account, HealthResponse, TransferRequest, TransferResponse

# Blue Agent writes LEDGER_SAFE_MODE=1 into this file to activate the patch.
_ENV_FILE = Path(__file__).parent / ".env"


def _is_safe_mode() -> bool:
    """
    Read the .env file directly on every call — bypasses os.environ caching
    so the Blue Agent's patch takes effect on the very next request with no restart.
    """
    if not _ENV_FILE.exists():
        return False
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("LEDGER_SAFE_MODE"):
            _, _, val = line.partition("=")
            return val.strip() == "1"
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="CodexArena Banking Ledger",
    description="A mission-critical ledger API with a race-condition vulnerability for adversarial testing.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    return HealthResponse(status="ok", safe_mode=_is_safe_mode())


@app.get("/accounts", response_model=list[Account], tags=["ledger"])
async def list_accounts():
    """Return all accounts with current balances."""
    return await get_accounts()


@app.post("/transfer", response_model=TransferResponse, tags=["ledger"])
async def transfer(req: TransferRequest):
    """
    Transfer funds between two accounts.

    **VULNERABLE by default** — uses a TOCTOU (Time-of-Check/Time-of-Use) pattern
    that allows concurrent requests to overdraft an account.

    Set LEDGER_SAFE_MODE=1 in ledger/.env to use the atomic, race-free implementation.
    """
    if _is_safe_mode():
        result = await transfer_funds_safe(req.from_account, req.to_account, req.amount, req.trace_id)
    else:
        result = await transfer_funds_unsafe(req.from_account, req.to_account, req.amount, req.trace_id)

    if not result["ok"]:
        # Return 400 so the Red Agent can count failures vs HTTP errors distinctly.
        raise HTTPException(status_code=400, detail=result)

    return TransferResponse(**result)


@app.post("/accounts/reset", tags=["system"])
async def reset():
    """Reset the database to its original seed state. Used between battle rounds."""
    await init_db()
    return {"ok": True, "message": "Ledger reset to initial state"}
