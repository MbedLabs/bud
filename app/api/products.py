"""
Products API endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_active_entity, require_permission
from app.db import get_db
from app.models import Product, Runner
from app.models.user import User
from app.schemas import ProductCreate, ProductResponse, ProductUpdate
from app.services.audit import record_audit_event

router = APIRouter()


@router.post(
    "",
    response_model=ProductResponse,
    status_code=201,
    responses={400: {"description": "Bad Request"}},
)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_permission("products", "manage")),
):
    """
    Create a new product.
    """
    result = await db.execute(select(Product).where(Product.name == data.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Product with this name already exists")

    product = Product(
        name=data.name,
        description=data.description,
    )
    db.add(product)
    await db.flush()
    await record_audit_event(
        db,
        "product.created",
        target_type="product",
        target_id=product.id,
        product_id=product.id,
        details={"name": product.name},
    )
    await db.refresh(product)
    return product


@router.get("", response_model=List[ProductResponse])
async def list_products(
    db: AsyncSession = Depends(get_db, scope="function"),
    _current_entity: User | Runner = Depends(get_current_active_entity),
):
    """
    List all products.
    """
    result = await db.execute(select(Product).order_by(Product.name))
    return result.scalars().all()


@router.get(
    "/{product_id}", response_model=ProductResponse, responses={404: {"description": "Not Found"}}
)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _current_entity: User | Runner = Depends(get_current_active_entity),
):
    """
    Get a product by ID.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    responses={400: {"description": "Bad Request"}, 404: {"description": "Not Found"}},
)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_permission("products", "manage")),
):
    """
    Change a product's name, description or status.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if data.name is not None and data.name != product.name:
        taken = await db.execute(select(Product.id).where(Product.name == data.name))
        if taken.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="Product with this name already exists")
        product.name = data.name
    if "description" in data.model_fields_set:
        product.description = data.description
    if data.status is not None:
        product.status = data.status.value
    await db.flush()
    await record_audit_event(
        db,
        "product.updated",
        target_type="product",
        target_id=product.id,
        product_id=product.id,
        details={"fields": sorted(data.model_fields_set)},
    )
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204, responses={404: {"description": "Not Found"}})
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_permission("products", "manage")),
):
    """
    Delete a product.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await record_audit_event(
        db,
        "product.deleted",
        target_type="product",
        target_id=product.id,
        product_id=product.id,
        details={"name": product.name},
    )
    await db.delete(product)
