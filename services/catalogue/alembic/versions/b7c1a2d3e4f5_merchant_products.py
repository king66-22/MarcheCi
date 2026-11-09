"""commercant : proprietaire de produit + galerie de photos

Revision ID: b7c1a2d3e4f5
Revises: c3e6746ec0d0
Create Date: 2026-11-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c1a2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "c3e6746ec0d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajoute le propriétaire (commerçant) et la table des photos produits."""
    op.add_column("products", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.create_index("ix_products_owner_id", "products", ["owner_id"], unique=False)

    op.create_table(
        "product_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_images_product_id", "product_images", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_product_images_product_id", table_name="product_images")
    op.drop_table("product_images")
    op.drop_index("ix_products_owner_id", table_name="products")
    op.drop_column("products", "owner_id")
