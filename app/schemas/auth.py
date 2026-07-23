"""
Auth and user schemas.
"""

from datetime import datetime
from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.passwords import validate_password_strength
from app.models.user import UserRole

# Every place a user chooses a password shares this policy (>= 12 chars, within
# the hashing backend's safe byte limit) so the rules cannot drift per endpoint.
PasswordStr = Annotated[str, AfterValidator(validate_password_strength)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: PasswordStr
    role: UserRole = UserRole.viewer


class InviteCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    role: UserRole = UserRole.viewer


class InviteResponse(BaseModel):
    message: str
    user: "UserResponse"
    invite_link: str | None = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    invited_at: datetime | None = None
    last_invite_sent_at: datetime | None = None
    invite_accepted_at: datetime | None = None
    password_set_at: datetime | None = None
    email_verified_at: datetime | None = None
    pending_email: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PasswordChange(BaseModel):
    current_password: str
    new_password: PasswordStr


class InviteInfoResponse(BaseModel):
    email: EmailStr
    full_name: str
    valid: bool
    expired: bool


class AcceptInviteRequest(BaseModel):
    token: str
    password: PasswordStr


class AcceptInviteResponse(BaseModel):
    requires_email_verification: bool = True
    email: EmailStr
    message: str


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: PasswordStr


class EmailChangeRequest(BaseModel):
    current_password: str
    new_email: EmailStr


class ConfirmEmailChangeRequest(BaseModel):
    token: str


class GenericMessageResponse(BaseModel):
    message: str


UserResponse.model_rebuild()
InviteResponse.model_rebuild()
