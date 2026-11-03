"""Endpoints produits + catégories + opérations internes stock."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..cache import ProductCache, get_product_cache
from ..database import get_db
from ..deps import AdminPayloadDep, DBDep
from ..models import Category, Product
from ..schemas import (
    CategoryCreate,
    CategoryRead,
    CategoryWithCount,
    ProductCreate,
    ProductDetail,
    ProductPage,
    ProductRead,
    ProductUpdate,
    StockAdjust,
    StockAdjustResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _page_to_json(page: ProductPage) -> str:
    return page.model_dump_json()


def product_to_detail(db: Session, product: Product) -> ProductDetail:
    d = ProductDetail.model_validate(product)
    if product.category_id is not None:
        cat = db.get(Category, product.category_id)
        if cat is not None:
            d.category_slug = cat.slug
            d.category_name = cat.name
    return d


# ----------------------------- Produits publics -----------------------------


def _list_products_cache_key_args(query: str, category: str | None, page: int, page_size: int, in_stock: bool):
    return (query, category, page, page_size, in_stock)


@router.get("/products", response_model=ProductPage, response_model_exclude_none=False)
def list_products(
    db: DBDep,
    response: Response,
    q: str = Query(default="", max_length=120, description="Recherche texte dans nom/description"),
    category: str | None = Query(default=None, description="slug de catégorie"),
    ids: str | None = Query(default=None, max_length=2000, description="Liste d'IDs séparés par des virgules (usage inter-service)"),
    in_stock: bool = Query(default=False, description="Uniquement produits avec stock > 0"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    cache: ProductCache = Depends(get_product_cache),
):
    """Liste paginée, filtrable, recherche. Cache Redis TTL 60 s (le filtre `ids` n'est caché)."""
    query_str = q
    # Le filtre inter-service `ids` bypass le cache : appelé avec des valeurs fraîches
    cacheable = ids is None
    key_args = _list_products_cache_key_args(query_str, category, page, page_size, in_stock)

    if cacheable:
        cached = cache.get_list(*key_args)
        if cached is not None:
            response.headers["X-Cache"] = "HIT"
            return ProductPage.model_validate_json(cached)

    stmt = (
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.created_at.desc(), Product.id.desc())
    )
    count_base = select(func.count(Product.id)).where(Product.is_active.is_(True))

    if ids:
        id_list = []
        for raw in ids.split(","):
            try:
                id_value = int(raw.strip())
            except ValueError:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"ID produit invalide : {raw!r}")
            id_list.append(id_value)
        stmt = stmt.where(Product.id.in_(id_list))
        count_base = count_base.where(Product.id.in_(id_list))
        if len(id_list) > 200:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Maximum 200 IDs par requête")

    if query_str:
        like = f"%{query_str.lower()}%"
        cond = or_(func.lower(Product.name).like(like), func.lower(Product.description).like(like))
        stmt = stmt.where(cond)
        count_base = count_base.where(cond)

    cat_slug = category
    if cat_slug:
        sub = select(Category.id).where(Category.slug == cat_slug)
        cat_id = db.scalar(sub)
        if cat_id is None:
            return ProductPage(items=[], total=0, page=page, page_size=page_size)  # caché aussi (404-like vide)
        stmt = stmt.where(Product.category_id == cat_id)
        count_base = count_base.where(Product.category_id == cat_id)

    if in_stock:
        cond = Product.stock > 0
        stmt = stmt.where(cond)
        count_base = count_base.where(cond)

    total = db.scalar(count_base) or 0
    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    result = ProductPage(
        items=[ProductRead.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    if cacheable:
        cache.set_list(*key_args, value=_page_to_json(result))
    response.headers["X-Cache"] = "MISS" if cacheable else "BYPASS"
    return result


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, db: DBDep):
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit introuvable")
    return product_to_detail(db, product)


@router.get("/categories", response_model=list[CategoryWithCount])
def list_categories(db: DBDep):
    stmt = select(
        Category,
        func.count(Product.id),
    ).outerjoin(
        Product, (Product.category_id == Category.id) & Product.is_active
    ).group_by(Category.id).order_by(Category.name)
    rows = db.execute(stmt).all()
    return [
        CategoryWithCount(
            id=cat.id, name=cat.name, slug=cat.slug, product_count=count or 0
        )
        for cat, count in rows
    ]


# ------------------------- Administration (ADMIN) -------------------------


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreate,
    db: DBDep,
    _admin: AdminPayloadDep,
    cache: ProductCache = Depends(get_product_cache),
):
    if db.scalar(select(Product.id).where(Product.slug == data.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Un produit avec ce slug existe déjà")
    if data.category_id is not None and db.get(Category, data.category_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Catégorie inconnue")
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    cache.invalidate_product_keys()
    logger.info("event", extra={"event": "product_created", "instance": product.id})
    return product


@router.put("/products/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: DBDep,
    _admin: AdminPayloadDep,
    cache: ProductCache = Depends(get_product_cache),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit introuvable")
    payload = data.model_dump(exclude_unset=True)
    if "category_id" in payload and payload["category_id"] is not None:
        if db.get(Category, payload["category_id"]) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Catégorie inconnue")
    for field, value in payload.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    cache.invalidate_product_keys()
    logger.info("event", extra={"event": "product_updated", "instance": product.id})
    return product


@router.delete("/products/{product_id}", response_model=ProductRead)
def delete_product(
    product_id: int,
    db: DBDep,
    _admin: AdminPayloadDep,
    cache: ProductCache = Depends(get_product_cache),
):
    """Suppression = désactivation (soft-delete) pour préserver l'historique commandes."""
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit introuvable")
    product.is_active = False
    product.stock = 0
    db.commit()
    db.refresh(product)
    cache.invalidate_product_keys()
    logger.info("event", extra={"event": "product_deactivated", "instance": product.id})
    return product


@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, db: DBDep, _admin: AdminPayloadDep, cache: ProductCache = Depends(get_product_cache)):
    if db.scalar(select(Category.id).where(Category.slug == data.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Une catégorie avec ce slug existe déjà")
    category = Category(**data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    cache.invalidate_product_keys()
    return category


@router.delete("/categories/{category_id}", response_model=CategoryRead)
def delete_category(category_id: int, db: DBDep, _admin: AdminPayloadDep, cache: ProductCache = Depends(get_product_cache)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Catégorie introuvable")
    # Détache les produits (category_id → NULL) mais ne supprime pas les produits
    db.delete(category)
    db.commit()
    cache.invalidate_product_keys()
    return CategoryRead.model_validate(category)


# ------------------------------ Interne stock ------------------------------


@router.post(
    "/products/{product_id}/adjust-stock",
    response_model=StockAdjustResponse,
    responses={404: {}, 409: {"description": "Stock résultant négatif"}, 422: {}},
)
def adjust_stock(
    product_id: int,
    data: StockAdjust,
    db: DBDep,
    _admin: AdminPayloadDep,
    cache: ProductCache = Depends(get_product_cache),
):
    """Appelé par le service Commandes pour réserver lib t restituer du stock."""
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit introuvable")
    new_stock = product.stock + data.delta
    if new_stock < 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Stock insuffisant")
    product.stock = new_stock
    db.commit()
    cache.invalidate_product_keys()
    return StockAdjustResponse(product_id=product.id, stock_after=new_stock)
