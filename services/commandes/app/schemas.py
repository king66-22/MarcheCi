"""Schémas Pydantic du service Commandes."""

from pydantic import BaseModel, Field, field_validator, model_validator


class OrderItemIn(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=999)

    @field_validator("product_id")
    @classmethod
    def positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("product_id doit être positif")
        return v


class OrderCreate(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)
    delivery_address: str = Field(min_length=10, max_length=400)
    delivery_phone: str = Field(min_length=8, max_length=30)

    @field_validator("delivery_phone")
    @classmethod
    def phone_reachable(cls, v: str) -> str:
        digits = sum(1 for c in v if c.isdigit())
        if digits < 8:
            raise ValueError("Numéro de téléphone invalide")
        return v

    @model_validator(mode="after")
    def distinct_products(self) -> "OrderCreate":
        ids = [it.product_id for it in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Un même produit apparaît plusieurs fois : fusionnez les quantités")
        return self


class OrderItemOut(BaseModel):
    product_id: int
    product_name: str
    unit_price_xof: int
    quantity: int


class OrderOut(BaseModel):
    id: int
    user_id: int
    status: str
    total_xof: int
    delivery_address: str
    delivery_phone: str
    payment_status: str
    created_at: str
    items: list[OrderItemOut]


class OrderPage(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    page_size: int


class StatusUpdate(BaseModel):
    status: str
