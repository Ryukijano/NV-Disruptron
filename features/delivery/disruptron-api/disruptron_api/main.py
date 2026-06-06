from __future__ import annotations

import logging

import uvicorn

from disruptron_api.config import ApiSettings
from disruptron_api.delivery.telegram import TelegramDelivery
from disruptron_api.gateway import create_app
from disruptron_api.subscriptions import SubscriptionStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run() -> None:
    settings = ApiSettings.from_env()
    store = SubscriptionStore(settings.subscriptions_path)
    delivery = TelegramDelivery(settings.telegram_bot_token)
    app = create_app(settings, store, delivery)

    logger.info(
        "NV Disruptron outputs API listening on %s:%s",
        settings.push_host,
        settings.push_port,
    )
    uvicorn.run(app, host=settings.push_host, port=settings.push_port, log_level="info")


if __name__ == "__main__":
    run()
