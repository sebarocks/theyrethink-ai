"""Smoke de carga mínimo de producción (Fase 6).

No sustituye a una prueba de carga real: comprueba que el servidor con varios workers
(`WEB_CONCURRENCY`) atiende tráfico moderado sin errores 5xx y con una latencia razonable.

Uso:
    uv run python -m scripts.smoke_load --base-url https://<dominio> --requests 50 --concurrency 5
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx

ENDPOINTS = ("/healthz", "/readyz")


async def _hammer(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    results: list[tuple[str, int | None, float]],
    base_url: str,
    index: int,
) -> None:
    url = base_url + ENDPOINTS[index % len(ENDPOINTS)]
    async with semaphore:
        started = time.perf_counter()
        try:
            response = await client.get(url)
            status: int | None = response.status_code
        except httpx.HTTPError:
            status = None
        results.append((url, status, time.perf_counter() - started))


async def run(base_url: str, requests: int, concurrency: int, request_timeout: float) -> int:
    semaphore = asyncio.Semaphore(concurrency)
    results: list[tuple[str, int | None, float]] = []
    async with httpx.AsyncClient(timeout=request_timeout) as client:
        await asyncio.gather(
            *(_hammer(client, semaphore, results, base_url, index) for index in range(requests))
        )

    latencies = [latency for _, _, latency in results]
    failures = [item for item in results if item[1] is None or item[1] >= 500]

    print(f"peticiones: {len(results)}  concurrencia: {concurrency}")
    print(
        "latencia (ms): "
        f"min={min(latencies) * 1000:.0f} "
        f"mediana={statistics.median(latencies) * 1000:.0f} "
        f"p95={statistics.quantiles(latencies, n=20)[18] * 1000:.0f} "
        f"max={max(latencies) * 1000:.0f}"
    )
    codes: dict[str, int] = {}
    for _, status, _ in results:
        codes[str(status)] = codes.get(str(status), 0) + 1
    print("códigos:", ", ".join(f"{code}={count}" for code, count in sorted(codes.items())))

    if failures:
        print(f"FALLO: {len(failures)} peticiones con error o 5xx")
        return 1
    print("OK: sin errores ni 5xx")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke de carga mínimo de theyrethink-ai")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    return asyncio.run(
        run(
            args.base_url.rstrip("/"),
            requests=args.requests,
            concurrency=args.concurrency,
            request_timeout=args.timeout,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
