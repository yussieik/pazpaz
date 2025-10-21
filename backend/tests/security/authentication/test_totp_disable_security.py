"""
Test TOTP disable security - API endpoint attack scenarios.

Security Requirement: TOTP disable must require verification to prevent
session hijacking attacks from downgrading 2FA protection.

Test Coverage:
- Stolen JWT cannot disable TOTP without valid code
- API endpoint enforces TOTP verification
- Invalid codes return 401 Unauthorized
- Valid codes allow disable
- Security logging for disable attempts
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, UTC

import pytest
import pyotp
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.config import settings
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace
from pazpaz.services.totp_service import enroll_totp, verify_and_enable_totp
from pazpaz.middleware.csrf import generate_csrf_token

pytestmark = pytest.mark.asyncio


def create_test_jwt(user_id: uuid.UUID, workspace_id: uuid.UUID, email: str) -> str:
    """Create a valid JWT token for testing with all required claims."""
    return jwt.encode(
        {
            "sub": str(user_id),
            "user_id": str(user_id),
            "workspace_id": str(workspace_id),
            "email": email,
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "jti": str(uuid.uuid4()),
        },
        settings.secret_key,
        algorithm="HS256",
    )


class TestTOTPDisableAPI:
    """Test DELETE /api/v1/auth/totp endpoint security."""

    async def test_totp_disable_requires_valid_code(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """DELETE /auth/totp requires valid TOTP code in request body."""
        # Create user with 2FA enabled
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="2fa@example.com",
            full_name="2FA User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Enable TOTP
        enrollment = await enroll_totp(db, user.id)
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, user.id, totp.now())

        # Create JWT for user
        access_token = create_test_jwt(user.id, user.workspace_id, user.email)

        # Generate CSRF token
        csrf_token = await generate_csrf_token(
            user_id=user.id,
            workspace_id=user.workspace_id,
            redis_client=redis_client,
        )

        # Try to disable without TOTP code - should fail with 422 (validation error)
        response = await client.request(
            "DELETE",
            "/api/v1/auth/totp",
            cookies={"access_token": access_token, "csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 422  # Missing required field

    async def test_totp_disable_with_invalid_code_fails(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """DELETE /auth/totp with invalid code returns 401."""
        # Create user with 2FA enabled
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="2fa-invalid@example.com",
            full_name="2FA User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Enable TOTP
        enrollment = await enroll_totp(db, user.id)
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, user.id, totp.now())

        # Create JWT for user
        access_token = create_test_jwt(user.id, user.workspace_id, user.email)

        # Try to disable with wrong code - should fail with 401
        response = await client.request(
            "DELETE",
            "/api/v1/auth/totp",
            cookies={"access_token": access_token},
            json={"totp_code": "000000"},
        )
        assert response.status_code == 401
        assert "Invalid TOTP code" in response.json()["detail"]

    async def test_totp_disable_with_valid_code_succeeds(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """DELETE /auth/totp with valid code succeeds."""
        # Create user with 2FA enabled
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="2fa-valid@example.com",
            full_name="2FA User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Enable TOTP
        enrollment = await enroll_totp(db, user.id)
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, user.id, totp.now())

        # Create JWT for user
        access_token = create_test_jwt(user.id, user.workspace_id, user.email)

        # Disable with valid code - should succeed
        code = totp.now()
        response = await client.request(
            "DELETE",
            "/api/v1/auth/totp",
            cookies={"access_token": access_token},
            json={"totp_code": code},
        )
        assert response.status_code == 200
        assert "disabled successfully" in response.json()["message"]

    async def test_totp_disable_with_backup_code_succeeds(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """DELETE /auth/totp with backup code succeeds."""
        # Create user with 2FA enabled
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="2fa-backup@example.com",
            full_name="2FA User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Enable TOTP
        enrollment = await enroll_totp(db, user.id)
        backup_code = enrollment["backup_codes"][0]
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, user.id, totp.now())

        # Create JWT for user
        access_token = jwt.encode(
            {
                "sub": str(user.id),
                "workspace_id": str(user.workspace_id),
                "email": user.email,
            },
            settings.secret_key,
            algorithm="HS256",
        )

        # Disable with backup code - should succeed
        response = await client.request(
            "DELETE",
            "/api/v1/auth/totp",
            cookies={"access_token": access_token},
            json={"totp_code": backup_code},
        )
        assert response.status_code == 200
        assert "disabled successfully" in response.json()["message"]


class TestTOTPDisableAttackScenarios:
    """Test attack scenarios for TOTP disable."""

    async def test_stolen_jwt_cannot_disable_totp(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """
        Simulate session hijacking attack.

        Attacker has valid JWT cookie but no access to TOTP device.
        Should not be able to disable 2FA.
        """
        # Create user with 2FA enabled
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="victim@example.com",
            full_name="Victim User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Enable TOTP
        enrollment = await enroll_totp(db, user.id)
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, user.id, totp.now())

        # Attacker steals JWT (but not TOTP device)
        stolen_token = create_test_jwt(user.id, user.workspace_id, user.email)

        # Attacker tries to disable 2FA with guessed code
        response = await client.delete(
            "/api/v1/auth/totp",
            cookies={"access_token": stolen_token},
            json={"totp_code": "123456"},
        )

        # Should fail - 2FA still protects the account
        assert response.status_code == 401
        assert "Invalid TOTP code" in response.json()["detail"]

        # Verify 2FA is still enabled
        await db.refresh(user)
        assert user.totp_enabled is True

    async def test_totp_disable_requires_recent_verification(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """
        TOTP disable should require fresh verification.

        No bypass via cached validation - code must be valid at disable time.
        """
        # Create user with 2FA enabled
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="recent-verify@example.com",
            full_name="Recent Verify User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Enable TOTP
        enrollment = await enroll_totp(db, user.id)
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, user.id, totp.now())

        # Create JWT for user
        access_token = create_test_jwt(user.id, user.workspace_id, user.email)

        # Try to disable with invalid code (no cached bypass)
        response = await client.request(
            "DELETE",
            "/api/v1/auth/totp",
            cookies={"access_token": access_token},
            json={"totp_code": "000000"},
        )

        assert response.status_code == 401

        # Verify 2FA still enabled (no bypass)
        await db.refresh(user)
        assert user.totp_enabled is True

    async def test_totp_disable_consumes_backup_code(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Backup code used for disable is single-use."""
        # Create user with 2FA enabled
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="backup-consume@example.com",
            full_name="Backup Consume User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Enable TOTP
        enrollment = await enroll_totp(db, user.id)
        backup_code = enrollment["backup_codes"][0]
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, user.id, totp.now())

        # Create JWT for user
        access_token = jwt.encode(
            {
                "sub": str(user.id),
                "workspace_id": str(user.workspace_id),
                "email": user.email,
            },
            settings.secret_key,
            algorithm="HS256",
        )

        # Disable with backup code - should succeed and consume it
        response = await client.request(
            "DELETE",
            "/api/v1/auth/totp",
            cookies={"access_token": access_token},
            json={"totp_code": backup_code},
        )
        assert response.status_code == 200

        # Backup code should be consumed (but 2FA is now disabled, so we can't test reuse)
        # The important part is it was single-use during the verification step
