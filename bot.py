import os
import sys
import html
import requests

# ==========================
# قراءة المفاتيح السرية من البيئة (GitHub Secrets)
# ==========================
CMC_API_KEY = os.environ.get("CMC_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def validate_env_vars():
    """التأكد من وجود جميع المفاتيح السرية المطلوبة قبل بدء التنفيذ."""
    missing = []
    if not CMC_API_KEY:
        missing.append("CMC_API_KEY")
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        print(f"متغيرات بيئة مفقودة: {', '.join(missing)}")
        sys.exit(1)


def fetch_top_1000_coins():
    """جلب بيانات أول 1000 عملة من CoinMarketCap."""
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": CMC_API_KEY,
    }
    params = {
        "start": "1",
        "limit": "1000",
        "convert": "USD",
    }
    response = requests.get(CMC_URL, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("data", [])


def get_top_losers(coins, top_n=5):
    """ترتيب العملات وجلب أعلى top_n عملة تعرضت لأكبر هبوط خلال 24 ساعة."""
    valid_coins = [
        c for c in coins
        if c.get("quote", {}).get("USD", {}).get("percent_change_24h") is not None
    ]
    sorted_coins = sorted(
        valid_coins,
        key=lambda c: c["quote"]["USD"]["percent_change_24h"]
    )
    return sorted_coins[:top_n]


def build_coin_market_url(slug):
    """
    بناء رابط صفحة الأسواق (Markets) الخاصة بالعملة على CoinMarketCap مباشرة.
    ملاحظة: هذا الرابط مؤقت (مباشر بدون إعلان) وسيُستبدل لاحقًا
    عند دمج منصة الإعلانات (سيتم تعديل هذه الدالة فقط دون المساس ببقية الكود).
    """
    return f"https://coinmarketcap.com/currencies/{slug}/#Markets"


def build_message(losers):
    """صياغة رسالة تليجرام منسقة تحتوي على العملات الخمس الأكثر هبوطًا."""
    lines = ["📉 <b>أكبر 5 عملات تعرضت لهبوط خلال آخر 24 ساعة</b>\n"]

    for coin in losers:
        name = html.escape(coin.get("name", ""))
        symbol = html.escape(coin.get("symbol", ""))
        slug = coin.get("slug", "")
        percent_change = coin["quote"]["USD"]["percent_change_24h"]

        market_link = build_coin_market_url(slug)

        lines.append(
            f"🔻 <b>{name}</b> ({symbol})\n"
            f"النسبة: <code>{percent_change:.2f}%</code>\n"
            f"🔗 <a href=\"{market_link}\">جدول الأسواق والمنصات</a>\n"
        )

    return "\n".join(lines)


def send_telegram_message(text):
    """إرسال الرسالة إلى قناة/محادثة تليجرام المحددة."""
    url = TELEGRAM_API_URL.format(token=TELEGRAM_TOKEN)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    response = requests.post(url, data=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def main():
    validate_env_vars()

    try:
        coins = fetch_top_1000_coins()
    except requests.exceptions.RequestException as e:
        print(f"خطأ أثناء جلب البيانات من CoinMarketCap: {e}")
        sys.exit(1)

    if not coins:
        print("لم يتم استلام أي بيانات من CoinMarketCap.")
        sys.exit(1)

    top_losers = get_top_losers(coins, top_n=5)

    if not top_losers:
        print("لم يتم العثور على عملات هابطة.")
        sys.exit(1)

    message = build_message(top_losers)

    try:
        send_telegram_message(message)
        print("تم إرسال الرسالة بنجاح.")
    except requests.exceptions.RequestException as e:
        print(f"خطأ أثناء إرسال الرسالة إلى تليجرام: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
# trigger
