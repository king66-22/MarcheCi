"""Schémas Pydantic (validation entrée/sortie du service Catalogue)."""

from pydantic import BaseModel, Field, field_validator


def _image_location(value: str | None) -> str | None:
    """Accepte une URL http(s) ou un chemin local servi par la gateway (`/media/…`)."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("URL d'image invalide")
    cleaned = value.strip()
    if cleaned.startswith(("/media/", "http://", "https://")) and len(cleaned) <= 500:
        return cleaned
    raise ValueError("L'image doit être une URL http(s) ou un chemin /media/…")


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CategoryCreate(CategoryBase):
    pass


class CategoryRead(CategoryBase):
    id: int

    model_config = {"from_attributes": True}


class CategoryWithCount(CategoryRead):
    product_count: int = 0


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    price_xof: int = Field(ge=0, description="Prix en FCFA entiers")
    category_id: int | None = None
    stock: int = Field(default=0, ge=0)
    image_url: str | None = Field(default=None, max_length=500)

    @field_validator("image_url", mode="before")
    @classmethod
    def validate_image_url(cls, v):
        return _image_location(v)


class ProductCreate(ProductBase):
    slug: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    price_xof: int | None = Field(default=None, ge=0)
    category_id: int | None = None
    stock: int | None = Field(default=None, ge=0)
    image_url: str | None = Field(default=None, max_length=500)

    @field_validator("image_url", mode="before")
    @classmethod
    def validate_image_url(cls, v):
        return _image_location(v)


class ProductImageRead(BaseModel):
    id: int
    url: str
    position: int

    model_config = {"from_attributes": True}


class ProductRead(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    price_xof: int
    category_id: int | None
    owner_id: int | None = None
    stock: int
    image_url: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class ProductDetail(ProductRead):
    category_slug: str | None = None
    category_name: str | None = None
    images: list[ProductImageRead] = Field(default_factory=list)


class ProductPage(BaseModel):
    """Réponse paginée de la liste (objet mis en cache Redis)."""

    items: list[ProductRead]
    total: int
    page: int
    page_size: int


class StockAdjust(BaseModel):
    delta: int = Field(ge=-1_000_000, le=1_000_000, description="Négatif pour décrément, positif pour restituer")


class StockAdjustResponse(BaseModel):
    product_id: int
    stock_after: int
