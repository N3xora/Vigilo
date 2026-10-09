"""Pydantic shape for an Account, returned by the repository — never the ORM
row itself, so callers outside this package never depend on SQLAlchemy.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class Account(BaseModel):
    id: uuid.UUID
    email: str
    status: str
    plan_id: str | None
    data_region: str | None
    clerk_user_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class Subscription(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    org_id: uuid.UUID
    product_slug: str
    billing_interval: str = "month"
    cancel_at_period_end: bool = False
    plan_id: str
    status: str
    provider: str
    provider_subscription_id: str
    current_period_end: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKey(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    org_id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BrandingProfile(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    logo_url: str | None
    primary_color: str | None
    footer_text: str | None
    custom_domain: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Organization(BaseModel):
    id: uuid.UUID
    clerk_org_id: str | None
    name: str
    slug: str
    is_personal: bool
    billing_customer_id: str | None = None
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class Membership(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    account_id: uuid.UUID
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberWithEmail(BaseModel):
    account_id: uuid.UUID
    email: str
    role: str


class ProductEnablement(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    product_slug: str
    status: str
    enabled_at: datetime

    model_config = {"from_attributes": True}


class UsageCounter(BaseModel):
    org_id: uuid.UUID
    product_slug: str
    meter: str
    period_start: date
    count: int

    model_config = {"from_attributes": True}


class OrgInvite(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
