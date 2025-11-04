import json
import re
from playwright.async_api import async_playwright

async def fetch_hepsiburada_price(url):
    try:
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            page = await browser.new_page()
            print("🧭 Hepsiburada sayfası yükleniyor...", url)

            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("networkidle")

            content = await page.content()

            # Debug amaçlı HTML kaydı
            with open("hepsiburada_debug.html", "w", encoding="utf-8") as f:
                f.write(content)

            price = None
            price_str = None

            # 0) Sepete özel fiyat
            m = re.search(r'Sepete\s+özel\s+fiyat[\s\S]{0,200}?([\d\.,]+)\s*(?:TL|₺)', content, re.IGNORECASE)
            if m:
                price_str = m.group(1)

            # 1) Premium ile <b>...</b>
            if not price_str:
                m = re.search(r'Premium\s+ile\s*<b>\s*([\d\.,]+)\s*(?:TL|₺)\s*</b>', content, re.IGNORECASE)
                if m:
                    price_str = m.group(1)

            # 2) JS veri fallback
            if not price_str:
                m = re.search(r'productsales\s*:\s*"([^"]+)"', content, re.IGNORECASE)
                if not m:
                    m = re.search(r'product_prices\s*:\s*\[\s*"?([\d\.,]+)"?\s*\]', content, re.IGNORECASE)
                if not m:
                    m = re.search(r'content_price%22%3A%5B%22([^%]+)%22%5D', content)
                if not m:
                    m = re.search(r'content_price"\s*:\s*"?([\d\.,]+)"?', content, re.IGNORECASE)
                if m:
                    price_str = m.group(1)

            # 3) utagData fallback
            if not price_str:
                match = re.search(
                    r"const\s+utagData\s*=\s*(\{.*?\});",
                    content,
                    re.DOTALL
                )
                if match:
                    json_text = match.group(1).strip()
                    try:
                        data = json.loads(json_text)
                        if "product_prices" in data and len(data["product_prices"]) > 0:
                            price_str = data["product_prices"][0]
                            print("💡 utagData'dan fiyat bulundu:", price_str)
                    except Exception as e:
                        print("⚠️ JSON parse hatası:", e)

            # 4) string → float
            if price_str:
                cleaned = price_str.strip()
                # remove anything but digits and separators
                cleaned = re.sub(r'[^\d\.,]', '', cleaned)
                if '.' in cleaned and ',' in cleaned:
                    if cleaned.rfind('.') > cleaned.rfind(','):
                        cleaned = cleaned.replace(',', '')
                    else:
                        cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    if ',' in cleaned and '.' not in cleaned:
                        frac = cleaned.split(',')[-1]
                        if len(frac) <= 2:
                            cleaned = cleaned.replace(',', '.')
                        else:
                            cleaned = cleaned.replace(',', '')
                try:
                    price = float(cleaned)
                except Exception:
                    price = price_str

            await browser.close()
            return price, url
    except Exception as e:
        print("ERROR: hepsiburada scrape error", e)
        return None, None

async def fetch_trendyol_price(url):
    try:
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            page = await browser.new_page()
            print("🧭 Trendyol sayfası yükleniyor...", url)

            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("networkidle")

            content = await page.content()

            # Debug
            with open("trendyol_debug.html", "w", encoding="utf-8") as f:
                f.write(content)

            price = None
            price_str = None

            # 0) meta product:price:amount
            m = re.search(r'<meta\s+property=["\']product:price:amount["\']\s+content=["\']([\d\.,]+)["\']', content, re.IGNORECASE)
            if m:
                price_str = m.group(1)

            # 1) LD+JSON offers.price veya price alanı
            if not price_str:
                for m in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', content, re.IGNORECASE):
                    ld = m.group(1).strip()
                    try:
                        parsed = json.loads(ld)
                        def extract_price(obj):
                            if isinstance(obj, dict):
                                if obj.get("offers") and isinstance(obj["offers"], dict) and "price" in obj["offers"]:
                                    return obj["offers"]["price"]
                                if "price" in obj:
                                    return obj["price"]
                            return None
                        candidate = None
                        if isinstance(parsed, list):
                            for item in parsed:
                                candidate = extract_price(item) or candidate
                        else:
                            candidate = extract_price(parsed)
                        if candidate:
                            price_str = str(candidate)
                            break
                    except Exception:
                        m2 = re.search(r'"price"\s*:\s*["\']?([\d\.,]+)["\']?', ld)
                        if m2:
                            price_str = m2.group(1)
                            break

            # 2) data-test-id veya sınıf bazlı içerik
            if not price_str:
                m = re.search(r'data-test-id=["\']product-price["\'][^>]*>([\s\d\.,₺TL]+)<', content, re.IGNORECASE)
                if m:
                    price_str = re.sub(r'[^\d\.,]', '', m.group(1))

            # 3) genel fallback: JSON içinde "price": ...
            if not price_str:
                m = re.search(r'["\']price["\']\s*:\s*["\']?([\d\.,]+)', content, re.IGNORECASE)
                if m:
                    price_str = m.group(1)

            # parse to float
            if price_str:
                cleaned = price_str.strip()
                cleaned = re.sub(r'[^\d\.,]', '', cleaned)
                if '.' in cleaned and ',' in cleaned:
                    if cleaned.rfind('.') > cleaned.rfind(','):
                        cleaned = cleaned.replace(',', '')
                    else:
                        cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    if ',' in cleaned and '.' not in cleaned:
                        frac = cleaned.split(',')[-1]
                        if len(frac) <= 2:
                            cleaned = cleaned.replace(',', '.')
                        else:
                            cleaned = cleaned.replace(',', '')
                try:
                    price = float(cleaned)
                except Exception:
                    price = price_str

            await browser.close()
            return price, url
    except Exception as e:
        print("ERROR: trendyol scrape error", e)
        return None, None

