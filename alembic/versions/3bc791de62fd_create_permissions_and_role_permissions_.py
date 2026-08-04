"""Create permissions and role_permissions tables

Revision ID: 3bc791de62fd
Revises: 889e93e80c00
Create Date: 2026-08-04 14:06:12.042947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3bc791de62fd'
down_revision: Union[str, Sequence[str], None] = '889e93e80c00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "permissions",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True
        ),

        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False
        ),

        sa.Column(
            "description",
            sa.String(length=255),
            nullable=True
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False
        ),

        sa.UniqueConstraint(
            "name",
            name="uq_permissions_name"
        )
    )

    op.create_index(
        "ix_permissions_name",
        "permissions",
        ["name"]
    )

    op.create_table(
        "role_permissions",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True
        ),

        sa.Column(
            "role_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "permission_id",
            sa.Integer(),
            nullable=False
        ),

        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            ondelete="CASCADE"
        ),

        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            ondelete="CASCADE"
        ),

        sa.UniqueConstraint(
            "role_id",
            "permission_id",
            name="uq_role_permission"
        )
    )

    op.create_index(
        "ix_role_permissions_role_id",
        "role_permissions",
        ["role_id"]
    )

    op.create_index(
        "ix_role_permissions_permission_id",
        "role_permissions",
        ["permission_id"]
    )



def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_role_permissions_permission_id",
        table_name="role_permissions"
    )

    op.drop_index(
        "ix_role_permissions_role_id",
        table_name="role_permissions"
    )

    op.drop_table("role_permissions")

    op.drop_index(
        "ix_permissions_name",
        table_name="permissions"
    )

    op.drop_table("permissions")
