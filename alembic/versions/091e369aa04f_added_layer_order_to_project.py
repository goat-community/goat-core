"""added layer order to project

Revision ID: 091e369aa04f
Revises: e89bad838064
Create Date: 2023-11-16 17:04:00.505589

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
import sqlmodel  



# revision identifiers, used by Alembic.
revision = '091e369aa04f'
down_revision = 'e89bad838064'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('layer_project', 'z_index', schema='customer')
    op.add_column('project', sa.Column('layer_order', sa.ARRAY(sa.Integer()), nullable=True), schema='customer')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('project', 'layer_order', schema='customer')
    op.add_column('layer_project', sa.Column('z_index', sa.INTEGER(), autoincrement=False, nullable=False), schema='customer')
    # ### end Alembic commands ###
