"""consolidation queue

Tabla `consolidation_jobs`: la cola de consolidacion de memoria (D7/D14). No es una tabla de
mensajes ni de memoria — es una cola de trabajos, encolada en la misma transaccion que el
turno y consumida con `SELECT ... FOR UPDATE SKIP LOCKED`.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea la cola de consolidacion."""
    op.create_table(
        "consolidation_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_consolidation_jobs_created_at"), "consolidation_jobs", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_consolidation_jobs_thread_id"), "consolidation_jobs", ["thread_id"], unique=False
    )
    op.create_index(
        "ix_consolidation_jobs_pending",
        "consolidation_jobs",
        ["attempts", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Elimina la cola de consolidacion."""
    op.drop_index("ix_consolidation_jobs_pending", table_name="consolidation_jobs")
    op.drop_index(op.f("ix_consolidation_jobs_thread_id"), table_name="consolidation_jobs")
    op.drop_index(op.f("ix_consolidation_jobs_created_at"), table_name="consolidation_jobs")
    op.drop_table("consolidation_jobs")
