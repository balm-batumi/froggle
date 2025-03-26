"""Add viewed_ads table

Revision ID: 2e36400acbb2
Revises: eb218bf6acee
Create Date: 2025-03-25 18:21:49.597430

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e36400acbb2'
down_revision: Union[str, None] = 'eb218bf6acee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'viewed_ads',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('advertisement_id', sa.Integer, sa.ForeignKey('advertisements.id'), nullable=False)
    )


def downgrade() -> None:
    op.drop_table('viewed_ads')
