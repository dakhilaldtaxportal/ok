from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select
from database import AsyncSessionLocal, Rider

router = Router()

class RiderRegistration(StatesGroup):
    waiting_for_contact = State()
    waiting_for_name = State()
    waiting_for_home_location = State()

class ChangeAddress(StatesGroup):
    waiting_for_new_location = State()

class ZoneSetup(StatesGroup):
    waiting_for_zone_radius = State()

@router.message(Command("registration_for_rider"))
async def start_rider_registration(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Share Phone Number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("রাইডার রেজিস্ট্রেশনের জন্য নিচে আপনার ফোন নম্বর শেয়ার করুন:", reply_markup=kb)
    await state.set_state(RiderRegistration.waiting_for_contact)

@router.message(RiderRegistration.waiting_for_contact, F.contact)
async def process_rider_contact(message: Message, state: FSMContext):
    await state.update_data(phone_number=message.contact.phone_number)
    await message.answer("ধন্যবাদ! এখন আপনার পুরো নাম লিখুন:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(RiderRegistration.waiting_for_name)

@router.message(RiderRegistration.waiting_for_name)
async def process_rider_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Share Home Location", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("এখন আপনার স্থায়ী হোম লোকেশন শেয়ার করুন:", reply_markup=kb)
    await state.set_state(RiderRegistration.waiting_for_home_location)

@router.message(RiderRegistration.waiting_for_home_location, F.location)
async def process_rider_home_location(message: Message, state: FSMContext):
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        rider = Rider(
            telegram_id=message.from_user.id,
            phone_number=data["phone_number"],
            full_name=data["full_name"],
            home_lat=message.location.latitude,
            home_lon=message.location.longitude,
            status="REGISTERED_OFFLINE"
        )
        session.add(rider)
        await session.commit()
        
    await message.answer("🎉 রেজিস্ট্রেশন সফল হয়েছে! কাজ শুরু করতে `/go_online` কমান্ড দিন।", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.clear()

@router.message(Command("change_home_address"))
async def change_home_address_start(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Share New Home Location", request_location=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.answer("আপনার নতুন হোম লোকেশন পাঠালুন:", reply_markup=kb)
    await state.set_state(ChangeAddress.waiting_for_new_location)

@router.message(ChangeAddress.waiting_for_new_location, F.location)
async def change_home_address_finish(message: Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        stmt = select(Rider).where(Rider.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        rider = res.scalar_one_or_none()
        if rider:
            rider.home_lat = message.location.latitude
            rider.home_lon = message.location.longitude
            await session.commit()
            await message.answer("✅ আপনার হোম এড্রেস সফলভাবে আপডেট করা হয়েছে।", reply_markup=ReplyKeyboardRemove())
        else:
            await message.answer("❌ আপনি নিবন্ধিত রাইডার নন।")
    await state.clear()

@router.message(Command("zone"))
async def set_zone_cmd(message: Message, state: FSMContext):
    await message.answer("হোম লোকেশন থেকে কত কিমি পর্যন্ত কাজ করতে চান? (১ থেকে ১০ এর মধ্যে সংখ্যা লিখুন):")
    await state.set_state(ZoneSetup.waiting_for_zone_radius)

@router.message(ZoneSetup.waiting_for_zone_radius)
async def process_zone_input(message: Message, state: FSMContext):
    try:
        val = float(message.text)
        if 1.0 <= val <= 10.0:
            async with AsyncSessionLocal() as session:
                stmt = select(Rider).where(Rider.telegram_id == message.from_user.id)
                res = await session.execute(stmt)
                rider = res.scalar_one_or_none()
                if rider:
                    rider.zone_radius_km = val
                    await session.commit()
                    await message.answer(f"✅ আপনার ডেলিভারি জোন {val} কিমি সেট করা হয়েছে।")
            await state.clear()
        else:
            await message.answer("১ থেকে ১০ এর মধ্যে সংখ্যা দিন।")
    except ValueError:
        await message.answer("সঠিক সংখ্যা প্রদান করুন।")

@router.message(Command("go_online"))
async def go_online_cmd(message: Message):
    await message.answer("🌐 অনলাইনে যেতে আপনার **Live Location** শেয়ার করুন (Location -> Share Live Location)।")

@router.message(Command("go_offline"))
async def go_offline_cmd(message: Message):
    async with AsyncSessionLocal() as session:
        stmt = select(Rider).where(Rider.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        rider = res.scalar_one_or_none()
        if rider:
            rider.status = "REGISTERED_OFFLINE"
            await session.commit()
            await message.answer("🔴 আপনি এখন অফলাইনে আছেন।")

@router.edited_message(F.location)
async def handle_live_location_stream(message: Message):
    # টেলিগ্রাম লাইভ লোকেশন আপডেট ব্যাকএন্ডে রিসিভ করা
    async with AsyncSessionLocal() as session:
        stmt = select(Rider).where(Rider.telegram_id == message.from_user.id)
        res = await session.execute(stmt)
        rider = res.scalar_one_or_none()
        if rider and rider.status != "SUSPENDED":
            rider.live_lat = message.location.latitude
            rider.live_lon = message.location.longitude
            if rider.status == "REGISTERED_OFFLINE":
                rider.status = "ONLINE_IDLE"
            await session.commit()
