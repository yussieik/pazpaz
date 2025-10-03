"""Email service for sending magic links and notifications."""

from __future__ import annotations

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


async def send_magic_link_email(email: str, token: str) -> None:
    """
    Send magic link email to user.

    For development, this logs the magic link to the console.
    For production, this should use a real email service (SMTP, SendGrid, etc.).

    Args:
        email: Recipient email address
        token: Magic link token

    Note:
        In production, replace this with actual email sending logic.
        Consider using services like SendGrid, AWS SES, or Mailgun.
    """
    # Construct magic link URL
    base_url = settings.frontend_url
    magic_link = f"{base_url}/auth/verify?token={token}"

    # Development: Log to console
    if settings.debug:
        logger.info(
            "magic_link_generated",
            email=email,
            magic_link=magic_link,
            message="DEVELOPMENT MODE: Magic link logged to console",
        )
        print(f"\n{'=' * 80}")
        print(f"Magic Link for {email}:")
        print(f"{magic_link}")
        print(f"{'=' * 80}\n")
    else:
        # Production: Send actual email
        # TODO: Implement production email sending
        logger.warning(
            "email_not_sent",
            email=email,
            reason="Production email service not implemented yet",
        )

        # Placeholder for production implementation:
        # async with aiosmtplib.SMTP(
        #     hostname=settings.smtp_host,
        #     port=settings.smtp_port,
        # ) as smtp:
        #     if settings.smtp_user:
        #         await smtp.login(settings.smtp_user, settings.smtp_password)
        #
        #     message = EmailMessage()
        #     message["From"] = settings.emails_from_email
        #     message["To"] = email
        #     message["Subject"] = "Your PazPaz Login Link"
        #     message.set_content(f"""
        #         Click the link below to log in to PazPaz:
        #
        #         {magic_link}
        #
        #         This link will expire in 10 minutes.
        #
        #         If you didn't request this, you can safely ignore this email.
        #     """)
        #
        #     await smtp.send_message(message)
        #
        # logger.info("magic_link_sent", email=email)


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
