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


class SetupCompletedResponse(BaseModel):
    """Returned once, to the browser that just created the administrator.

    ``runner_api_key`` is the shared runner-registration secret. On a packaged
    deployment it is generated at first boot and written to a file the operator
    has no way to read, so this response is their only chance to capture it. It
    is never returned again, never written to a log, and never sent by mail.
    """

    message: str
    runner_api_key: str | None = None
