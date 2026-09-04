import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/delivery_db")
    
    # Render-এর String মান নিরাপদে প্রসেস করার জন্য
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

    class Config:
        extra = "ignore"

settings = Settings()
