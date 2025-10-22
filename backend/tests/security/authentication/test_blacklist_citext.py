"""Test CITEXT case-insensitive behavior in email blacklist."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from pazpaz.core.blacklist import is_email_blacklisted
from pazpaz.models.email_blacklist import EmailBlacklist


@pytest.mark.asyncio
class TestBlacklistCITEXT:
    """Test that email column uses CITEXT for case-insensitive comparisons."""

    async def test_citext_extension_enabled(self, db):
        """Verify CITEXT extension is enabled."""
        result = await db.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'citext'")
        )
        assert result.scalar() == 1, "CITEXT extension not enabled"

    async def test_email_column_is_citext(self, db):
        """Verify email_blacklist.email column uses CITEXT type."""
        result = await db.execute(
            text("""
            SELECT t.typname
            FROM pg_attribute a
            JOIN pg_type t ON a.atttypid = t.oid
            WHERE a.attrelid = 'email_blacklist'::regclass
            AND a.attname = 'email'
        """)
        )
        data_type = result.scalar()
        assert data_type == "citext", f"Expected citext, got {data_type}"

    async def test_case_insensitive_insert_prevention(self, db, test_user):
        """Database should prevent duplicate emails with different cases."""
        # Insert lowercase
        entry1 = EmailBlacklist(
            email="duplicate@example.com", reason="Test", added_by=test_user.id
        )
        db.add(entry1)
        await db.commit()

        # Try to insert uppercase (should fail due to unique constraint)
        entry2 = EmailBlacklist(
            email="DUPLICATE@EXAMPLE.COM",
            reason="Test duplicate",
            added_by=test_user.id,
        )
        db.add(entry2)

        with pytest.raises(
            IntegrityError, match="duplicate key.*email_blacklist_email"
        ):
            await db.commit()

        await db.rollback()

    async def test_case_insensitive_query(self, db, test_user):
        """Query should find emails regardless of case."""
        # Insert lowercase
        entry = EmailBlacklist(
            email="testcase@example.com", reason="Test", added_by=test_user.id
        )
        db.add(entry)
        await db.commit()

        # Query with uppercase should find it
        result = await db.scalar(
            select(EmailBlacklist.id).where(
                EmailBlacklist.email == "TESTCASE@EXAMPLE.COM"
            )
        )
        assert result is not None

        # Query with mixed case should find it
        result = await db.scalar(
            select(EmailBlacklist.id).where(
                EmailBlacklist.email == "TestCase@Example.Com"
            )
        )
        assert result is not None

    async def test_blacklist_check_case_insensitive(self, db, test_user):
        """is_email_blacklisted should work with any case."""
        # Insert lowercase
        entry = EmailBlacklist(
            email="blocked@example.com", reason="Test", added_by=test_user.id
        )
        db.add(entry)
        await db.commit()

        # Check with various cases
        assert await is_email_blacklisted(db, "blocked@example.com") is True
        assert await is_email_blacklisted(db, "BLOCKED@EXAMPLE.COM") is True
        assert await is_email_blacklisted(db, "Blocked@Example.Com") is True
        assert await is_email_blacklisted(db, "bLoCkEd@eXaMpLe.CoM") is True

    async def test_direct_db_insert_uppercase_blocked(self, db, test_user):
        """Direct database insert with uppercase should still block lowercase checks."""
        # Simulate attacker inserting uppercase directly
        await db.execute(
            text("""
            INSERT INTO email_blacklist (id, email, reason, added_by, created_at, updated_at, added_at)
            VALUES (
                gen_random_uuid(),
                'ATTACKER@EVIL.COM',
                'Direct insert',
                :added_by,
                NOW(),
                NOW(),
                NOW()
            )
        """),
            {"added_by": test_user.id},
        )
        await db.commit()

        # Application should still detect it (lowercase check)
        assert await is_email_blacklisted(db, "attacker@evil.com") is True

    async def test_index_case_insensitive(self, db, test_user):
        """Index should work case-insensitively (performance check)."""
        # Insert many entries
        for i in range(100):
            entry = EmailBlacklist(
                email=f"user{i}@example.com", reason="Test", added_by=test_user.id
            )
            db.add(entry)
        await db.commit()

        # Query with uppercase should use index (fast)
        import time

        start = time.time()

        result = await db.scalar(
            select(EmailBlacklist.id).where(
                EmailBlacklist.email == "USER50@EXAMPLE.COM"
            )
        )

        duration = time.time() - start

        assert result is not None
        assert duration < 0.1, f"Query took {duration}s (should use index)"

    async def test_mixed_case_entries_consolidated(self, db, test_user):
        """Verify multiple case variations cannot coexist."""
        # Insert first variation
        entry1 = EmailBlacklist(
            email="test@example.com", reason="First entry", added_by=test_user.id
        )
        db.add(entry1)
        await db.commit()

        # Try multiple case variations - all should fail
        test_cases = [
            "TEST@EXAMPLE.COM",
            "Test@Example.Com",
            "TeSt@ExAmPlE.cOm",
        ]

        for email_variant in test_cases:
            entry = EmailBlacklist(
                email=email_variant, reason="Duplicate attempt", added_by=test_user.id
            )
            db.add(entry)

            with pytest.raises(IntegrityError):
                await db.commit()

            await db.rollback()

        # Verify only one entry exists
        count = await db.scalar(
            select(EmailBlacklist.id).where(
                EmailBlacklist.email.ilike("test@example.com")
            )
        )
        assert count is not None
