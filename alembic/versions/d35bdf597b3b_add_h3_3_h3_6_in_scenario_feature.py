"""add h3_3, h3_6 in scenario_feature

Revision ID: d35bdf597b3b
Revises: 2e3886888851
Create Date: 2024-07-25 21:40:28.619603

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
import sqlmodel  



# revision identifiers, used by Alembic.
revision = 'd35bdf597b3b'
down_revision = '2e3886888851'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('scenario_feature', sa.Column('h3_3', sa.Integer(), nullable=False), schema='customer')
    op.add_column('scenario_feature', sa.Column('h3_6', sa.Integer(), nullable=False), schema='customer')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('scenario_feature', 'h3_6', schema='customer')
    op.drop_column('scenario_feature', 'h3_3', schema='customer')
    # ### end Alembic commands ###