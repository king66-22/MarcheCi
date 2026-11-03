"""Schémas Pydantic (validation entrée/sortie du service Catalogue)."""

from pydantic import BaseModel, Field, HttpUrl, field_validator


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
    image_url: HttpUrl | None = None

    @field_validator("image_url", mode="before")
    @classmethod
    def empty_to_none(cls, v):
        if v == "" or v is None:
            return None
        return v


class ProductCreate(ProductBase):
    slug: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    price_xof: int | None = Field(default=None, ge=0)
    category_id: int | None = None
    stock: int | None = Field(default=None, ge=0)
    image_url: HttpUrl | None = None


class ProductRead(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    price_xof: int
    category_id: int | None
    stock: int
    image_url: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class ProductDetail(ProductRead):
    category_slug: str | None = None
    category_name: str | None = None


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
