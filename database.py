from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional
import config

engine = create_async_engine(config.settings.DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Rider(Base):
    __tablename__ = "riders"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(unique=True, index=True)
    full_name: Mapped[str]
    home_lat: Mapped[float]
    home_lon: Mapped[float]
    live_lat: Mapped[Optional[float]] = mapped_column(nullable=True)
    live_lon: Mapped[Optional[float]] = mapped_column(nullable=True)
    zone_radius_km: Mapped[float] = mapped_column(default=5.0)
    status: Mapped[str] = mapped_column(default="REGISTERED_OFFLINE") # Statuses: REGISTERED_OFFLINE, ONLINE_IDLE, DISPATCH_PENDING, IN_TRANSIENT, SUSPENDED

class Vendor(Base):
    __tablename__ = "vendors"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    business_name: Mapped[str]
    phone_number: Mapped[str] = mapped_column(unique=True, index=True)
    address: Mapped[str]
    lat: Mapped[float]
    lon: Mapped[float]
    is_suspended: Mapped[bool] = mapped_column(default=False)

class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    base_fare: Mapped[float] = mapped_column(default=50.0)
    base_km: Mapped[float] = mapped_column(default=3.0)
    extra_per_km: Mapped[float] = mapped_column(default=20.0)
    broadcast_per_km: Mapped[float] = mapped_column(default=15.0)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
