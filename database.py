from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, BigInteger, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from datetime import datetime
from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    role = Column(String(20), default="customer")
    fullname = Column(String(100), nullable=True) # اضافه شد
    phone = Column(String(15), nullable=True)     # اضافه شد
    address = Column(Text, nullable=True)         # اضافه شد
    joined_at = Column(DateTime, default=datetime.utcnow)

class License(Base):
    __tablename__ = "licenses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), unique=True, index=True)
    duration_days = Column(Integer)
    is_used = Column(Boolean, default=False)
    activated_by = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    is_active = Column(Boolean, default=True)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    name = Column(String(100))
    photo_id = Column(String(200), nullable=True)
    price = Column(Integer)
    stock = Column(Integer)
    description = Column(Text, nullable=True)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    fullname = Column(String(100), nullable=True)
    address = Column(Text, nullable=True) # اضافه شد برای جلوگیری از گم شدن آدرس
    total_price = Column(Integer)
    status = Column(String(20), default="pending") 
    receipt_photo_id = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)