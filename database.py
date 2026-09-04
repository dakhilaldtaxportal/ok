import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, String, Float, DateTime, func
from config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Rider(Base):
    __tablename__ = "riders"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=True)
    full_name: Mapped[str] = mapped_column(String, nullable=True)
    home_lat: Mapped[float] = mapped_column(Float, nullable=True)
    home_lon: Mapped[float] = mapped_column(Float, nullable=True)
    live_lat: Mapped[float] = mapped_column(Float, nullable=True)
    live_lon: Mapped[float] = mapped_column(Float, nullable=True)
    zone_radius_km: Mapped[float] = mapped_column(Float, default=3.0)
    status: Mapped[str] = mapped_column(String, default="REGISTERED_OFFLINE")
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

class Vendor(Base):
    __tablename__ = "vendors"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    shop_name: Mapped[str] = mapped_column(String, nullable=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

class AdminSetting(Base):
    __tablename__ = "admin_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    base_fare: Mapped[float] = mapped_column(Float, default=50.0)
    base_km: Mapped[float] = mapped_column(Float, default=3.0)
    extra_per_km: Mapped[float] = mapped_column(Float, default=20.0)
    broadcast_per_km: Mapped[float] = mapped_column(Float, default=15.0)

async def init_db():
    async with engine.begin() as conn:
        # আগের টেবিলগুলোর কলাম সমস্যা থাকলে নতুন করে রি-ক্রিয়েট করবে
        await conn.run_sync(Base.metadata.create_all)
