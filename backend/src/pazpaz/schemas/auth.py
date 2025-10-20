"""Pydantic schemas for authentication API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MagicLinkRequest(BaseModel):
    """Request schema for magic link generation."""

    email: EmailStr = Field(..., description="Email address to send magic link to")


class MagicLinkResponse(BaseModel):
    """Response schema for magic link request."""

    message: str = Field(
        default="If an account exists with this email, a login link has been sent.",
        description="Success message (generic to prevent email enumeration)",
    )


class TokenVerifyRequest(BaseModel):
    """Request schema for magic link token verification.

    Security: Token length validation prevents malformed or suspicious tokens.
    - Min 32 chars: Ensures sufficient entropy (256 bits for URL-safe base64)
    - Max 128 chars: Prevents buffer overflow or DOS attacks via oversized tokens
    """

    token: str = Field(
        ...,
        description="Magic link token from email",
        min_length=32,
        max_length=128,
        examples=["abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"],
    )


class TokenVerifyResponse(BaseModel):
    """Response schema for token verification."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user: UserInToken = Field(..., description="Authenticated user information")


class UserInToken(BaseModel):
    """User information included in token response."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LogoutResponse(BaseModel):
    """Response schema for logout."""

    message: str = Field(
        default="Logged out successfully", description="Success message"
    )
