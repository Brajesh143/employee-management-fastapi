from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from auth.dependencies import get_current_user

from models.employee import Employee
from models.role_permission import RolePermission
from models.permission import Permission


def require_permission(permission_name: str):

    def permission_checker(
        current_user: Employee = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):

        if current_user.role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role not assigned."
            )

        permissions = (
            db.query(Permission.name)
            .join(
                RolePermission,
                Permission.id == RolePermission.permission_id
            )
            .filter(
                RolePermission.role_id == current_user.role_id
            )
            .all()
        )

        permission_list = [
            permission[0]
            for permission in permissions
        ]

        if permission_name not in permission_list:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to perform this action."
            )

        return current_user

    return permission_checker