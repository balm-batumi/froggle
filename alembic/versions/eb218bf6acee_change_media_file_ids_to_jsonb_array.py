"""Change media_file_ids to JSONB array

Revision ID: eb218bf6acee
Revises: 1c26600bb2cd
Create Date: 2025-03-25 10:35:56.393128

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'eb218bf6acee'
down_revision: Union[str, None] = '1c26600bb2cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column(
        'advertisements',
        'media_file_ids',
        existing_type=sa.ARRAY(sa.String()),
        type_=sa.ARRAY(sa.dialects.postgresql.JSONB()),
        nullable=True,
        postgresql_using="media_file_ids::jsonb[]"
    )


def downgrade() -> None:
    op.alter_column(
        'advertisements',
        'media_file_ids',
        existing_type=sa.ARRAY(postgresql.JSONB(astext_type=sa.Text())),
        type_=postgresql.ARRAY(sa.VARCHAR()),
        nullable=True
    )