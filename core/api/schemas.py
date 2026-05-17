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
    tool_type: Optional[str] = None
    category: Optional[str] = None
    install_method: Optional[str] = None
    is_in_manifest: bool
    lifecycle_state: str
    # Operator-pin authority class (D77). NOT-NULL on the model —
    # every row carries it (`auto-managed` default); not Optional.
    pin_status: str
    path: Optional[str] = None
    ambient_loading: Optional[bool] = None
    # Catalog metadata extension (Stage 1A items 4+7). Surfaced on the
    # API at item 1b so `concierge list-active` can render the use-case
    # / limitation / ownership / transport prose the ingest populated.
    # All Optional — NULL for rows predating the ingest.
    agent_owner: Optional[str] = None
    best_for: Optional[str] = None
    limitation: Optional[str] = None
    prefix: Optional[str] = None
    transport: Optional[str] = None
    auth: Optional[str] = None
    succeeded_by: Optional[str] = None
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
