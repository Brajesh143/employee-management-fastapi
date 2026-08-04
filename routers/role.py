from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from auth.permissions import require_permission
from schemas.role import RoleCreate, RoleResponse, RoleUpdate
import crud.role as crud

router = APIRouter()

@router.post(
    "/",
    response_model=RoleResponse,
    dependencies=[Depends(require_permission("role:create"))]
)
def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db)
):
    return crud.create_role(
        db,
        role
    )

@router.get(
    "/",
    response_model=list[RoleResponse],
    dependencies=[Depends(require_permission("role:read"))]
)
def get_roles(
    db: Session = Depends(get_db)
):
    return crud.get_roles(db)

@router.get(
    "/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(require_permission("role:read"))]
)
def get_role(role_id: int, db: Session = Depends(get_db)):
    role = crud.get_role(
        db,
        role_id
    )

    if not role:
        raise HTTPException(
            status_code=404,
            detail="Role not found"
        )

    return role

@router.patch(
    "/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(require_permission("role:update"))]
)
def update_role(
    role_id: int,
    role: RoleUpdate,
    db: Session = Depends(get_db)
):
    updated_role = crud.update_role(
        db,
        role_id,
        role
    )

    if not updated_role:
        raise HTTPException(
            status_code=404,
            detail="Role not found"
        )

    return updated_role


@router.delete(
    "/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(require_permission("role:delete"))]
)
def delete_role(role_id: int, db: Session = Depends(get_db)):
    deleted_role = crud.delete_role(
        db,
        role_id
    )

    if not deleted_role:
        raise HTTPException(
            status_code=404,
            detail="Role not found"
        )

    return deleted_role
