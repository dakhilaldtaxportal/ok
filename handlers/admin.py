from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from database import AsyncSessionLocal, Vendor, Rider, SystemSettings
from config import settings

router = Router()

def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.ADMIN_TELEGRAM_IDS

@router.message(Command("add_vendor"))
async def add_vendor_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    # ফরম্যাট: /add_vendor telegram_id, business_name, phone, address, lat, lon
    try:
        raw_text = message.text.replace("/add_vendor", "").strip()
        parts = [p.strip() for p in raw_text.split(",")]
        tg_id, name, phone, addr, lat, lon = int(parts[0]), parts[1], parts[2], parts[3], float(parts[4]), float(parts[5])
        
        async with AsyncSessionLocal() as session:
            v = Vendor(telegram_id=tg_id, business_name=name, phone_number=phone, address=addr, lat=lat, lon=lon)
            session.add(v)
            await session.commit()
            await message.answer("✅ ভেন্ডর সফলভাবে এড করা হয়েছে।")
    except Exception as e:
        await message.answer("❌ ফরম্যাট সঠিক নয়। \nব্যবহার: `/add_vendor tg_id, Name, Phone, Address, Lat, Lon`", parse_mode="Markdown")

@router.message(Command("search_user"))
async def search_user_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    phone = message.text.replace("/search_user", "").strip()
    async with AsyncSessionLocal() as session:
        # রাইডার সার্চ
        r_stmt = select(Rider).where(Rider.phone_number == phone)
        rider = (await session.execute(r_stmt)).scalar_one_or_none()
        if rider:
            await message.answer(f"🏍️ **Rider Found:**\nName: {rider.full_name}\nPhone: {rider.phone_number}\nStatus: {rider.status}", parse_mode="Markdown")
            return
            
        # ভেন্ডর সার্চ
        v_stmt = select(Vendor).where(Vendor.phone_number == phone)
        vendor = (await session.execute(v_stmt)).scalar_one_or_none()
        if vendor:
            await message.answer(f"🏪 **Vendor Found:**\nName: {vendor.business_name}\nPhone: {vendor.phone_number}\nSuspended: {vendor.is_suspended}", parse_mode="Markdown")
            return
            
        await message.answer("❌ নম্বর দিয়ে কোনো ইউজার পাওয়া যায়নি।")

@router.message(Command("suspend"))
async def suspend_user_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    phone = message.text.replace("/suspend", "").strip()
    async with AsyncSessionLocal() as session:
        r_stmt = select(Rider).where(Rider.phone_number == phone)
        rider = (await session.execute(r_stmt)).scalar_one_or_none()
        if rider:
            rider.status = "SUSPENDED"
            await session.commit()
            await message.answer("🚫 রাইডার একাউন্ট সাসপেন্ড করা হয়েছে।")
            return
            
        v_stmt = select(Vendor).where(Vendor.phone_number == phone)
        vendor = (await session.execute(v_stmt)).scalar_one_or_none()
        if vendor:
            vendor.is_suspended = True
            await session.commit()
            await message.answer("🚫 ভেন্ডর একাউন্ট সাসপেন্ড করা হয়েছে।")

@router.message(Command("update_pricing"))
async def update_pricing_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    # Format: /update_pricing base_fare, base_km, extra_per_km, broadcast_per_km
    try:
        raw_text = message.text.replace("/update_pricing", "").strip()
        parts = [float(p.strip()) for p in raw_text.split(",")]
        async with AsyncSessionLocal() as session:
            stmt = select(SystemSettings).where(SystemSettings.id == 1)
            sys_s = (await session.execute(stmt)).scalar_one_or_none()
            if not sys_s:
                sys_s = SystemSettings(id=1)
                session.add(sys_s)
            
            sys_s.base_fare = parts[0]
            sys_s.base_km = parts[1]
            sys_s.extra_per_km = parts[2]
            sys_s.broadcast_per_km = parts[3]
            await session.commit()
            await message.answer("✅ প্রাইসিং সফলভাবে আপডেট করা হয়েছে।")
    except Exception:
        await message.answer("❌ উদাহরণ: `/update_pricing 50, 3, 20, 15`", parse_mode="Markdown")
