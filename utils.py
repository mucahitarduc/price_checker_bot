# utils.py
import re
import urllib.parse

def normalize_price(text):
    """
    Gelen metindeki rakamları alıp float döndürür.
    Örn: "1.234,56 TL" -> 1234.56
    """
    if text is None:
        return None
    # remove non-digit except comma and dot
    text = text.strip()
    # Hepsiburada genelde "1.234,56" formatında olabilir.
    # Remove currency letters:
    text = re.sub(r"[^\d,\.]", "", text)
    if not text:
        return None
    # If comma is decimal separator (common in TR), handle it
    # Heuristic: if there's both '.' and ',' and ',' after '.', treat '.' as thousand sep
    if "." in text and "," in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        # if only '.' present and more than one digit after dot => assume decimal
        if "," in text and "." not in text:
            text = text.replace(",", ".")
    try:
        return float(text)
    except:
        # fallback to extracting digits
        digits = re.findall(r"[\d]+", text)
        if digits:
            return float("".join(digits))
    return None

def domain_from_url(url):
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lower()
    except:
        return None
