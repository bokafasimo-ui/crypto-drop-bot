import os
import sys
import requests

from supabase_helper import get_client

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")  # رقمك الشخصي، لاستخدامه في أمر /stats
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def get_last_update_id(supabase):
    """قراءة آخر update_id تمت معالجته، حتى لا نعالج نفس الرسائل مرتين."""
    res = supabase.table("bot_state").select("value").eq("key", "last_update_id").execute()
    if res.data:
        return int(res.data[0]["value"])
    return 0


def set_last_update_id(supabase, update_id):
    supabase.table("bot_state").upsert({"key": "last_update_id", "value": str(update_id)}).execute()


def save_user(supabase, chat_id, username, first_name):
    """حفظ مستخدم جديد أو تحديث بياناته إن كان موجودًا مسبقًا."""
    supabase.table("bot_users").upsert({
        "chat_id": chat_id,
        "username": username,
        "first_name": first_name,
    }).execute()


def remove_user(supabase, chat_id):
    """حذف مستخدم من قاعدة البيانات (عند حظر البوت أو مغادرته)."""
    supabase.table("bot_users").delete().eq("chat_id", chat_id).execute()


def count_users(supabase):
    res = supabase.table("bot_users").select("chat_id", count="exact").execute()
    return res.count if res.count is not None else len(res.data)


def send_message(chat_id, text):
    requests.post(
        f"{API_URL}/sendMessage",
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=30,
    )


def handle_start(supabase, chat, chat_id):
    username = chat.get("username")
    first_name = chat.get("first_name")
    save_user(supabase, chat_id, username, first_name)
    send_message(
        chat_id,
        "أهلاً بك 👋\nستصلك تلقائيًا كل نصف ساعة قائمة بأكثر 5 عملات تعرضت لهبوط خلال آخر 24 ساعة."
    )


def handle_stats(supabase, chat_id):
    """أمر خاص بك فقط كمطوّر، يعرض عدد المستخدمين الكلي."""
    if ADMIN_CHAT_ID and str(chat_id) == str(ADMIN_CHAT_ID):
        total = count_users(supabase)
        send_message(chat_id, f"📊 عدد المستخدمين الحاليين: <b>{total}</b>")


def main():
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN مفقود")
        sys.exit(1)

    supabase = get_client()
    last_id = get_last_update_id(supabase)

    resp = requests.get(
        f"{API_URL}/getUpdates",
        params={
            "offset": last_id + 1,
            "timeout": 0,
            "allowed_updates": '["message", "my_chat_member"]',
        },
        timeout=30,
    )
    resp.raise_for_status()
    updates = resp.json().get("result", [])

    max_id = last_id
    new_users = 0
    removed_users = 0

    for update in updates:
        update_id = update["update_id"]
        max_id = max(max_id, update_id)

        # حالة: المستخدم حظر البوت أو أوقفه أو غادره
        member_update = update.get("my_chat_member")
        if member_update:
            chat_id = member_update.get("chat", {}).get("id")
            new_status = member_update.get("new_chat_member", {}).get("status")
            if chat_id and new_status in ("kicked", "left"):
                remove_user(supabase, chat_id)
                removed_users += 1
            continue

        message = update.get("message")
        if not message:
            continue

        text = message.get("text", "") or ""
        chat = message.get("chat", {})
        chat_id = chat.get("id")

        if not chat_id:
            continue

        if text.startswith("/start"):
            handle_start(supabase, chat, chat_id)
            new_users += 1
        elif text.startswith("/stats"):
            handle_stats(supabase, chat_id)

    if max_id > last_id:
        set_last_update_id(supabase, max_id)

    print(
        f"تم فحص {len(updates)} تحديث، "
        f"مستخدمين جدد: {new_users}، مستخدمين غادروا: {removed_users}"
    )


if __name__ == "__main__":
    main()
