import asyncio
import logging
import os
from bot import build_app
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if TELEGRAM_TOKEN is None:
    raise RuntimeError("TELEGRAM_TOKEN environment variable required")

async def main():
    app = build_app(TELEGRAM_TOKEN)

    # initialize and start the application (non-blocking)
    await app.initialize()
    await app.start()

    # start polling (non-blocking)
    await app.updater.start_polling()

    # start scheduler with the same bot instance
    bot = app.bot
    scheduler = await start_scheduler(bot)

    logger.info("Bot and scheduler running. Ctrl+C to exit.")
    # keep running until cancelled
    try:
        await asyncio.Event().wait()
    finally:
        # graceful shutdown
        scheduler.shutdown(wait=False)
        await app.updater.stop_polling()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())