from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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

@router.message(Command("start"))
async def start_cmd(message: Message):
    welcome_text = (
        "👋 **ফুড ডেলিভারি প্ল্যাটফর্মে স্বাগতম!**\n\n"
        "আপনার ভূমিকা অনুযায়ী নিচের কমান্ডগুলো ব্যবহার করুন:\n\n"
        "🏍️ **রাইডার কমান্ড:**\n"
        "• `/registration_for_rider` - রেজিস্ট্রেশন করুন\n"
        "• `/go_online` - কাজ শুরু করতে অনলাইনে যান\n"
        "• `/go_offline` - অফলাইনে যান\n"
        "• `/zone` - ডেলিভারি জোন সেট করুন\n"
        "• `/change_home_address` - এড্রেস আপডেট করুন\n\n"
        "🏪 **ভেন্ডর কমান্ড:**\n"
        "• `/post_order` - ১ কিমি রেঞ্জে অর্ডার পোস্ট\n"
        "• `/broadcast` - ৫ কিমি রেঞ্জে ব্রডকাস্ট\n\n"
        "⚙️ **এডমিন কমান্ড:**\n"
        "• `/add_vendor` - ভেন্ডর যোগ করুন\n"
        "• `/search_user` - ইউজার খুঁজুন\n"
        "• `/suspend` - একাউন্ট বন্ধ করুন\n"
        "• `/update_pricing` - চার্জ আপডেট করুন"
    )
    await message.answer(welcome_text, parse_mode="Markdown")

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

# লোকেশন হ্যান্ডলিং আরও ফ্লেক্সিবল করা হয়েছে (বাটন ও নরমাল অ্যাটাচমেন্ট দুইটাই রিসিভ করবে)
@router.message(RiderRegistration.waiting_for_home_location, F.location)
async def process_rider_home_location(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    phone = data.get("phone_number", "N/A")
    name = data.get("full_name", "Unknown Rider")
    
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Rider).where(Rider.telegram_id == user_id)
            res = await session.execute(stmt)
            rider = res.scalar_one_or_none()

            if rider:
                # আগে থেকে আইডি থাকলে ডাটা আপডেট হবে
                rider.phone_number = phone
                rider.full_name = name
                rider.home_lat = float(message.location.latitude)
                rider.home_lon = float(message.location.longitude)
                rider.status = "REGISTERED_OFFLINE"
            else:
                # নতুন রাইডার তৈরি হবে
                new_rider = Rider(
                    telegram_id=user_id,
                    phone_number=phone,
                    full_name=name,
                    home_lat=float(message.location.latitude),
                    home_lon=float(message.location.longitude),
                    status="REGISTERED_OFFLINE"
                )
                session.add(new_rider)

            await session.commit()
            
        await message.answer("🎉 রেজিস্ট্রেশন সফল হয়েছে! কাজ শুরু করতে `/go_online` কমান্ড দিন।", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
        await state.clear()
        
    except Exception as e:
        print(f"Error saving rider: {e}")
        await message.answer("❌ ডেটা সেভ করার সময় এরর ঘটেছে। আবার `/registration_for_rider` চেষ্টা করুন।", reply_markup=ReplyKeyboardRemove())
        await state.clear()

# জেন্যারিক লোকেশন ট্র্যাপ (যদি FSM স্টেট কোনো কারণে রিসেট হয়ে যায়)
@router.message(F.location)
async def fallback_location(message: Message):
    await message.answer("⚠️ আপনি বর্তমানে রেজিস্ট্রেশন প্রসেসে নেই। আবার শুরু করতে `/registration_for_rider` চাপুন।")
