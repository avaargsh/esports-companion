import uuid

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
    sku_id: uuid.UUID
    quantity: int = Field(default=1, ge=1, le=10)
    remark: str = Field(default="", max_length=500)


class OrderOut(BaseModel):
    id: uuid.UUID
    order_no: str
    user_id: uuid.UUID
    game_id: uuid.UUID
    sku_id: uuid.UUID
    status: str
    quantity: int
    unit_price: int
    total_amount: int
    player_amount: int
    platform_fee: int
    version: int
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


class ClaimRequest(BaseModel):
    expected_version: int = Field(ge=0)
