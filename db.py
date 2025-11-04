# db.py
import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    url = Column(Text, unique=True, nullable=False)
    title = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_checked_at = Column(DateTime, nullable=True)

class PriceLog(Base):
    __tablename__ = "price_logs"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    price = Column(Float, nullable=False)
    currency = Column(String, nullable=True)
    checked_at = Column(DateTime, default=datetime.datetime.utcnow)

    product = relationship("Product")

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    active = Column(Boolean, default=True)
    target_price = Column(Float, nullable=True)  # optional alert threshold

    user = relationship("User")
    product = relationship("Product")


def init_db(db_url="sqlite:///./prices.db"):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

# session_factory = init_db()  # çağıran modülde oluştur
