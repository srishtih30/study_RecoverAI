"""add customer contact cap to stopping rules

Revision ID: 0003_add_max_contacts
Revises: 0002_seed_stopping_rules
Create Date: 2026-09-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_add_max_contacts"
down_revision: Union[str, None] = "0002_seed_stopping_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("stopping_rules_config") as batch_op:
        batch_op.add_column(sa.Column("max_contacts", sa.Integer(), nullable=False, server_default="2"))
    op.execute("UPDATE stopping_rules_config SET max_contacts = 1 WHERE failure_category = 'unknown'")


def downgrade() -> None:
    with op.batch_alter_table("stopping_rules_config") as batch_op:
        batch_op.drop_column("max_contacts")
