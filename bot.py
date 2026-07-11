import os
import sys
import html
import time
import requests

from supabase_helper import get_client

# ==========================
# قراءة المفاتيح السرية من البيئة (GitHub Secrets)
# ==========================
CMC_API_KEY = os.environ.get("CMC_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")  # يُستخدم كإشعار احتياطي لك فقط عند الأخطاء

CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def validate_env_vars():
    """التأكد من وجود جميع المفاتيح السرية المطلوبة قبل بدء التنفيذ."""
    missing = []
    if not CMC_API_KEY:
        missing.append("CMC_API_KEY")
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
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


def get_all_subscribers(supabase):
    """جلب قائمة chat_id لكل المستخدمين المسجلين في قاعدة البيانات."""
    res = supabase.table("bot_users").select("chat_id").execute()
    return [row["chat_id"] for row in res.data]


def send_telegram_message(chat_id, text):
    """إرسال الرسالة إلى محادثة تليجرام محددة."""
    url = TELEGRAM_API_URL.format(token=TELEGRAM_TOKEN)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    response = requests.post(url, data=payload, timeout=30)
    return response


def remove_user(supabase, chat_id):
    """حذف مستخدم من قاعدة البيانات (عند اكتشاف أنه حظر البوت أو غادره)."""
    supabase.table("bot_users").delete().eq("chat_id", chat_id).execute()


def broadcast_message(supabase, subscribers, text):
    """إرسال الرسالة لكل المشتركين، مع حذف من حظر البوت تلقائيًا من القائمة."""
    sent = 0
    failed = 0
    removed = 0
    for chat_id in subscribers:
        try:
            response = send_telegram_message(chat_id, text)
            if response.status_code == 200:
                sent += 1
            elif response.status_code == 403:
                # المستخدم حظر البوت أو غادره: يُحذف من قاعدة البيانات مباشرة
                remove_user(supabase, chat_id)
                removed += 1
            else:
                failed += 1
                print(f"فشل الإرسال إلى {chat_id}: {response.text}")
            time.sleep(0.05)  # تجنب تجاوز حدود Telegram لعدد الرسائل في الثانية
        except requests.exceptions.RequestException as e:
            failed += 1
            print(f"خطأ أثناء الإرسال إلى {chat_id}: {e}")
    return sent, failed, removed


def main():
    validate_env_vars()

    try:
        supabase = get_client()
    except RuntimeError as e:
        print(f"خطأ في الاتصال بـ Supabase: {e}")
        sys.exit(1)

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

    subscribers = get_all_subscribers(supabase)

    if not subscribers:
        print("لا يوجد مشتركون مسجلون بعد.")
        return

    sent, failed, removed = broadcast_message(supabase, subscribers, message)
    print(
        f"تم الإرسال إلى {sent} مستخدم، "
        f"فشل الإرسال إلى {failed} مستخدم، "
        f"تم حذف {removed} مستخدم غادر/حظر البوت."
    )


if __name__ == "__main__":
    main()
