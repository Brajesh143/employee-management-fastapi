"""Add password_hash and last_login

Revision ID: 889e93e80c00
Revises: 9cde3f51e9ee
Create Date: 2026-08-04 09:49:43.930680

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '889e93e80c00'
down_revision: Union[str, Sequence[str], None] = '9cde3f51e9ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("employees")}

    if "password_hash" not in existing_columns:
        op.add_column(
            "employees",
            sa.Column(
                "password_hash",
                sa.String(length=255),
                nullable=True,
            ),
        )

    if "last_login" not in existing_columns:
        op.add_column(
            "employees",
            sa.Column(
                "last_login",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("employees")}

    if "last_login" in existing_columns:
        op.drop_column("employees", "last_login")

    if "password_hash" in existing_columns:
        op.drop_column("employees", "password_hash")