async def fetch_amazon_price(url):
    try:
        async with async_playwright() as p:
            # chromium genelde Amazon ile daha stabil çalışır
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                locale="tr-TR",
                viewport={"width": 1280, "height": 800},
            )
            # ek header (dil tercihi gibi)
            await context.set_extra_http_headers({"accept-language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"})
            page = await context.new_page()
            print("🧭 Amazon sayfası yükleniyor...", url)

            # daha uzun timeout, önce networkidle dene, gerekirse domcontentloaded ile retry
            try:
                await page.goto(url, timeout=120_000, wait_until="networkidle")
            except Exception:
                try:
                    await page.goto(url, timeout=120_000, wait_until="domcontentloaded")
                except Exception as e:
                    print("ERROR: Amazon page.goto failed:", e)
                    await context.close()
                    await browser.close()
                    return None, None

            content = await page.content()

            # Debug
            with open("amazon_debug.html", "w", encoding="utf-8") as f:
                f.write(content)

            price = None
            price_str = None

            # 0) common Amazon selectors: .a-offscreen is most reliable
            m = re.search(r'<span[^>]+class=["\'][^"\']*a-offscreen[^"\']*["\'][^>]*>([^<]+)<', content, re.IGNORECASE)
            if m:
                price_str = re.sub(r'[^\d\.,]', '', m.group(1))

            # 1) fallback selectors (priceblock ids)
            if not price_str:
                m = re.search(r'id=["\']priceblock_ourprice["\'][^>]*>([^<]+)<', content, re.IGNORECASE)
                if m:
                    price_str = re.sub(r'[^\d\.,]', '', m.group(1))
            if not price_str:
                m = re.search(r'id=["\']priceblock_dealprice["\'][^>]*>([^<]+)<', content, re.IGNORECASE)
                if m:
                    price_str = re.sub(r'[^\d\.,]', '', m.group(1))

            # 2) meta product:price:amount
            if not price_str:
                m = re.search(r'<meta\s+property=["\']product:price:amount["\']\s+content=["\']([\d\.,]+)["\']', content, re.IGNORECASE)
                if m:
                    price_str = m.group(1)

            # 3) LD+JSON içinden price
            if not price_str:
                for m in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', content, re.IGNORECASE):
                    ld = m.group(1).strip()
                    try:
                        parsed = json.loads(ld)
                        def extract_price(obj):
                            if isinstance(obj, dict):
                                if obj.get("offers") and isinstance(obj["offers"], dict) and "price" in obj["offers"]:
                                    return obj["offers"]["price"]
                                if "price" in obj:
                                    return obj["price"]
                            return None
                        candidate = None
                        if isinstance(parsed, list):
                            for item in parsed:
                                candidate = extract_price(item) or candidate
                        else:
                            candidate = extract_price(parsed)
                        if candidate:
                            price_str = str(candidate)
                            break
                    except Exception:
                        m2 = re.search(r'"price"\s*:\s*["\']?([\d\.,]+)["\']?', ld)
                        if m2:
                            price_str = m2.group(1)
                            break

            # 4) genel fallback JSON alanı
            if not price_str:
                m = re.search(r'["\']price["\']\s*:\s*["\']?([\d\.,]+)', content, re.IGNORECASE)
                if m:
                    price_str = m.group(1)

            # parse to float (aynı mantık)
            if price_str:
                cleaned = price_str.strip()
                cleaned = re.sub(r'[^\d\.,]', '', cleaned)
                if '.' in cleaned and ',' in cleaned:
                    if cleaned.rfind('.') > cleaned.rfind(','):
                        cleaned = cleaned.replace(',', '')
                    else:
                        cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    if ',' in cleaned and '.' not in cleaned:
                        frac = cleaned.split(',')[-1]
                        if len(frac) <= 2:
                            cleaned = cleaned.replace(',', '.')
                        else:
                            cleaned = cleaned.replace(',', '')
                try:
                    price = float(cleaned)
                except Exception:
                    price = None

            await context.close()
            await browser.close()
            return price, url
    except Exception as e:
        print("ERROR: amazon scrape error", e)
        return None, None

async def fetch_price(url):
    """
    Dispatcher: domain bazlı uygun fonksiyonu çağırır.
    """
    if not url:
        return None, None
    u = url.lower()
    if "hepsiburada" in u or "hb" in u:
        return await fetch_hepsiburada_price(url)
    if "trendyol" in u or "ty.gl" in u:
        return await fetch_trendyol_price(url)
    if "amazon" in u or "amzn.eu" in u:
        return await fetch_amazon_price(url)
    # fallback: default to hepsiburada parser attempt
    return await fetch_hepsiburada_price(url)
