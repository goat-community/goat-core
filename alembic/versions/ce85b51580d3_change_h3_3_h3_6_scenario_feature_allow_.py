"""change h3_3, h3_6 scenario_feature allow null

Revision ID: ce85b51580d3
Revises: d35bdf597b3b
Create Date: 2024-07-25 21:45:02.504258

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
import sqlmodel  



# revision identifiers, used by Alembic.
revision = 'ce85b51580d3'
down_revision = 'd35bdf597b3b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('scenario_feature', 'h3_3',
               existing_type=sa.INTEGER(),
               nullable=True,
               schema='customer')
    op.alter_column('scenario_feature', 'h3_6',
               existing_type=sa.INTEGER(),
               nullable=True,
               schema='customer')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('scenario_feature', 'h3_6',
               existing_type=sa.INTEGER(),
               nullable=False,
               schema='customer')
    op.alter_column('scenario_feature', 'h3_3',
               existing_type=sa.INTEGER(),
               nullable=False,
               schema='customer')
    # ### end Alembic commands ###
