"""SQLAlchemy 2.x declarative models for packs, tools, requests, and memory events."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from core.db.base import Base


TOOL_TYPE_VALUES = ("mcp", "cli", "http", "skill")
"""Peer categories per blueprint-v2 §Five Core Capabilities item #1.

Shared by Tool.tool_type and by ingest parsers so the constrained set
is declared once. Adding a new category requires a schema migration
that updates the Enum's CHECK constraint.
"""


class Pack(Base):
    __tablename__ = "packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transport: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    tools: Mapped[list["Tool"]] = relationship(
        back_populates="pack", cascade="all, delete-orphan"
    )


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pack_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("packs.id"), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_type: Mapped[Optional[str]] = mapped_column(
        Enum(*TOOL_TYPE_VALUES, name="tool_type"),
        nullable=True,
        index=True,
    )
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    install_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_in_manifest: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    pack: Mapped[Optional[Pack]] = relationship(back_populates="tools")


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    folder: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    tool_name: Mapped[str] = mapped_column(String(256))
    tool_slug: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    is_discovered: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_markdown: Mapped[str] = mapped_column(Text)
    parsed_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class MemoryEvent(Base):
    __tablename__ = "memory_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
