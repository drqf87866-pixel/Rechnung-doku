from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: Optional[int] = None
    filename: str
    bauvorhaben: str
    rechnungsnummer: Optional[str]
    rechnungsbetrag: Optional[float]
    nettobetrag: Optional[float] = None
    steuerbetrag: Optional[float] = None
    waehrung: str
    konfidenz: Optional[float]
    hinweise: Optional[str]
    upload_time: datetime


class InvoicePatch(BaseModel):
    rechnungsnummer: Optional[str] = None
    rechnungsbetrag: Optional[float] = None
    nettobetrag: Optional[float] = None
    steuerbetrag: Optional[float] = None
    bauvorhaben: Optional[str] = None


class UserDirectoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str


class ShareCreate(BaseModel):
    bauvorhaben: str = Field(min_length=1, max_length=255)
    user_id: int


class ShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bauvorhaben: str
    owner_id: int
    owner_username: str
    owner_display_name: str
    shared_with_user_id: int
    shared_with_username: str
    shared_with_display_name: str
    created_at: datetime


class BauvorhabenInfo(BaseModel):
    name: str
    is_shared: bool = False
    can_manage_shares: bool = False


Role = Literal["admin", "user"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: Role
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: Role = "user"


class UserPatch(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class SetupAdmin(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(default="Administrator", min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SetupStatus(BaseModel):
    needs_setup: bool
