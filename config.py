import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/delivery_db")
    ADMIN_TELEGRAM_IDS: list[int] = [123456789]  # আপনার টেলিগ্রাম আইডি বসাবেন

    # প্রাথমিক রেট সেটআপ
    DEFAULT_BASE_FARE: float = 50.0       # ৩ কিমি পর্যন্ত ৫০ টাকা
    DEFAULT_BASE_KM: float = 3.0          # বেস ডিস্ট্যান্স ৩ কিমি
    DEFAULT_EXTRA_PER_KM: float = 20.0    # পরবর্তী প্রতি কিমি ২০ টাকা
    DEFAULT_BROADCAST_PER_KM: float = 15.0# ব্রডকাস্টে ভেন্ডর রাইডারকে প্রতি কিমিতে দিবে ১৫ টাকা

settings = Settings()
