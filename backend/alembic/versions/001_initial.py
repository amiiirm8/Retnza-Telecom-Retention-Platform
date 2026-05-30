"""initial schema

Revision ID: 001
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables created via seed_db Base.metadata.create_all for MVP;
    # migration mirrors models for production Alembic workflow.
    pass


def downgrade() -> None:
    pass
