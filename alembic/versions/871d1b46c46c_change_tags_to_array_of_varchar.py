"""Change tags to ARRAY of varchar

Revision ID: 871d1b46c46c
Revises: 2e36400acbb2
Create Date: 2025-03-25 21:07:15.148437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '871d1b46c46c'
down_revision: Union[str, None] = '2e36400acbb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('advertisements', 'tags',
                    existing_type=sa.ARRAY(sa.String()),
                    type_=postgresql.ARRAY(sa.String()),
                    nullable=True)


def downgrade() -> None:
    op.alter_column('advertisements', 'tags',
                    existing_type=postgresql.ARRAY(sa.String()),
                    type_=sa.ARRAY(sa.String()),
                    nullable=True)