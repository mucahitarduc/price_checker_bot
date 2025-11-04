# test_scrape.py
import sys
import datetime
from scraper import fetch_hepsiburada_price
from db import init_db, Product, PriceLog
from utils import domain_from_url

DB_URL = "sqlite:///./prices.db"

Session = init_db(DB_URL)

def test_price(url: str):
    session = Session()
    domain = domain_from_url(url) or ""
    if "hepsiburada" not in domain:
        print("❌ Şu an sadece hepsiburada destekleniyor.")
        return

    # Ürün DB'de var mı kontrol et
    product = session.query(Product).filter_by(url=url).first()
    if not product:
        product = Product(url=url, domain=domain, title=None)
        session.add(product)
        session.commit()
        print(f"✅ Yeni ürün eklendi. ID: {product.id}")

    print("🔎 Fiyat çekiliyor...")
    price, _ = fetch_hepsiburada_price(url)
    if price is None:
        print("⚠️  Fiyat alınamadı.")
        return

    # Son log'u al
    last_log = session.query(PriceLog).filter_by(product_id=product.id).order_by(PriceLog.checked_at.desc()).first()
    last_price = last_log.price if last_log else None

    # Yeni fiyatı ekle
    pl = PriceLog(product_id=product.id, price=price, currency="TRY", checked_at=datetime.datetime.utcnow())
    session.add(pl)
    session.commit()

    print(f"💾 Kaydedildi: {price:.2f} TL")

    # Karşılaştırma
    if last_price is not None:
        if price < last_price:
            diff = last_price - price
            print(f"📉 Fiyat düştü! {last_price:.2f} → {price:.2f} TL  (-{diff:.2f} TL)")
        elif price > last_price:
            diff = price - last_price
            print(f"📈 Fiyat arttı! {last_price:.2f} → {price:.2f} TL  (+{diff:.2f} TL)")
        else:
            print(f"⚖️  Fiyat değişmedi ({price:.2f} TL).")
    else:
        print("📦 İlk kayıt — karşılaştırma yok.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        url = "https://www.hepsiburada.com/samsung-43-m7-ls43bm700upxuf-60hz-4ms-hdmi-type-c-uhd-akilli-monitor-p-HBCV000040I4O2" # input("Hepsiburada ürün linkini girin: ").strip()
    else:
        url = sys.argv[1]
    test_price(url)
