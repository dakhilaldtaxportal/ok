import asyncio
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import Rider, Vendor, AsyncSessionLocal
from services.osrm import haversine_distance, get_osrm_road_distance, calculate_delivery_charge

async def find_eligible_riders(
    session: AsyncSession,
    vendor: Vendor,
    cust_lat: float,
    cust_lon: float,
    max_vendor_distance_km: float = 1.0
) -> List[Rider]:
    """
    ১. রাইডারের লাইভ লোকেশন ভেন্ডর থেকে max_vendor_distance_km (১কিমি বা ৫কিমি) এর মধ্যে হতে হবে।
    ২. ভেন্ডর এবং কাস্টমার উভয় লোকেশনই রাইডারের হোম লোকেশন থেকে রাইডারের সেট করা zone_radius_km এর মধ্যে হতে হবে।
    ৩. রাইডারের স্টেট ONLINE_IDLE হতে হবে।
    """
    stmt = select(Rider).where(Rider.status == "ONLINE_IDLE")
    result = await session.execute(stmt)
    active_riders = result.scalars().all()
    
    eligible_riders = []
    
    for rider in active_riders:
        if rider.live_lat is None or rider.live_lon is None:
            continue
            
        # ১. ভেন্ডর থেকে রাইডারের লাইভ লোকেশনের দূরত্ব
        dist_vendor_to_rider = haversine_distance(
            vendor.lat, vendor.lon, rider.live_lat, rider.live_lon
        )
        if dist_vendor_to_rider > max_vendor_distance_km:
            continue
            
        # ২. রাইডারের হোম লোকেশন থেকে ভেন্ডরের দূরত্ব
        dist_home_to_vendor = haversine_distance(
            rider.home_lat, rider.home_lon, vendor.lat, vendor.lon
        )
        # ৩. রাইডারের হোম লোকেশন থেকে কাস্টমারের দূরত্ব
        dist_home_to_cust = haversine_distance(
            rider.home_lat, rider.home_lon, cust_lat, cust_lon
        )
        
        # উভটাই রাইডারের জোন রেডিয়াসের মধ্যে থাকতে হবে
        if dist_home_to_vendor <= rider.zone_radius_km and dist_home_to_cust <= rider.zone_radius_km:
            eligible_riders.append(rider)
            
    return eligible_riders

class OrderDispatchManager:
    def __init__(self):
        self.active_dispatches = {} # order_id: task

    async def offer_order_to_rider(
        self, bot, order_data: dict, eligible_riders: List[Rider], current_index: int = 0
    ):
        if current_index >= len(eligible_riders):
            # কোনো রাইডার অর্ডার একসেপ্ট করেনি
            await bot.send_message(
                order_data["vendor_telegram_id"],
                "❌ দুঃখিত, ১ মিনিটের মধ্যে কোনো রাইডার অর্ডারটি গ্রহণ করেনি বা কোনো রাইডার উপলব্ধ নেই।"
            )
            return

        current_rider = eligible_riders[current_index]
        
        # রাইডারের স্ট্যাটাস লক করা
        async with AsyncSessionLocal() as session:
            stmt = select(Rider).where(Rider.id == current_rider.id)
            res = await session.execute(stmt)
            r = res.scalar_one_or_none()
            if r and r.status == "ONLINE_IDLE":
                r.status = "DISPATCH_PENDING"
                await session.commit()
            else:
                # রাইডার অনুপলব্ধ হলে পরবর্তী রাইডারে স্কিপ
                await self.offer_order_to_rider(bot, order_data, eligible_riders, current_index + 1)
                return

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Accept (1 min)", callback_data=f"accept_{order_data['id']}_{current_rider.id}_{current_index}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{order_data['id']}_{current_rider.id}_{current_index}")
            ]
        ])

        msg_text = (
            f"🔔 **নতুন ডেলিভারি অর্ডার!**\n\n"
            f"🏪 ভেন্ডর: {order_data['vendor_name']}\n"
            f"📍 ভেন্ডর ঠিকানা: {order_data['vendor_address']}\n"
            f"💰 কাস্টমার ডেলিভারি চার্জ: {order_data['delivery_charge']} Tk\n"
        )
        if order_data.get("is_broadcast"):
            msg_text += f"🎁 **ব্রডকাস্ট বোনাস (ভেন্ডর পে করবে):** {order_data.get('broadcast_surcharge', 0)} Tk\n"

        msg = await bot.send_message(current_rider.telegram_id, msg_text, reply_markup=kb, parse_mode="Markdown")
        
        # ৬০ সেকেন্ডের কাউন্টডাউন টাইমার
        await asyncio.sleep(60)
        
        # ৬০ সেকেন্ড পর চেক করা একসেপ্ট হয়েছে কিনা
        async with AsyncSessionLocal() as session:
            stmt = select(Rider).where(Rider.id == current_rider.id)
            res = await session.execute(stmt)
            r = res.scalar_one_or_none()
            if r and r.status == "DISPATCH_PENDING":
                r.status = "ONLINE_IDLE" # স্ট্যাটাস রিলিজ
                await session.commit()
                
                try:
                    await bot.edit_message_text("⏰ সময়ের মধ্যে একসেপ্ট না করায় অর্ডারটি হাতছাড়া হয়েছে।", chat_id=current_rider.telegram_id, message_id=msg.message_id)
                except Exception:
                    pass
                
                # পরবর্তী রাইডারের কাছে অর্ডার পাঠানো
                await self.offer_order_to_rider(bot, order_data, eligible_riders, current_index + 1)

dispatch_manager = OrderDispatchManager()
