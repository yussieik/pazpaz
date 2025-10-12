"""Common CRUD operation helpers to reduce duplicate code."""

from __future__ import annotations

from typing import Any, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger

logger = get_logger(__name__)

# Type variable for SQLAlchemy models
ModelType = TypeVar("ModelType")


async def check_unique_name_in_workspace[T: ModelType](
    db: AsyncSession,
    model_class: type[T],
    workspace_id: Any,
    name: str,
    exclude_id: Any | None = None,
) -> None:
    """
    Check if a name is unique within a workspace.

    This helper eliminates duplicate name uniqueness validation across
    Service, Location, and other entities with workspace-scoped names.

    Args:
        db: Database session
        model_class: SQLAlchemy model class (e.g., Service, Location)
        workspace_id: Workspace UUID to check within
        name: Name to check for uniqueness
        exclude_id: Optional ID to exclude from check (for updates)

    Raises:
        HTTPException: 409 if name already exists in workspace

    Example:
        >>> await check_unique_name_in_workspace(
        ...     db, Service, workspace_id, "Massage Therapy"
        ... )
    """
    query = select(model_class).where(
        model_class.workspace_id == workspace_id,  # type: ignore[attr-defined]
        model_class.name == name,  # type: ignore[attr-defined]
    )

    if exclude_id is not None:
        query = query.where(model_class.id != exclude_id)  # type: ignore[attr-defined]

    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        entity_name = model_class.__name__  # type: ignore[attr-defined]
        logger.info(
            "unique_name_conflict",
            entity=entity_name,
            workspace_id=str(workspace_id),
            name=name,
        )
        raise HTTPException(
            status_code=409,
            detail=f"{entity_name} with name '{name}' already exists",
        )


async def soft_delete_with_fk_check[T: ModelType](
    db: AsyncSession,
    entity: T,
    entity_id: Any,
    workspace_id: Any,
    reference_model_class: type,
    reference_field_name: str,
    entity_name: str,
) -> None:
    """
    Perform smart deletion: soft delete if referenced, hard delete if not.

    This helper eliminates duplicate soft-delete logic for Service and Location
    deletion endpoints.

    Strategy:
    - If entity is referenced by other records: set is_active=False (soft delete)
    - If entity has no references: actually delete the record (hard delete)

    Args:
        db: Database session
        entity: Entity instance to delete
        entity_id: ID of the entity being deleted
        workspace_id: Workspace UUID (for logging)
        reference_model_class: Model that might reference this entity
            (e.g., Appointment)
        reference_field_name: Foreign key field name (e.g., "service_id")
        entity_name: Human-readable entity name for logging (e.g., "service")

    Example:
        >>> await soft_delete_with_fk_check(
        ...     db, service, service_id, workspace_id,
        ...     Appointment, "service_id", "service"
        ... )
    """
    # Check if entity is referenced by any records
    reference_field = getattr(reference_model_class, reference_field_name)
    count_query = select(func.count()).where(reference_field == entity_id)
    count_result = await db.execute(count_query)
    reference_count = count_result.scalar_one()

    if reference_count > 0:
        # Soft delete: set is_active to False
        entity.is_active = False  # type: ignore[attr-defined]
        await db.commit()

        logger.info(
            f"{entity_name}_soft_deleted",
            entity_id=str(entity_id),
            workspace_id=str(workspace_id),
            reference_count=reference_count,
        )
    else:
        # Hard delete: no references exist
        await db.delete(entity)
        await db.commit()

        logger.info(
            f"{entity_name}_hard_deleted",
            entity_id=str(entity_id),
            workspace_id=str(workspace_id),
        )


def apply_partial_update[T: ModelType](
    entity: T,
    update_data: BaseModel,
) -> dict[str, Any]:
    """
    Apply partial updates from Pydantic model to SQLAlchemy entity.

    This helper eliminates the duplicate pattern:
        update_data = model.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(entity, field, value)

    Args:
        entity: SQLAlchemy model instance to update
        update_data: Pydantic model with update data

    Returns:
        Dictionary of fields that were updated (for logging)

    Example:
        >>> updated_fields = apply_partial_update(client, client_data)
        >>> logger.info("client_updated", updated_fields=list(updated_fields.keys()))
    """
    update_dict = update_data.model_dump(exclude_unset=True)

    for field, value in update_dict.items():
        setattr(entity, field, value)

    return update_dict
