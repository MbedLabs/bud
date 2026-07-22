"""
Products API endpoints.
"""

from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_active_entity, require_role
from app.db import get_db
from app.models import Product, Runner
from app.models.user import User, UserRole
from app.schemas import ProductCreate, ProductResponse

router = APIRouter()


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Create a new product.
    """
    # Check if product already exists
    result = await db.execute(select(Product).where(Product.name == data.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Product with this name already exists")

    product = Product(
        name=data.name,
        description=data.description,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


@router.get("", response_model=List[ProductResponse])
async def list_products(
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    List all products.
    """
    result = await db.execute(select(Product).order_by(Product.name))
    return result.scalars().all()


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    Get a product by ID.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Delete a product.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
