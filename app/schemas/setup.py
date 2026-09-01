"""
Schemas for the first-run setup flow.

Only meaningful on a Bud instance that has never had a user: the endpoints
behind these schemas refuse to do anything once an account exists.
"""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.passwords import validate_password_strength

PasswordStr = Annotated[str, AfterValidator(validate_password_strength)]


class SetupStatusResponse(BaseModel):
    """Whether this instance still needs its first administrator."""

    setup_required: bool


class CreateFirstAdminRequest(BaseModel):
    email: EmailStr
    password: PasswordStr
    full_name: str = Field(min_length=1, max_length=255)
