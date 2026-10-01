"""posicion de consolidacion de memoria.

Añade `threads.last_consolidated_message_count`: la posicion dentro del transcript ya
consolidada. `last_consolidated_at` por si sola no basta — si la cola se atrasa, dos trabajos
seguidos consolidarian el ultimo turno y los intermedios se perderian (D7).

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Añade el marcador de posicion de consolidacion."""
    op.add_column(
        "threads",
        sa.Column(
            "last_consolidated_message_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Elimina el marcador de posicion de consolidacion."""
    op.drop_column("threads", "last_consolidated_message_count")
