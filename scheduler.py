# scheduler.py
import os
import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import init_db, Product, PriceLog, Subscription, User
from scraper import fetch_price
import datetime
from sqlalchemy import desc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./prices.db")
Session = init_db(DB_URL)

CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))

async def check_all_products(bot):
    session = Session()
    products = session.query(Product).all()
    logger.info("Checking %d products", len(products))
    for p in products:
        try:
            await check_product(p.id, bot)
        except Exception as e:
            logger.exception("Error checking product %s", p.id)

async def check_product(product_id, bot):
    session = Session()
    p = session.query(Product).filter_by(id=product_id).first()
    if not p:
        return
    try:
        price, _ = await fetch_price(p.url)
    except Exception as e:
        logger.exception("scrape failed for %s", p.url)
        return
    p.last_checked_at = datetime.datetime.utcnow()
    session.add(p)
    if price is None:
        session.commit()
        return

    # get last price
    last = session.query(PriceLog).filter_by(product_id=p.id).order_by(PriceLog.checked_at.desc()).first()
    last_price = last.price if last else None

    # add new log
    pl = PriceLog(product_id=p.id, price=price, currency="TRY")
    session.add(pl)
    session.commit()
    logger.info("Product %s price: %s (previous: %s)", p.id, price, last_price)

    # if price decreased vs last_price -> notify subscribers
    if last_price is not None and price < last_price:
        subs = session.query(Subscription).filter_by(product_id=p.id, active=True).all()
        for s in subs:
            user = session.query(User).filter_by(id=s.user_id).first()
            if not user:
                continue
            text = (f"Fiyat düştü!\n{p.title or p.url}\n"
                    f"Yeni fiyat: {price:.2f} TL (önceki: {last_price:.2f} TL)\n{p.url}")
            try:
                await bot.send_message(chat_id=int(user.telegram_id), text=text)
            except Exception:
                logger.exception("Couldn't send message to %s", user.telegram_id)

async def start_scheduler(bot):
    """
    Create and start APScheduler that calls check_all_products(bot) every CHECK_INTERVAL_MINUTES.
    """
    scheduler = AsyncIOScheduler()
    # use a lambda to schedule coroutine creation
    scheduler.add_job(lambda: asyncio.create_task(check_all_products(bot)), "interval", minutes=CHECK_INTERVAL_MINUTES)
    scheduler.start()
    logger.info("Scheduler started (interval: %s minutes).", CHECK_INTERVAL_MINUTES)
    return scheduler

if __name__ == "__main__":
    from telegram import Bot
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    bot = Bot(token=TELEGRAM_TOKEN)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_scheduler(bot))
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
