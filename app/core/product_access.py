"""Which products a new run or a result upload may name."""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product
from app.schemas import ProductStatus


async def refuse_archived_product(db: AsyncSession, product_id: Optional[int]) -> None:
    """Answer 409 when the named product is archived; any other product id passes."""
    if product_id is None:
        return
    product = (
        await db.execute(select(Product).where(Product.id == product_id))
    ).scalar_one_or_none()
    if product is not None and product.status == ProductStatus.ARCHIVED.value:
        raise HTTPException(status_code=409, detail=f"Product {product.name} is archived")
