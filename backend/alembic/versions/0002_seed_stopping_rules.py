"""seed default stopping rules per failure category

Revision ID: 0002_seed_stopping_rules
Revises: 0001_initial_schema
Create Date: 2026-09-04

Populates stopping_rules_config with sensible default bounded-retry rules for
every FailureCategory (retriable_technical, insufficient_funds, card_issue,
customer_action_needed, unknown). Idempotent and reversible.
"""

from datetime import datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "0002_seed_stopping_rules"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

stopping_rules_table = sa.table(
    "stopping_rules_config",
    sa.column("id", sa.String(36)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("failure_category", sa.String(32)),
    sa.column("max_retries", sa.Integer()),
    sa.column("retry_intervals_hours", sa.JSON()),
    sa.column("max_days_open", sa.Integer()),
    sa.column("opt_out_respected", sa.Boolean()),
)

from app.services.stopping_rules import DEFAULT_STOPPING_RULES


def upgrade() -> None:
    bind = op.get_bind()
    # Check existing failure categories so this migration is safe to re-run
    query = sa.select(stopping_rules_table.c.failure_category)
    existing_categories = set(bind.execute(query).scalars().all())

    now = datetime.now(timezone.utc)
    to_insert = [
        {
            "id": str(uuid.uuid4()),
            "created_at": now,
            "updated_at": now,
            **rule,
        }
        for rule in DEFAULT_STOPPING_RULES
        if rule["failure_category"] not in existing_categories
    ]

    if to_insert:
        op.bulk_insert(stopping_rules_table, to_insert)


def downgrade() -> None:
    bind = op.get_bind()
    categories = [rule["failure_category"] for rule in DEFAULT_STOPPING_RULES]
    delete_stmt = stopping_rules_table.delete().where(
        stopping_rules_table.c.failure_category.in_(categories)
    )
    bind.execute(delete_stmt)
