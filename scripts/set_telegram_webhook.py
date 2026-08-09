"""Register the Telegram bot webhook URL (and optional secret) via Bot API.

Usage:
    venv\\Scripts\\python -m scripts.set_telegram_webhook https://your-subdomain.ngrok-free.dev
"""

import argparse
import sys

import httpx

from app.core.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Set Telegram bot webhook URL.")
    parser.add_argument("base_url", help="Public base URL (e.g. https://xxx.ngrok-free.dev)")
    args = parser.parse_args()

    if not settings.telegram_configured:
        print("TELEGRAM_BOT_TOKEN is not set in .env", file=sys.stderr)
        sys.exit(1)

    webhook_url = f"{args.base_url.rstrip('/')}/webhook/telegram"
    payload: dict[str, str] = {"url": webhook_url}
    if settings.telegram_webhook_secret != "change-me":
        payload["secret_token"] = settings.telegram_webhook_secret

    api = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    set_resp = httpx.post(f"{api}/setWebhook", json=payload, timeout=15.0)
    print("setWebhook:", set_resp.json())

    info_resp = httpx.get(f"{api}/getWebhookInfo", timeout=15.0)
    print("getWebhookInfo:", info_resp.json())


if __name__ == "__main__":
    main()
