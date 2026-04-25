"""Client schema compatibility helpers.

Ensures legacy databases can work with newer client legal-fields columns
without a separate migration step.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def ensure_client_legal_columns(db: AsyncSession) -> None:
    """Create legal requisites columns in ``clients`` if missing."""
    await db.execute(text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS kpp varchar(20) NULL"))
    await db.execute(text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS ogrn varchar(20) NULL"))
    await db.execute(text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS ogrnip varchar(20) NULL"))
    await db.execute(text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS bik varchar(20) NULL"))
    await db.execute(text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS bank_account varchar(50) NULL"))
    await db.execute(text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS corr_account varchar(50) NULL"))
    await db.execute(text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS bank_name varchar(500) NULL"))
