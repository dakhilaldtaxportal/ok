import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
    
    # ডাটাবেস URL প্রসেসিং (postgres:// বা postgresql:// কে অটোমেটিক asyncpg তে কনভার্ট করবে)
    @property
    def DATABASE_URL(self) -> str:
        raw_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/delivery_db")
        if raw_url.startswith("postgres://"):
            return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+asyncpg://"):
            return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return raw_url

    # Render-এর Environment Variable থেকে Admin ID পড়ার নিরাপদ ব্যবস্থা
    ADMIN_TELEGRAM_IDS_RAW: str = os.getenv("ADMIN_TELEGRAM_IDS", "123456789")

    @property
    def ADMIN_TELEGRAM_IDS(self) -> list[int]:
        raw = os.getenv("ADMIN_TELEGRAM_IDS", self.ADMIN_TELEGRAM_IDS_RAW)
        result = []
        for item in raw.replace("[", "").replace("]", "").split(","):
            item = item.strip()
            if item.isdigit():
                result.append(int(item))
        return result

    # প্রাথমিক ডেলিভারি চার্জ সেটিং
    DEFAULT_BASE_FARE: float = 50.0
    DEFAULT_BASE_KM: float = 3.0
    DEFAULT_EXTRA_PER_KM: float = 20.0
    DEFAULT_BROADCAST_PER_KM: float = 15.0

    class Config:
        extra = "ignore"

settings = Settings()
