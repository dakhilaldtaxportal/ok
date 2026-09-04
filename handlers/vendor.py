import uuid
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select
from database import AsyncSessionLocal, Vendor, Rider, SystemSettings
from services.gmaps import extract_coordinates_from_gmaps
from services.osrm import get_osrm_road_distance, calculate_delivery_charge, haversine_distance
from services.dispatch import find_eligible_riders, dispatch_manager

router = Router()

# ইন-মেমোরি অ্যাক্টিভ অর্ডার ক্যাশ
active_orders_db = {}

class PostOrderState(StatesGroup):
    waiting_for_gmaps = State()

class BroadcastOrderState(StatesGroup):
    waiting_for_gmaps = State()

@router.message(Command("post_order"))
async def post_order_start(message: Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        stmt = select(Vendor).where(Vendor.telegram_id == message.from_user.id, Vendor.is_suspended == False)
        res = await session.execute(stmt)
        vendor = res.scalar_one_or_none()
        if not vendor:
            await message.answer("❌ আপনি অনুমোদিত ভেন্ডর নন অথবা আপনার অ্যাকাউন্ট সাসপেন্ড করা হয়েছে।")
            return
            
    await message.answer("কাস্টমারের Google Maps Pin Location Link পাঠান:")
    await state.set_state(PostOrderState.waiting_for_gmaps)

@router.message(PostOrderState.waiting_for_gmaps)
async def process_post_order(message: Message, state: FSMContext, bot: Bot):
    url = message.text
    coords = await extract_coordinates_from_gmaps(url)
    if not coords:
        await message.answer("❌ সঠিক গুগল ম্যাপস লিংক পাওয়া যায়নি। পুনরায় লিংক দিন:")
        return
        
    cust_lat, cust_lon = coords
    
    async with AsyncSessionLocal() as session:
        # ভেন্ডর ডাটা পড়া
        stmt_v = select(Vendor).where(Vendor.telegram_id == message.from_user.id)
        v_res = await session.execute(stmt_v)
        vendor = v_res.scalar_one_or_none()
        
        # সিস্টেম প্রাইসিং
        stmt_s = select(SystemSettings).where(SystemSettings.id == 1)
        s_res = await session.execute(stmt_s)
        sys_settings = s_res.scalar_one_or_none()
        base_fare = sys_settings.base_fare if sys_settings else 50.0
        base_km = sys_settings.base_km if sys_settings else 3.0
        extra_per_km = sys_settings.extra_per_km if sys_settings else 20.0
        
        # OSRM দিয়ে রাস্তা অনুযায়ী দূরত্ব বের করা
        road_km = await get_osrm_road_distance(vendor.lon, vendor.lat, cust_lon, cust_lat)
        delivery_charge = calculate_delivery_charge(road_km, base_fare, base_km, extra_per_km)
        
        # ১ কিমি রেঞ্জে রাইডার খোঁজা
        eligible_riders = await find_eligible_riders(session, vendor, cust_lat, cust_lon, max_vendor_distance_km=1.0)
        
        if not eligible_riders:
            await message.answer("❌ ১ কিমি রেঞ্জের ভেতরে কোনো রাইডার পাওয়া যায়নি। আপনি `/broadcast` কমান্ড ব্যবহার করতে পারেন।", parse_mode="Markdown")
            await state.clear()
            return
            
        order_id = str(uuid.uuid4())[:8]
        order_data = {
            "id": order_id,
            "vendor_telegram_id": vendor.telegram_id,
            "vendor_name": vendor.business_name,
            "vendor_phone": vendor.phone_number,
            "vendor_address": vendor.address,
            "vendor_lat": vendor.lat,
            "vendor_lon": vendor.lon,
            "cust_lat": cust_lat,
            "cust_lon": cust_lon,
            "cust_gmaps": url,
            "delivery_charge": delivery_charge,
            "is_broadcast": False
        }
        active_orders_db[order_id] = order_data
        
        await message.answer(f"✅ অর্ডার তৈরি হয়েছে!\n📏 দূরত্ব: {road_km:.2f} Km\n💰 কাস্টমার ডেলিভারি ফি: {delivery_charge} Tk\n🔍 ১ কিমি রেঞ্জে রাইডার খোঁজা হচ্ছে...")
        asyncio.create_task(dispatch_manager.offer_order_to_rider(bot, order_data, eligible_riders, 0))
        
    await state.clear()

@router.message(Command("broadcast"))
async def broadcast_order_start(message: Message, state: FSMContext):
    await message.answer("📢 [Broadcast Order] কাস্টমারের Google Maps Link দিন (৫ কিমি রেঞ্জে রাইডার খোঁজা হবে):")
    await state.set_state(BroadcastOrderState.waiting_for_gmaps)

@router.message(BroadcastOrderState.waiting_for_gmaps)
async def process_broadcast_order(message: Message, state: FSMContext, bot: Bot):
    url = message.text
    coords = await extract_coordinates_from_gmaps(url)
    if not coords:
        await message.answer("❌ সঠিক গুগল ম্যাপস লিংক পাওয়া যায়নি।")
        return
        
    cust_lat, cust_lon = coords
    
    async with AsyncSessionLocal() as session:
        stmt_v = select(Vendor).where(Vendor.telegram_id == message.from_user.id)
        vendor = (await session.execute(stmt_v)).scalar_one_or_none()
        
        stmt_s = select(SystemSettings).where(SystemSettings.id == 1)
        sys_settings = (await session.execute(stmt_s)).scalar_one_or_none()
        
        broadcast_rate = sys_settings.broadcast_per_km if sys_settings else 15.0
        
        road_km = await get_osrm_road_distance(vendor.lon, vendor.lat, cust_lon, cust_lat)
        delivery_charge = calculate_delivery_charge(road_km, sys_settings.base_fare, sys_settings.base_km, sys_settings.extra_per_km)
        
        # ৫ কিমি রেঞ্জে রাইডার খোঁজা
        eligible_riders = await find_eligible_riders(session, vendor, cust_lat, cust_lon, max_vendor_distance_km=5.0)
        
        if not eligible_riders:
            await message.answer("❌ ৫ কিমি ব্রডকাস্ট রেঞ্জেও কোনো রাইডার পাওয়া যায়নি।")
            await state.clear()
            return
            
        order_id = str(uuid.uuid4())[:8]
        # রাইডারের দূরত্ব অনুযায়ী ভেন্ডর থেকে রাইডারের সারচার্জ হিসাব
        first_rider = eligible_riders[0]
        v_to_r_dist = haversine_distance(vendor.lat, vendor.lon, first_rider.live_lat, first_rider.live_lon)
        broadcast_surcharge = round(v_to_r_dist * broadcast_rate, 2)
        
        order_data = {
            "id": order_id,
            "vendor_telegram_id": vendor.telegram_id,
            "vendor_name": vendor.business_name,
            "vendor_phone": vendor.phone_number,
            "vendor_address": vendor.address,
            "vendor_lat": vendor.lat,
            "vendor_lon": vendor.lon,
            "cust_lat": cust_lat,
            "cust_lon": cust_lon,
            "cust_gmaps": url,
            "delivery_charge": delivery_charge,
            "is_broadcast": True,
            "broadcast_surcharge": broadcast_surcharge
        }
        active_orders_db[order_id] = order_data
        
        await message.answer(f"📢 ব্রডকাস্ট অর্ডার পোস্ট হয়েছে!\n💵 অতিরিক্ত সারচার্জ (ভেন্ডর ফি): {broadcast_surcharge} Tk\n🔍 রাইডারদের কাছে পাঠানো হচ্ছে...")
        asyncio.create_task(dispatch_manager.offer_order_to_rider(bot, order_data, eligible_riders, 0))
        
    await state.clear()

@router.callback_query(F.data.startswith("accept_"))
async def accept_order_callback(call: CallbackQuery, bot: Bot):
    parts = call.data.split("_")
    order_id, rider_id = parts[1], int(parts[2])
    order = active_orders_db.get(order_id)
    
    if not order:
        await call.answer("অর্ডারটি পাওয়া যায়নি বা মেয়াদ শেষ হয়েছে।", show_alert=True)
        return
        
    async with AsyncSessionLocal() as session:
        stmt = select(Rider).where(Rider.id == rider_id)
        rider = (await session.execute(stmt)).scalar_one_or_none()
        
        if rider:
            rider.status = "IN_TRANSIENT" # রাইডারের একাউন্ট লক
            await session.commit()
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Complete", callback_data=f"complete_{order_id}_{rider.id}"),
                 InlineKeyboardButton(text="🔄 Release", callback_data=f"release_{order_id}_{rider.id}")]
            ])
            
            # রাইডারকে ডিটেইলস পাঠানো
            await bot.send_message(
                rider.telegram_id,
                f"🎉 **অর্ডার একসেপ্ট হয়েছে!**\n\n"
                f"🏪 ভেন্ডর নাম: {order['vendor_name']}\n"
                f"📞 ভেন্ডর নম্বর: {order['vendor_phone']}\n"
                f"📍 ভেন্ডর এড্রেস: {order['vendor_address']}\n"
                f"🗺️ কাস্টমার ম্যাপ লিংক: {order['cust_gmaps']}\n"
                f"💰 ডেলিভারি চার্জ: {order['delivery_charge']} Tk",
                reply_markup=kb,
                parse_mode="Markdown"
            )
            
            # ভেন্ডরকে কন্টাক্ট পাঠানো
            await bot.send_message(
                order["vendor_telegram_id"],
                f"✅ **রাইডার অর্ডার গ্রহণ করেছে!**\n\n"
                f"👤 রাইডার নাম: {rider.full_name}\n"
                f"📞 রাইডার নম্বর: {rider.phone_number}"
            )
            
            await call.message.delete()

