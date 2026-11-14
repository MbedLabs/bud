"""
Products API endpoints.
"""

from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_active_entity, get_current_user
from app.api.groups import (
    check_giveable,
    load_group,
    require_access_management,
    require_within_own_access,
)
from app.core.access import app_permissions, group_permissions, holds_on_product
from app.db import get_db
from app.models import (
    NotificationChannel,
    Product,
    ProductAccess,
    ProductNotificationRule,
    Runner,
)
from app.models.access import AccessGroup
from app.models.user import User
from app.schemas import (
    ProductCreate,
    ProductGroupMembers,
    ProductMemberResponse,
    ProductNotificationChannelOption,
    ProductNotificationRuleCreate,
    ProductNotificationRuleResponse,
    ProductNotificationRuleUpdate,
    ProductResponse,
    ProductUpdate,
)
from app.services.audit import record_audit_event

PRODUCT_NOT_FOUND = "Product not found"
RULE_NOT_FOUND = "Notification rule not found"
RULE_TARGET = "notification_rule"
INSUFFICIENT_PERMISSIONS = "Insufficient permissions."

router = APIRouter()


async def _product(db: AsyncSession, product_id: int) -> Product:
    """The product with the id; a missing product is a 404."""
    product = (
        await db.execute(select(Product).where(Product.id == product_id))
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail=PRODUCT_NOT_FOUND)
    return product


async def _require_manage(db: AsyncSession, user: User, product_id: int) -> None:
    """Refuse a user who does not hold products.manage on the product."""
    if not await holds_on_product(db, user, product_id, "products.manage"):
        raise HTTPException(status_code=403, detail=INSUFFICIENT_PERMISSIONS)


async def _members(
    db: AsyncSession, product_id: int, group_id: int | None = None
) -> List[ProductMemberResponse]:
    """The users holding a group on the product, by group then name."""
    query = (
        select(User, AccessGroup)
        .join(ProductAccess, ProductAccess.user_id == User.id)
        .join(AccessGroup, AccessGroup.id == ProductAccess.group_id)
        .where(ProductAccess.product_id == product_id)
        .order_by(AccessGroup.name, User.full_name)
    )
    if group_id is not None:
        query = query.where(ProductAccess.group_id == group_id)
    return [
        ProductMemberResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            profile_picture_url=user.profile_picture_url,
            group_id=group.id,
            group_name=group.name,
        )
        for user, group in (await db.execute(query)).all()
    ]


@router.post(
    "",
    response_model=ProductResponse,
    status_code=201,
    responses={400: {"description": "Bad Request"}, 403: {"description": "Forbidden"}},
)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new product; products.manage held app-wide is required.
    """
    if "products.manage" not in await app_permissions(db, current_user):
        raise HTTPException(status_code=403, detail=INSUFFICIENT_PERMISSIONS)
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
        raise HTTPException(status_code=404, detail=PRODUCT_NOT_FOUND)
    return product


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    responses={
        400: {"description": "Bad Request"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: User = Depends(get_current_user),
):
    """
    Change a product's name, description or status; products.manage on the product is required.
    """
    product = await _product(db, product_id)
    await _require_manage(db, current_user, product_id)
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


@router.delete(
    "/{product_id}",
    status_code=204,
    responses={403: {"description": "Forbidden"}, 404: {"description": "Not Found"}},
)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a product and its assignments; products.manage on the product is required.
    """
    product = await _product(db, product_id)
    await _require_manage(db, current_user, product_id)
    await record_audit_event(
        db,
        "product.deleted",
        target_type="product",
        target_id=product.id,
        product_id=product.id,
        details={"name": product.name},
    )
    await db.execute(delete(ProductAccess).where(ProductAccess.product_id == product_id))
    await db.execute(
        delete(ProductNotificationRule).where(ProductNotificationRule.product_id == product_id)
    )
    await db.delete(product)


@router.get(
    "/{product_id}/members",
    response_model=List[ProductMemberResponse],
    responses={403: {"description": "Forbidden"}, 404: {"description": "Not Found"}},
)
async def list_product_members(
    product_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _actor: User = Depends(require_access_management),
):
    """The users holding each group on the product."""
    await _product(db, product_id)
    return await _members(db, product_id)


@router.put(
    "/{product_id}/groups/{group_id}/members",
    response_model=List[ProductMemberResponse],
    responses={
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        422: {"description": "Unprocessable Content"},
    },
)
async def set_product_group_members(
    product_id: int,
    group_id: int,
    data: ProductGroupMembers,
    db: AsyncSession = Depends(get_db, scope="function"),
    actor: User = Depends(require_access_management),
):
    """Make exactly the listed users hold the group on the product; each change is audited."""
    await _product(db, product_id)
    group = await load_group(db, group_id)
    await require_within_own_access(db, actor, group_permissions(group))
    wanted = set(data.user_ids)
    current = set(
        await db.scalars(
            select(ProductAccess.user_id).where(
                ProductAccess.product_id == product_id, ProductAccess.group_id == group_id
            )
        )
    )
    for user_id in sorted(wanted - current):
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=404, detail="User not found")
        await check_giveable(db, actor, group, user)
        db.add(ProductAccess(product_id=product_id, user_id=user_id, group_id=group_id))
        await record_audit_event(
            db,
            "product.member_added",
            target_type="product",
            target_id=product_id,
            product_id=product_id,
            details={"user_id": user_id, "group_id": group_id},
        )
    for user_id in sorted(current - wanted):
        await db.execute(
            delete(ProductAccess).where(
                ProductAccess.product_id == product_id,
                ProductAccess.group_id == group_id,
                ProductAccess.user_id == user_id,
            )
        )
        await record_audit_event(
            db,
            "product.member_removed",
            target_type="product",
            target_id=product_id,
            product_id=product_id,
            details={"user_id": user_id, "group_id": group_id},
        )
    await db.flush()
    return await _members(db, product_id, group_id)


