"""Local dev entrypoint.

psycopg's async mode cannot use Windows' default Proactor loop. uvicorn's own
``run()`` forces a Proactor loop on Windows via ``setup_event_loop()``, so we bypass
it and drive ``Server.serve()`` inside an explicit SelectorEventLoop instead.

The classification worker runs on the same loop unless ``LIMCITY_EMBED_WORKER=0``.

Usage:
    venv\\Scripts\\python run.py
"""

import asyncio
import contextlib
import logging
import os
import selectors
import sys

from uvicorn import Config, Server

from app.workers.classify_worker import run_forever

logger = logging.getLogger(__name__)


async def serve_with_worker(server: Server) -> None:
    embed = os.environ.get("LIMCITY_EMBED_WORKER", "1") != "0"
    worker: asyncio.Task[None] | None = None
    if embed:
        worker = asyncio.create_task(run_forever(), name="limcity-classify-worker")
    try:
        await server.serve()
    finally:
        if worker is not None:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    config = Config("main:app", host=host, port=port, log_level="info")
    server = Server(config)
    logger.info(
        "Limcity demo: http://%s:%s/dashboard  admin: http://%s:%s/admin",
        host,
        port,
        host,
        port,
    )

    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.set_event_loop(loop)
        loop.run_until_complete(serve_with_worker(server))
    else:
        asyncio.run(serve_with_worker(server))


if __name__ == "__main__":
    main()
