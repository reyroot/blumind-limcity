"""Local dev entrypoint.

psycopg's async mode cannot use Windows' default Proactor loop. uvicorn's own
``run()`` forces a Proactor loop on Windows via ``setup_event_loop()``, so we bypass
it and drive ``Server.serve()`` inside an explicit SelectorEventLoop instead.

Usage:
    venv\\Scripts\\python run.py
"""

import asyncio
import selectors
import sys

from uvicorn import Config, Server


def main() -> None:
    config = Config("main:app", host="127.0.0.1", port=8000, log_level="info")
    server = Server(config)

    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()
