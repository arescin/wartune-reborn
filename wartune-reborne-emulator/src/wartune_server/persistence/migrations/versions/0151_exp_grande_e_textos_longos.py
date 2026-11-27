"""EXP em 64 bits e listas de montaria/guarda sem limite de tamanho

``characters.total_gp`` passa de 2.147.483.647 no nível 78 (``AdminApi::GRADE_TOTAL_GP``: 2.096.429.635 no 78 e
3.033.865.047 no 80), então ``gp``/``total_gp`` do personagem e ``gp`` do herói viram BIGINT. As colunas de
montaria (``mount_avatars``, ``mount_expiry``, ``mount_fly``, ``mount_stars``, ``mount_since``) e
``battle_guard`` guardam listas separadas por vírgula que crescem com o número de montarias/guardas possuídas e
estouravam VARCHAR(1024)/VARCHAR(255); viram TEXT.

Revision ID: 0151
Revises: 0150
Create Date: 2026-11-27 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0151"
down_revision = "0150"
branch_labels = None
depends_on = None

BIG = [("characters", "gp"), ("characters", "total_gp"), ("heroes", "gp")]
LONG = [
    ("player_systems", "mount_avatars", 1024),
    ("player_systems", "mount_expiry", 1024),
    ("player_systems", "mount_fly", 1024),
    ("player_systems", "mount_stars", 1024),
    ("player_systems", "mount_since", 1024),
    ("player_systems", "battle_guard", 255),
]


def upgrade() -> None:
    for table, column in BIG:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.Integer(),
                type_=sa.BigInteger(),
                existing_nullable=False,
                existing_server_default="0",
            )
    for table, column, _ in LONG:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.String(),
                type_=sa.Text(),
                existing_nullable=False,
                existing_server_default="",
            )


def downgrade() -> None:
    for table, column, size in LONG:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.Text(),
                type_=sa.String(length=size),
                existing_nullable=False,
                existing_server_default="",
            )
    for table, column in BIG:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.BigInteger(),
                type_=sa.Integer(),
                existing_nullable=False,
                existing_server_default="0",
            )
