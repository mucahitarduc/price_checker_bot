# bot.py
import os
import logging
import asyncio
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

from db import init_db, User, Product, PriceLog, Subscription
from scraper import fetch_price
from utils import domain_from_url
from scheduler import check_product

from sqlalchemy.exc import IntegrityError
import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./prices.db")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8043856442:AAE3D6Muz5CeE1cwdzrqnpsxvSxMTevR7QU")

Session = init_db(DB_URL)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Merhaba! Bu bot Hepsiburada, Trendyol ve Amazon linklerini takip eder. Ürün linki gönderin.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start - başlat\n/list - takipteki ürünler\n/stop <id> - takibi durdur\n")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    session = Session()
    user = session.query(User).filter_by(telegram_id=chat_id).first()
    if not user:
        await update.message.reply_text("Henüz ürün takip etmiyorsunuz.")
        return
    subs = session.query(Subscription).filter_by(user_id=user.id, active=True).all()
    if not subs:
        await update.message.reply_text("Aktif takip yok.")
        return
    lines = []
    for s in subs:
        p = s.product
        # son log
        last = session.query(PriceLog).filter_by(product_id=p.id).order_by(PriceLog.checked_at.desc()).first()
        price_str = f"{last.price:.2f}" if last else "bilinmiyor"
        lines.append(f"ID:{p.id} - {p.title or p.url}\nFiyat: {price_str}")
    await update.message.reply_text("\n\n".join(lines[:20]))

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: /stop <product_id>")
        return
    try:
        pid = int(args[0])
    except:
        await update.message.reply_text("product_id integer olmalı")
        return
    session = Session()
    user = session.query(User).filter_by(telegram_id=chat_id).first()
    if not user:
        await update.message.reply_text("Kayıtlı kullanıcı bulunamadı.")
        return
    sub = session.query(Subscription).filter_by(user_id=user.id, product_id=pid, active=True).first()
    if not sub:
        await update.message.reply_text("Bu ürün için aktif aboneliğiniz yok.")
        return
    sub.active = False
    session.commit()
    await update.message.reply_text(f"Takip durduruldu: {pid}")

async def update_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    session = Session()
    user = session.query(User).filter_by(telegram_id=chat_id).first()
    if not user:
        await update.message.reply_text("Kayıtlı kullanıcı bulunamadı.")
        return
    subs = session.query(Subscription).filter_by(user_id=user.id, active=True).all()
    if not subs:
        await update.message.reply_text("Aktif takip yok.")
        return
    count = 0
    for s in subs:
        try:
            await check_product(s.product_id, context.bot)
            count += 1
        except Exception as e:
            logger.exception("Error updating product %s", s.product_id)
    await update.message.reply_text(f"Güncelleme tamamlandı. {count} ürün kontrol edildi.")

async def link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    chat_id = str(update.effective_user.id)
    session = Session()
    # kullanıcıyı ekle / var mı kontrol
    user = session.query(User).filter_by(telegram_id=chat_id).first()
    if not user:
        user = User(telegram_id=chat_id)
        session.add(user)
        session.commit()

    # mesaj içinde ilk URL'i ayıkla (paylaş açıklaması vs. olabilir)
    m = re.search(r'(https?://[^\s]+)', text)
    if not m:
        await update.message.reply_text("Lütfen içinde bir ürün linki bulunan bir mesaj gönderin (http/https ile).")
        return
    url = m.group(1).rstrip('.,);\'"')  # sondaki noktalama işaretlerini temizle

    domain = domain_from_url(url) or ""
    if ("hepsiburada" not in domain and "hb" not in domain and
        "trendyol" not in domain and "ty" not in domain and
        "amazon" not in domain and "amzn.to" not in domain and "amzn" not in domain):
        await update.message.reply_text("Şu an Hepsiburada, Trendyol ve Amazon destekleniyor.")
        return

    # product varsa bul yoksa ekle
    product = session.query(Product).filter_by(url=url).first()
    if not product:
        # ilk fiyat çekimi yap
        await update.message.reply_text("Ürün ekleniyor, ilk fiyat çekiliyor...")
        product = Product(url=url, domain=domain, title=None)
        session.add(product)
        session.commit()
    try:
        price, _ = await fetch_price(url)
    except Exception as e:
        logger.exception("scrape error")
        await update.message.reply_text("Ürün sayfasına erişilemedi veya fiyat alınamadı. Daha sonra tekrar deneyin.")
        return
    if price is not None:
        pl = PriceLog(product_id=product.id, price=price, currency="TRY")
        session.add(pl)
        session.commit()
        await update.message.reply_text(f"Fiyat: {price:.2f} TL. ID: {product.id}")
    else:
        await update.message.reply_text(f"Fiyat alınamadı. ID: {product.id}")

    # subscription ekle
    # eğer kullanıcı zaten aboneyse onu bilgilendir
    existing = session.query(Subscription).filter_by(user_id=user.id, product_id=product.id, active=True).first()
    if existing:
        return
    sub = Subscription(user_id=user.id, product_id=product.id, active=True)
    session.add(sub)
    session.commit()
    await update.message.reply_text(f"Takip başladı. Ürün ID: {product.id}")

def build_app(token: str):
    if token is None:
        raise RuntimeError("Telegram token variable required")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("update", update_cmd))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), link_handler))
    return app

if __name__ == "__main__":
    application = build_app()
    application.run_polling()
