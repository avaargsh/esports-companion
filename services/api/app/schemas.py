import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class GameOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    icon_url: str | None = None
    model_config = {"from_attributes": True}


class SKUOut(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    name: str
    service_type: str
    duration_minutes: int
    price: int
    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    sku_id: uuid.UUID | None = None
    offering_id: uuid.UUID | None = None
    quantity: int = Field(default=1, ge=1, le=10)
    remark: str = Field(default="", max_length=500)


class OrderOut(BaseModel):
    id: uuid.UUID
    order_no: str
    user_id: uuid.UUID
    game_id: uuid.UUID
    sku_id: uuid.UUID
    designated_player_id: uuid.UUID | None = None
    status: str
    quantity: int
    unit_price: int
    total_amount: int
    player_amount: int
    platform_fee: int
    version: int
    model_config = {"from_attributes": True}


class OrderServicePlayerOut(BaseModel):
    id: uuid.UUID
    display_name: str
    avatar_url: str | None = None
    rating: float
    service_status: str
    binding: str
    assigned_by: str | None = None


class OrderDetailOut(OrderOut):
    service_player: OrderServicePlayerOut | None = None
    available_actions: list[str] = Field(default_factory=list)


class OrderEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    actor_type: str
    created_at: datetime
    model_config = {"from_attributes": True}


class PlayerApply(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    bio: str = Field(default="", max_length=500)


class PlayerUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    bio: str | None = Field(default=None, max_length=500)
    service_status: str | None = None


class PlayerOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    verification_status: str
    service_status: str
    model_config = {"from_attributes": True}


class PlayerSkillUpsert(BaseModel):
    rank: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    evidence_url: str = Field(min_length=1, max_length=512)


class PlayerSkillOut(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    game_id: uuid.UUID
    rank: str | None
    description: str
    evidence_url: str | None
    verification_status: str
    review_note: str
    status: str
    model_config = {"from_attributes": True}


class PublicSkillOut(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    game_name: str
    rank: str
    description: str


class ClaimRequest(BaseModel):
    expected_version: int = Field(ge=0)


class OrderMessageCreate(BaseModel):
    client_message_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=1000)


class OrderMessageOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    sender_user_id: uuid.UUID
    sender_role: str
    message_type: str
    content: str
    client_message_id: str
    created_at: object
    model_config = {"from_attributes": True}


class PaymentPrepareOut(BaseModel):
    order_id: uuid.UUID
    order_status: str
    provider: str
    payment_status: str
    client_payload: dict
    replayed: bool


class GameAdminCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_\-]+$")
    name: str = Field(min_length=1, max_length=80)
    icon_url: str | None = Field(default=None, max_length=512)
    sort_order: int = 0


class GameAdminUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    icon_url: str | None = Field(default=None, max_length=512)
    sort_order: int | None = None
    status: str | None = None


class SKUAdminCreate(BaseModel):
    game_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120)
    service_type: str = Field(min_length=1, max_length=64)
    unit: str = Field(default="SESSION", min_length=1, max_length=32)
    duration_minutes: int = Field(gt=0, le=1440)
    price: int = Field(ge=0)
    platform_fee_rate: Decimal = Field(default=Decimal("0.2000"), ge=0, le=1)
    status: str = "ACTIVE"
    config_json: dict = Field(default_factory=dict)


class SKUAdminUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    service_type: str | None = Field(default=None, min_length=1, max_length=64)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    price: int | None = Field(default=None, ge=0)
    platform_fee_rate: Decimal | None = Field(default=None, ge=0, le=1)
    status: str | None = None
    config_json: dict | None = None


class ProviderOfferingUpsert(BaseModel):
    price_override: int | None = Field(default=None, ge=0)
    description: str = Field(default="", max_length=1000)
    status: str = "ACTIVE"


class ProviderOfferingOut(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    sku_id: uuid.UUID
    price_override: int | None
    description: str
    status: str
    model_config = {"from_attributes": True}


class WithdrawalCreate(BaseModel):
    amount: int = Field(gt=0)


class WithdrawalOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    wallet_id: uuid.UUID
    amount: int
    status: str
    provider: str
    provider_txn_id: str | None
    failure_reason: str | None
    created_at: object
    completed_at: object | None
    rejected_at: object | None
    model_config = {"from_attributes": True}


class PublicOfferingOut(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    game_id: uuid.UUID
    game_name: str
    sku_name: str
    service_type: str
    duration_minutes: int
    price: int
    description: str


class PublicReviewOut(BaseModel):
    id: uuid.UUID
    rating: int
    content: str


class PublicPlayerOut(BaseModel):
    id: uuid.UUID
    display_name: str
    avatar_url: str | None = None
    bio: str
    gender: str | None = None
    service_status: str
    rating: float
    review_count: int
    order_count: int
    offerings: list[PublicOfferingOut]
    skills: list[PublicSkillOut] = Field(default_factory=list)
    reviews: list[PublicReviewOut] = Field(default_factory=list)


class DisputeCreate(BaseModel):
    reason_code: str = Field(min_length=2, max_length=64)
    description: str = Field(default="", max_length=2000)


class DisputeOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    status: str
    opened_by_user_id: uuid.UUID
    opened_by_role: str
    reason_code: str
    description: str
    held_amount: int
    resolution: str | None
    resolved_by_user_id: uuid.UUID | None
    resolved_at: object | None
    created_at: object
    model_config = {"from_attributes": True}


class RefundOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    dispute_id: uuid.UUID
    amount: int
    status: str
    provider: str
    out_refund_no: str | None
    provider_refund_id: str | None
    completed_at: object | None
    model_config = {"from_attributes": True}


class RefundComplete(BaseModel):
    provider_refund_id: str = Field(min_length=1, max_length=128)
