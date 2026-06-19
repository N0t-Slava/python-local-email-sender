from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import inspect, text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.configs.config import DATABASE_URL, SYNC_DATABASE_URL

engine = create_async_engine(DATABASE_URL)
session_factory = async_sessionmaker(engine, expire_on_commit=False)
sync_engine = create_engine(SYNC_DATABASE_URL)
sync_session_factory = sessionmaker(sync_engine, expire_on_commit=False)
class SQLBase(DeclarativeBase):
    pass

def get_sync_db():
    with sync_session_factory() as session:
        yield session

# Dependency для FastAPI
async def get_db():
    async with session_factory() as session:
        yield session


async def init_db():
    from src.models import models

    async with engine.begin() as conn:
        await conn.run_sync(SQLBase.metadata.create_all)
        await _ensure_contacts_schema(conn)
        await _ensure_suppression_list_schema(conn)
        await _ensure_campaigns_content_schema(conn)
        await _ensure_campaign_recipients_variables_schema(conn)
        await _ensure_campaign_recipients_indexes(conn)

async def _ensure_campaigns_content_schema(conn):
    def get_columns(sync_conn):
        inspector = inspect(sync_conn)
        if not inspector.has_table("campaigns"):
            return set()
        return {column["name"] for column in inspector.get_columns("campaigns")}

    columns = await conn.run_sync(get_columns)

    if not columns:
        return

    if conn.dialect.name == "postgresql":
        if "from_name" not in columns:
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN from_name VARCHAR"))

        if "reply_to_email" not in columns:
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN reply_to_email VARCHAR"))

        if "html_body" not in columns:
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN html_body TEXT"))

        if "content_type" not in columns:
            await conn.execute(
                text("ALTER TABLE campaigns ADD COLUMN content_type VARCHAR NOT NULL DEFAULT 'plain'")
            )

        if "send_rate_per_second" not in columns:
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN send_rate_per_second DOUBLE PRECISION"))

        if "track_opens" not in columns:
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN track_opens BOOLEAN NOT NULL DEFAULT TRUE"))

        if "track_clicks" not in columns:
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN track_clicks BOOLEAN NOT NULL DEFAULT TRUE"))

        if "scheduled_at" not in columns:
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN scheduled_at TIMESTAMP"))

        if "category" not in columns:
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN category VARCHAR"))

        if "tags" not in columns:
            await conn.execute(text("ALTER TABLE campaigns ADD COLUMN tags JSONB"))
        
async def _ensure_campaign_recipients_variables_schema(conn):
    def get_columns(sync_conn):
        inspector = inspect(sync_conn)
        if not inspector.has_table("campaign_recipients"):
            return set()
        return {column["name"] for column in inspector.get_columns("campaign_recipients")}

    columns = await conn.run_sync(get_columns)

    if not columns or "variables" in columns:
        return

    if conn.dialect.name == "postgresql":
        await conn.execute(text("ALTER TABLE campaign_recipients ADD COLUMN variables JSONB"))
    else:
        await conn.execute(text("ALTER TABLE campaign_recipients ADD COLUMN variables JSON"))


async def _ensure_campaign_recipients_indexes(conn):
    def has_table(sync_conn):
        inspector = inspect(sync_conn)
        return inspector.has_table("campaign_recipients")

    if not await conn.run_sync(has_table):
        return

    if conn.dialect.name == "postgresql":
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_campaign_recipients_claim
                ON campaign_recipients (campaign_id, status, attempt_count, created_at)
                """
            )
        )

async def _ensure_contacts_schema(conn):
    def get_columns(sync_conn):
        inspector = inspect(sync_conn)
        if not inspector.has_table("contacts"):
            return set()
        return {column["name"] for column in inspector.get_columns("contacts")}

    columns = await conn.run_sync(get_columns)
    if not columns:
        return

    dialect_name = conn.dialect.name

    if dialect_name == "postgresql":
        if "user_id" not in columns:
            await conn.execute(text("ALTER TABLE contacts ADD COLUMN user_id VARCHAR"))
            if "owner_id" in columns:
                await conn.execute(text("UPDATE contacts SET user_id = owner_id WHERE user_id IS NULL"))
        if "owner_id" in columns:
            await conn.execute(text("ALTER TABLE contacts ALTER COLUMN owner_id DROP NOT NULL"))

        if "name" not in columns:
            await conn.execute(text("ALTER TABLE contacts ADD COLUMN name VARCHAR NOT NULL DEFAULT ''"))
        if "status" not in columns:
            await conn.execute(text("ALTER TABLE contacts ADD COLUMN status VARCHAR NOT NULL DEFAULT 'subscribed'"))
        if "created_at" not in columns:
            await conn.execute(text("ALTER TABLE contacts ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT NOW()"))
        if "updated_at" not in columns:
            await conn.execute(text("ALTER TABLE contacts ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW()"))

        await conn.execute(text("UPDATE contacts SET name = '' WHERE name IS NULL"))
        await conn.execute(text("UPDATE contacts SET status = 'subscribed' WHERE status IS NULL"))
        await conn.execute(text("UPDATE contacts SET created_at = NOW() WHERE created_at IS NULL"))
        await conn.execute(text("UPDATE contacts SET updated_at = created_at WHERE updated_at IS NULL"))
        await conn.execute(text("ALTER TABLE contacts ALTER COLUMN user_id SET NOT NULL"))
        await conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = '_user_email_uc'
                    ) THEN
                        ALTER TABLE contacts ADD CONSTRAINT _user_email_uc UNIQUE (user_id, email);
                    END IF;
                END $$;
                """
            )
        )


async def _ensure_suppression_list_schema(conn):
    def get_columns(sync_conn):
        inspector = inspect(sync_conn)
        if not inspector.has_table("suppression_list"):
            return set()
        return {column["name"] for column in inspector.get_columns("suppression_list")}

    columns = await conn.run_sync(get_columns)
    if not columns:
        return

    if conn.dialect.name == "postgresql":
        if "user_id" not in columns:
            await conn.execute(text("ALTER TABLE suppression_list ADD COLUMN user_id VARCHAR"))
        if "note" not in columns:
            await conn.execute(text("ALTER TABLE suppression_list ADD COLUMN note TEXT"))
        if "created_by_user_id" not in columns:
            await conn.execute(text("ALTER TABLE suppression_list ADD COLUMN created_by_user_id VARCHAR"))

        await conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = '_suppression_list_email_uc'
                    ) THEN
                        ALTER TABLE suppression_list DROP CONSTRAINT _suppression_list_email_uc;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = '_suppression_list_user_email_uc'
                    ) THEN
                        ALTER TABLE suppression_list ADD CONSTRAINT _suppression_list_user_email_uc UNIQUE (user_id, email);
                    END IF;
                END $$;
                """
            )
        )
