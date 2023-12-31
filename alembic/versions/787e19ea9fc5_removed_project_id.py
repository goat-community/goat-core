"""removed project_id

Revision ID: 787e19ea9fc5
Revises: c10bc2e3e748
Create Date: 2023-09-17 13:24:15.516632

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
import sqlmodel  

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '787e19ea9fc5'
down_revision = 'c10bc2e3e748'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('job', 'project_id', schema='customer')
    op.drop_column('layer', 'max_zoom', schema='customer')
    op.drop_column('layer', 'min_zoom', schema='customer')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('layer', sa.Column('min_zoom', sa.INTEGER(), autoincrement=False, nullable=True), schema='customer')
    op.add_column('layer', sa.Column('max_zoom', sa.INTEGER(), autoincrement=False, nullable=True), schema='customer')
    op.add_column('job', sa.Column('project_id', postgresql.UUID(), autoincrement=False, nullable=True), schema='customer')
    # ### end Alembic commands ###
