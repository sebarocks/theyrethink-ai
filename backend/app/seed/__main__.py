"""CLI del seed: `python -m app.seed [--export] [--no-admin]`.

Asume el esquema ya migrado (`uv run alembic upgrade head`). `--export` reescribe el
artefacto golden `app/seed/golden/canonical_state.json` tras sembrar.
"""

from __future__ import annotations

import argparse
import asyncio

from app.db import get_sessionmaker
from app.seed.export import export_canonical_state, write_golden
from app.seed.runner import seed


async def _run(*, export: bool, include_admin: bool) -> None:
    async with get_sessionmaker()() as session:
        canonical = await seed(session, include_admin=include_admin)
        print(
            f"seed: {len(canonical.roles)} roles, {len(canonical.sources)} fuentes, "
            f"{len(canonical.agents)} agentes"
        )
        if export:
            state = await export_canonical_state(session)
            destination = write_golden(state)
            print(f"golden escrito en {destination}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Siembra los datos canonicos.")
    parser.add_argument(
        "--export", action="store_true", help="Reescribe el artefacto golden tras sembrar."
    )
    parser.add_argument(
        "--no-admin", action="store_true", help="No intenta sembrar el usuario admin."
    )
    args = parser.parse_args()
    asyncio.run(_run(export=args.export, include_admin=not args.no_admin))


if __name__ == "__main__":
    main()
