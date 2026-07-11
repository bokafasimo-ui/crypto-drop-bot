import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


def get_client():
    """إنشاء عميل Supabase باستخدام المتغيرات السرية من البيئة."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL أو SUPABASE_KEY غير موجودة في متغيرات البيئة")
    return create_client(SUPABASE_URL, SUPABASE_KEY)
