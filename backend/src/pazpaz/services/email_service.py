"""Email service for sending magic links and notifications."""

from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


async def send_magic_link_email(email: str, token: str) -> None:
    """
    Send magic link email to user.

    Sends email via SMTP (MailHog in development, production SMTP in prod).

    Args:
        email: Recipient email address
        token: Magic link token

    Raises:
        Exception: If email sending fails
    """
    # Construct magic link URL
    base_url = settings.frontend_url
    magic_link = f"{base_url}/auth/verify?token={token}"

    # Create email message
    message = EmailMessage()
    message["From"] = "PazPaz <noreply@pazpaz.app>"
    message["To"] = email
    message["Subject"] = "Your PazPaz Login Link"

    # Email body (plain text)
    message.set_content(f"""
Hello,

Click the link below to log in to PazPaz:

{magic_link}

This link will expire in 10 minutes.

If you didn't request this, you can safely ignore this email.

---
PazPaz - Practice Management for Independent Therapists
""")

    # Send via SMTP
    try:
        async with aiosmtplib.SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
        ) as smtp:
            # Authenticate if credentials provided (not needed for MailHog)
            if settings.smtp_user:
                await smtp.login(settings.smtp_user, settings.smtp_password)

            await smtp.send_message(message)

        logger.info(
            "magic_link_sent",
            email=email,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
        )

        # Also log to console in debug mode for convenience
        if settings.debug:
            print(f"\n{'=' * 80}")
            print(f"✅ Magic link email sent to: {email}")
            print("   Check MailHog: http://localhost:8025")
            print(f"   Direct link: {magic_link}")
            print(f"{'=' * 80}\n")

    except Exception as e:
        logger.error(
            "failed_to_send_email",
            email=email,
            error=str(e),
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            exc_info=True,
        )
        raise


async def send_welcome_email(email: str, full_name: str) -> None:
    """
    Send welcome email to new user.

    Args:
        email: Recipient email address
        full_name: User's full name
    """
    logger.info("welcome_email", email=email, full_name=full_name)
    # TODO: Implement welcome email
    pass
