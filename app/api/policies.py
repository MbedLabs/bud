"""Policies API: the person-agnostic permission sets that groups bundle.

Holders of access management read them; only an Admin creates, edits, duplicates or
deletes one. Default policies are read-only; duplicating one gives an editable copy.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_permission, require_role
from app.core.access import PERMISSION_CATALOGUE
from app.db.database import get_db
from app.models.access import Policy, access_group_policies
from app.models.user import User, UserRole
from app.schemas.groups import (
    CatalogueResource,
    PolicyCreate,
    PolicyResponse,
    PolicyUpdate,
)
from app.services.audit import record_audit_event

router = APIRouter()

require_access_management = require_permission("access", "manage")
require_admin = require_role(UserRole.admin)


def _normalize(permissions: dict[str, list[str]]) -> dict[str, list[str]]:
    """Validate the matrix against the catalogue and order it; unknown names are a 422."""
    matrix: dict[str, list[str]] = {}
    for resource, actions in permissions.items():
        allowed = PERMISSION_CATALOGUE.get(resource)
        if allowed is None:
            raise HTTPException(status_code=422, detail=f"Unknown resource: {resource}")
        unknown = sorted(set(actions) - set(allowed))
        if unknown:
            raise HTTPException(
                status_code=422, detail=f"Unknown action for {resource}: {', '.join(unknown)}"
            )
        if actions:
            matrix[resource] = [action for action in allowed if action in actions]
    return matrix


def _response(policy: Policy) -> PolicyResponse:
    return PolicyResponse(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        permissions=policy.permissions or {},
        is_default=policy.is_default,
        system_key=policy.system_key,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


async def _load(db: AsyncSession, policy_id: int) -> Policy:
    policy = await db.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


def _refuse_default(policy: Policy) -> None:
    if policy.is_default:
        raise HTTPException(
            status_code=409, detail="Default policies cannot be changed; duplicate it instead"
        )


async def _save(db: AsyncSession, policy: Policy) -> None:
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="A policy with this name already exists")


@router.get("/catalogue", response_model=list[CatalogueResource])
async def get_catalogue(_actor: User = Depends(require_access_management)):
    """Every resource and the actions a policy can grant on it."""
    return [
        CatalogueResource(resource=resource, actions=list(actions))
        for resource, actions in PERMISSION_CATALOGUE.items()
    ]


@router.get("", response_model=list[PolicyResponse])
async def list_policies(
    db: AsyncSession = Depends(get_db, scope="function"),
    _actor: User = Depends(require_access_management),
):
    """Every policy, defaults first."""
    policies = (
        await db.execute(select(Policy).order_by(Policy.is_default.desc(), Policy.id))
    ).scalars()
    return [_response(policy) for policy in policies]


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _actor: User = Depends(require_access_management),
):
    """One policy."""
    return _response(await _load(db, policy_id))


@router.post("", response_model=PolicyResponse, status_code=201)
async def create_policy(
    data: PolicyCreate,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """Create a custom policy."""
    policy = Policy(
        name=data.name,
        description=data.description,
        permissions=_normalize(data.permissions),
        is_default=False,
    )
    db.add(policy)
    await _save(db, policy)
    await record_audit_event(
        db,
        "policy.created",
        target_type="policy",
        target_id=policy.id,
        details={"name": policy.name, "permissions": policy.permissions},
    )
    return _response(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: int,
    data: PolicyUpdate,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """Change a custom policy's name, description or permissions."""
    policy = await _load(db, policy_id)
    _refuse_default(policy)
    if data.name is not None:
        policy.name = data.name
    if "description" in data.model_fields_set:
        policy.description = data.description
    if data.permissions is not None:
        policy.permissions = _normalize(data.permissions)
    await _save(db, policy)
    await record_audit_event(
        db,
        "policy.updated",
        target_type="policy",
        target_id=policy_id,
        details={"fields": sorted(data.model_fields_set)},
    )
    return _response(policy)


@router.post("/{policy_id}/duplicate", response_model=PolicyResponse, status_code=201)
async def duplicate_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """Create an editable copy named ``<name> (copy)``."""
    source = await _load(db, policy_id)
    copy = Policy(
        name=f"{source.name} (copy)"[:100],
        description=source.description,
        permissions=dict(source.permissions or {}),
        is_default=False,
    )
    db.add(copy)
    await _save(db, copy)
    await record_audit_event(
        db,
        "policy.created",
        target_type="policy",
        target_id=copy.id,
        details={"name": copy.name, "duplicated_from": source.id},
    )
    return _response(copy)


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """Delete a custom policy that no group uses."""
    policy = await _load(db, policy_id)
    _refuse_default(policy)
    in_use = await db.scalar(
        select(access_group_policies.c.group_id)
        .where(access_group_policies.c.policy_id == policy_id)
        .limit(1)
    )
    if in_use is not None:
        raise HTTPException(status_code=409, detail="A group uses this policy")
    await record_audit_event(
        db,
        "policy.deleted",
        target_type="policy",
        target_id=policy_id,
        details={"name": policy.name},
    )
    await db.delete(policy)
    await db.flush()
