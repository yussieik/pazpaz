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
    - Min 32 chars: Ensures sufficient entropy (minimum 256 bits for URL-safe base64)
    - Max 128 chars: Prevents buffer overflow or DOS attacks via oversized tokens
    - 384-bit tokens: 48 bytes base64url encoded = 64 characters
    """

    token: str = Field(
        ...,
        description="Magic link token from email (384-bit entropy)",
        min_length=32,  # Minimum 256-bit tokens
        max_length=128,  # Maximum to accommodate 384-bit tokens (64 chars) + margin
        examples=[
            "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567890ABCD"
        ],  # 64 char example for 384-bit token
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
    is_platform_admin: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LogoutResponse(BaseModel):
    """Response schema for logout."""

    message: str = Field(
        default="Logged out successfully", description="Success message"
    )


# TOTP/2FA Schemas


class TOTPEnrollResponse(BaseModel):
    """Response for TOTP enrollment."""

    secret: str = Field(
        ..., description="Base32-encoded TOTP secret (store securely in authenticator)"
    )
    qr_code: str = Field(
        ..., description="Data URI with QR code image (scan with authenticator app)"
    )
    backup_codes: list[str] = Field(
        ...,
        description="One-time backup codes (save offline, shown only once)",
        examples=[["A1B2C3D4", "E5F6G7H8", "I9J0K1L2"]],
    )


class TOTPVerifyRequest(BaseModel):
    """Request to verify TOTP code during enrollment."""

    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit TOTP code from authenticator app",
        examples=["123456"],
    )


class TOTPVerifyResponse(BaseModel):
    """Response for TOTP verification."""

    success: bool = Field(..., description="Whether verification succeeded")
    message: str = Field(..., description="Success or error message")


class MagicLink2FARequest(BaseModel):
    """Request to complete authentication with 2FA after magic link."""

    temp_token: str = Field(
        ...,
        description="Temporary token from magic link verification",
        min_length=32,
        max_length=128,
    )
    totp_code: str = Field(
        ...,
        min_length=6,
        max_length=8,
        description="6-digit TOTP code or 8-character backup code",
        examples=["123456", "A1B2C3D4"],
    )


class MagicLink2FAResponse(BaseModel):
    """Response for 2FA verification after magic link."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user: UserInToken = Field(..., description="Authenticated user information")


class TOTPDisableRequest(BaseModel):
    """Request to disable TOTP (requires verification)."""

    totp_code: str = Field(
        ...,
        min_length=6,
        max_length=8,
        description="Current 6-digit TOTP code or 8-character backup code",
        examples=["123456", "A1B2C3D4"],
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"totp_code": "123456"}}
    )
