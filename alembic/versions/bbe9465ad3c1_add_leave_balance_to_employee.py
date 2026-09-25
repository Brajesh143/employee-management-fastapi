"""add leave balance to employee

Revision ID: bbe9465ad3c1
Revises: 3bc791de62fd
Create Date: 2026-09-26 00:44:20.000221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbe9465ad3c1'
down_revision: Union[str, Sequence[str], None] = '3bc791de62fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column(
            "leave_balance",
            sa.Float(),
            nullable=False,
            server_default="24.0",
        ),
    )


def downgrade() -> None:
    op.drop_column("employees", "leave_balance")