async def _managed_product(db: AsyncSession, user: User, product_id: int) -> Product:
    """The product, when the user holds products.manage on it; 404 or 403 otherwise."""
    product = await _product(db, product_id)
    await _require_manage(db, user, product_id)
    return product


def _rule_response(rule: ProductNotificationRule) -> ProductNotificationRuleResponse:
    """A rule with its channel's name, format and state."""
    return ProductNotificationRuleResponse(
        id=rule.id,
        product_id=rule.product_id,
        channel_id=rule.channel_id,
        channel_name=rule.channel.name,
        channel_format=rule.channel.format,
        channel_enabled=rule.channel.enabled,
        run_filter=rule.run_filter,
    )


async def _rule(db: AsyncSession, product_id: int, rule_id: int) -> ProductNotificationRule:
    """The product's rule with the id; any other rule is a 404."""
    rule = (
        await db.execute(
            select(ProductNotificationRule).where(
                ProductNotificationRule.id == rule_id,
                ProductNotificationRule.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail=RULE_NOT_FOUND)
    return rule


async def _audit_rule(
    db: AsyncSession, action: str, rule: ProductNotificationRule, channel_name: str
) -> None:
    """Record a rule change in the audit log with its product, channel and run filter."""
    await record_audit_event(
        db,
        action,
        target_type=RULE_TARGET,
        target_id=rule.id,
        product_id=rule.product_id,
        details={"channel": channel_name, "run_filter": rule.run_filter},
    )


@router.get(
    "/{product_id}/notification-channels",
    response_model=List[ProductNotificationChannelOption],
    responses={
        403: {"description": HTTPStatus(403).phrase},
        404: {"description": HTTPStatus(404).phrase},
    },
)
async def list_product_notification_channels(
    product_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: User = Depends(get_current_user),
):
    """The channels a rule on the product can point at, without their URL or secret."""
    await _managed_product(db, current_user, product_id)
    channels = (
        (await db.execute(select(NotificationChannel).order_by(NotificationChannel.name)))
        .scalars()
        .all()
    )
    return [
        ProductNotificationChannelOption(
            id=channel.id, name=channel.name, format=channel.format, enabled=channel.enabled
        )
        for channel in channels
    ]


@router.get(
    "/{product_id}/notification-rules",
    response_model=List[ProductNotificationRuleResponse],
    responses={
        403: {"description": HTTPStatus(403).phrase},
        404: {"description": HTTPStatus(404).phrase},
    },
)
async def list_product_notification_rules(
    product_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: User = Depends(get_current_user),
):
    """The product's rules, by channel name."""
    await _managed_product(db, current_user, product_id)
    rules = (
        (
            await db.execute(
                select(ProductNotificationRule)
                .join(
                    NotificationChannel,
                    NotificationChannel.id == ProductNotificationRule.channel_id,
                )
                .where(ProductNotificationRule.product_id == product_id)
                .order_by(NotificationChannel.name)
            )
        )
        .scalars()
        .all()
    )
    return [_rule_response(rule) for rule in rules]


@router.post(
    "/{product_id}/notification-rules",
    response_model=ProductNotificationRuleResponse,
    status_code=201,
    responses={
        400: {"description": HTTPStatus(400).phrase},
        403: {"description": HTTPStatus(403).phrase},
        404: {"description": HTTPStatus(404).phrase},
    },
)
async def create_product_notification_rule(
    product_id: int,
    data: ProductNotificationRuleCreate,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: User = Depends(get_current_user),
):
    """Post the product's finished runs to a channel, filtered by the rule's run filter."""
    await _managed_product(db, current_user, product_id)
    channel = await db.get(NotificationChannel, data.channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    taken = (
        await db.execute(
            select(ProductNotificationRule.id).where(
                ProductNotificationRule.product_id == product_id,
                ProductNotificationRule.channel_id == channel.id,
            )
        )
    ).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(
            status_code=400, detail="The product already has a rule for this channel"
        )
    rule = ProductNotificationRule(
        product_id=product_id, channel_id=channel.id, run_filter=data.run_filter
    )
    db.add(rule)
    await db.flush()
    await _audit_rule(db, "notification_rule.created", rule, channel.name)
    await db.refresh(rule, ["channel"])
    return _rule_response(rule)


@router.patch(
    "/{product_id}/notification-rules/{rule_id}",
    response_model=ProductNotificationRuleResponse,
    responses={
        403: {"description": HTTPStatus(403).phrase},
        404: {"description": HTTPStatus(404).phrase},
    },
)
async def update_product_notification_rule(
    product_id: int,
    rule_id: int,
    data: ProductNotificationRuleUpdate,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: User = Depends(get_current_user),
):
    """Change a rule's run filter."""
    await _managed_product(db, current_user, product_id)
    rule = await _rule(db, product_id, rule_id)
    rule.run_filter = data.run_filter
    await db.flush()
    await _audit_rule(db, "notification_rule.updated", rule, rule.channel.name)
    return _rule_response(rule)


@router.delete(
    "/{product_id}/notification-rules/{rule_id}",
    status_code=204,
    responses={
        403: {"description": HTTPStatus(403).phrase},
        404: {"description": HTTPStatus(404).phrase},
    },
)
async def delete_product_notification_rule(
    product_id: int,
    rule_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: User = Depends(get_current_user),
):
    """Stop posting the product's runs to the rule's channel."""
    await _managed_product(db, current_user, product_id)
    rule = await _rule(db, product_id, rule_id)
    await _audit_rule(db, "notification_rule.deleted", rule, rule.channel.name)
    await db.delete(rule)
    await db.flush()
    return Response(status_code=204)
