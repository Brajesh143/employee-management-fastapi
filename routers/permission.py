from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.permissions import require_permission
from crud import permission as crud
from database import get_db
from models.employee import Employee
from schemas.permission import (
    PermissionCreate,
    PermissionResponse,
    PermissionUpdate,
)
from schemas.role_permission import RolePermissionUpdate


router = APIRouter()


@router.get(
    "/",
    response_model=list[PermissionResponse],
    dependencies=[Depends(require_permission("permission:manage"))],
)
def list_permissions(db: Session = Depends(get_db)):
    return crud.list_permissions(db)


@router.post(
    "/",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("permission:manage"))],
)
def create_permission(
    payload: PermissionCreate,
    db: Session = Depends(get_db),
):
    return crud.create_permission(db, payload)


@router.patch(
    "/{permission_id}",
    response_model=PermissionResponse,
    dependencies=[Depends(require_permission("permission:manage"))],
)
def update_permission(
    permission_id: int,
    payload: PermissionUpdate,
    db: Session = Depends(get_db),
):
    permission = crud.update_permission(db, permission_id, payload)
    if permission is None:
        raise HTTPException(status_code=404, detail="Permission not found.")
    return permission


@router.delete(
    "/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("permission:manage"))],
)
def delete_permission(
    permission_id: int,
    db: Session = Depends(get_db),
):
    if crud.delete_permission(db, permission_id) is None:
        raise HTTPException(status_code=404, detail="Permission not found.")


@router.get(
    "/roles/{role_id}/permissions",
    response_model=list[PermissionResponse],
    dependencies=[Depends(require_permission("role:read"))],
)
def list_role_permissions(role_id: int, db: Session = Depends(get_db)):
    permissions = crud.list_role_permissions(db, role_id)
    if permissions is None:
        raise HTTPException(status_code=404, detail="Role not found.")
    return permissions


@router.put(
    "/roles/{role_id}/permissions",
    response_model=list[PermissionResponse],
    dependencies=[Depends(require_permission("role:assign"))],
)
def replace_role_permissions(
    role_id: int,
    payload: RolePermissionUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    permissions = crud.replace_role_permissions(
        db,
        role_id,
        payload.permission_ids,
        current_user,
    )
    if permissions is None:
        raise HTTPException(status_code=404, detail="Role not found.")
    return permissions
