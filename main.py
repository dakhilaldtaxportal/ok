import os
import asyncio
import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher
from config import settings
from database import init_db
from handlers import rider, vendor, admin

app = FastAPI()
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# হ্যান্ডলার রাউটারগুলো যুক্ত করা
dp.include_router(rider.router)
dp.include_router(vendor.router)
dp.include_router(admin.router)

@app.get("/health")
async def health_check():
    """Render sleep বন্ধ রাখার জন্য UptimeRobot পিং এন্ডপয়েন্ট"""
    return {"status": "healthy", "service": "Telegram Delivery Orchestrator"}

async def run_bot():
    await init_db()
    print("🤖 Bot engine started polling...")
    await dp.start_polling(bot)

async def main():
    # Render-এর দেওয়া ডায়নামিক PORT পড়া (Render পোর্ট না পাঠালে ডিফল্ট 8080 ধরবে)
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    
    # ওয়েব সার্ভার এবং বটের ইভেন্ট লুপ একত্রে চালনা
    await asyncio.gather(
        server.serve(),
        run_bot()
    )

if __name__ == "__main__":
    asyncio.run(main())