@router.callback_query(F.data.startswith("complete_"))
async def complete_order_callback(call: CallbackQuery):
    parts = call.data.split("_")
    rider_id = int(parts[2])
    async with AsyncSessionLocal() as session:
        stmt = select(Rider).where(Rider.id == rider_id)
        rider = (await session.execute(stmt)).scalar_one_or_none()
        if rider:
            rider.status = "ONLINE_IDLE"
            await session.commit()
            await call.message.edit_text("🎉 ডেলিভারি সফলভাবে কমপ্লিট হয়েছে!")

@router.callback_query(F.data.startswith("release_"))
async def release_order_callback(call: CallbackQuery, bot: Bot):
    parts = call.data.split("_")
    order_id, rider_id = parts[1], int(parts[2])
    order = active_orders_db.get(order_id)
    
    async with AsyncSessionLocal() as session:
        stmt = select(Rider).where(Rider.id == rider_id)
        rider = (await session.execute(stmt)).scalar_one_or_none()
        if rider:
            rider.status = "ONLINE_IDLE"
            await session.commit()
            await call.message.edit_text("⚠️ আপনি অর্ডারটি রিলেজ করেছেন। এটি অন্য রাইডারের কাছে পাঠানো হচ্ছে...")
            
            # ভেন্ডরকে জানানো
            stmt_v = select(Vendor).where(Vendor.telegram_id == order["vendor_telegram_id"])
            vendor = (await session.execute(stmt_v)).scalar_one_or_none()
            eligible_riders = await find_eligible_riders(session, vendor, order["cust_lat"], order["cust_lon"])
            asyncio.create_task(dispatch_manager.offer_order_to_rider(bot, order, eligible_riders, 0))
