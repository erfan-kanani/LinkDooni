"""Use original saved URL for duplicate detection.

Revision ID: 0002_unique_original_link_url
Revises: 0001_initial
Create Date: 2026-05-10 14:45:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_unique_original_link_url"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_links_user_canonical_url", "links", type_="unique")
    op.create_unique_constraint("uq_links_user_url", "links", ["user_id", "url"])


def downgrade() -> None:
    op.drop_constraint("uq_links_user_url", "links", type_="unique")
    op.create_unique_constraint(
        "uq_links_user_canonical_url", "links", ["user_id", "canonical_url"]
    )
