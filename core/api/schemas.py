"""Pydantic response models for the catalog API."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ToolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    install_method: Optional[str] = None
    is_in_manifest: bool
    is_active: bool
    pack_id: Optional[int] = None
    pack_slug: Optional[str] = None
    pack_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ToolList(BaseModel):
    items: list[ToolOut]
    total: int


class PackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: Optional[str] = None
    transport: Optional[str] = None
    status: str
    tool_count: int
    created_at: datetime
    updated_at: datetime


class PackList(BaseModel):
    items: list[PackOut]
    total: int
