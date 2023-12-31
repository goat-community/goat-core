"""Init update schema

Revision ID: 141691733561
Revises: 
Create Date: 2023-08-02 19:47:05.620201

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
import sqlmodel  

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '141691733561'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS customer")
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('data_store',
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('type', sa.Text(), nullable=False),
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='customer'
    )
    op.create_table('user',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='customer'
    )
    op.create_table('folder',
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['customer.user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='customer'
    )
    op.create_table('scenario',
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['customer.user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='customer'
    )
    op.create_table('layer',
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('tags', sa.ARRAY(sa.Text()), nullable=True),
    sa.Column('thumbnail_url', sa.Text(), nullable=True),
    sa.Column('min_zoom', sa.Integer(), nullable=True),
    sa.Column('max_zoom', sa.Integer(), nullable=True),
    sa.Column('data_source', sa.Text(), nullable=True),
    sa.Column('data_reference_year', sa.Integer(), nullable=True),
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('folder_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('type', sa.Text(), nullable=False),
    sa.Column('data_store_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('extent', geoalchemy2.types.Geometry(geometry_type='MULTIPOLYGON', srid=4326, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
    sa.Column('style', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('data_type', sa.Text(), nullable=True),
    sa.Column('legend_urls', sa.ARRAY(sa.Text()), nullable=True),
    sa.Column('indicator_type', sa.Text(), nullable=True),
    sa.Column('scenario_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('scenario_type', sa.Text(), nullable=True),
    sa.Column('feature_layer_type', sa.Text(), nullable=True),
    sa.Column('size', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['data_store_id'], ['customer.data_store.id'], ),
    sa.ForeignKeyConstraint(['folder_id'], ['customer.folder.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['scenario_id'], ['customer.scenario.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['customer.user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='customer'
    )
    op.create_table('project',
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('tags', sa.ARRAY(sa.Text()), nullable=True),
    sa.Column('thumbnail_url', sa.Text(), nullable=True),
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('folder_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('initial_view_state', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['folder_id'], ['customer.folder.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['customer.user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='customer'
    )
    op.create_table('analysis_request',
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('type', sa.Text(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.Column('layer_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.ForeignKeyConstraint(['layer_id'], ['customer.layer.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='customer'
    )
    op.create_index(op.f('ix_customer_analysis_request_layer_id'), 'analysis_request', ['layer_id'], unique=False, schema='customer')
    op.create_table('layer_project',
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('group', sa.Text(), nullable=True),
    sa.Column('layer_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('style', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('query', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['layer_id'], ['customer.layer.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['customer.project.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='customer'
    )
    op.create_table('report',
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('tags', sa.ARRAY(sa.Text()), nullable=True),
    sa.Column('thumbnail_url', sa.Text(), nullable=True),
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('folder_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('report', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['folder_id'], ['customer.folder.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['customer.project.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['customer.user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='customer'
    )
    op.create_table('scenario_feature',
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.Column('feature_id', sa.Integer(), nullable=False),
    sa.Column('original_layer_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('scenario_type', sa.Text(), nullable=False),
    sa.Column('modification', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['original_layer_id'], ['customer.layer.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='customer'
    )
    op.create_table('scenario_scenario_feature',
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('scenario_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('scenario_feature_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.ForeignKeyConstraint(['scenario_feature_id'], ['customer.scenario_feature.id'], ),
    sa.ForeignKeyConstraint(['scenario_id'], ['customer.scenario.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='customer'
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('scenario_scenario_feature', schema='customer')
    op.drop_table('scenario_feature', schema='customer')
    op.drop_table('report', schema='customer')
    op.drop_table('layer_project', schema='customer')
    op.drop_index(op.f('ix_customer_analysis_request_layer_id'), table_name='analysis_request', schema='customer')
    op.drop_table('analysis_request', schema='customer')
    op.drop_table('project', schema='customer')
    op.drop_table('layer', schema='customer')
    op.drop_table('scenario', schema='customer')
    op.drop_table('folder', schema='customer')
    op.drop_table('user', schema='customer')
    op.drop_table('data_store', schema='customer')
    # ### end Alembic commands ###
