from pydantic import BaseModel, Field


class Account(BaseModel):
    id: int
    name: str
    balance: float


class TransferRequest(BaseModel):
    from_account: int = Field(..., description="Source account ID")
    to_account: int = Field(..., description="Destination account ID")
    amount: float = Field(..., gt=0, description="Amount to transfer (must be positive)")
    trace_id: str | None = Field(None, description="Optional idempotency key (UUID)")


class TransferResponse(BaseModel):
    ok: bool
    transferred: float | None = None
    error: str | None = None
    balance: float | None = None


class HealthResponse(BaseModel):
    status: str
    safe_mode: bool
