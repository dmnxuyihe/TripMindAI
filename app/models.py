"""SQLAlchemy ORM; PostgreSQL 与 SQLite 测试后端共用。"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = 'conversations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False, default='qwen-plus')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    messages: Mapped[list['ChatMessage']] = relationship(back_populates='conversation', cascade='all,delete-orphan', order_by='ChatMessage.id')


class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    conversation: Mapped[Conversation] = relationship(back_populates='messages')


class Attraction(Base):
    __tablename__ = 'attractions'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    city: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    province: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default='[]')
    description: Mapped[str] = mapped_column(Text, nullable=False, default='')
    duration_hours: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    photo_url: Mapped[str] = mapped_column(Text, nullable=False, default='')
    photo_credit: Mapped[str] = mapped_column(Text, nullable=False, default='')
    photo_source: Mapped[str] = mapped_column(Text, nullable=False, default='')


class Defect(Base):
    __tablename__ = 'defects'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    steps: Mapped[str] = mapped_column(Text, nullable=False)
    expected: Mapped[str] = mapped_column(Text, nullable=False)
    actual: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default='minor')
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='open')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

Index('ix_conversations_updated', Conversation.updated_at)

class Itinerary(Base):
    """保存下来的行程，用于分享链接。"""
    __tablename__ = 'itineraries'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False, default='未命名行程')
    city: Mapped[str] = mapped_column(String(50), nullable=False, default='')
    days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class PoiCache(Base):
    """Isolated from teaching fixtures: real AMap points only."""
    __tablename__ = 'amap_poi_cache'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    city: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(70), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
