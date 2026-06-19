import asyncio
from datetime import UTC, datetime

from src.models.models import Contact
from src.services.contacts_service import (
    add_contact_service,
    delete_contact_service,
    import_contacts_service,
    list_contacts_service,
)


class FakeScalarResult:
    def __init__(self, contacts):
        self.contacts = contacts

    def all(self):
        return self.contacts


class FakeContactSession:
    def __init__(self):
        self.contacts = []
        self.seen_filters = []

    async def scalar(self, query):
        filters = self._filters(query)
        for contact in self.contacts:
            if self._matches(contact, filters):
                return contact
        return None

    async def scalars(self, query):
        filters = self._filters(query)
        contacts = [contact for contact in self.contacts if self._matches(contact, filters)]
        contacts.sort(key=lambda contact: contact.created_at, reverse=True)
        return FakeScalarResult(contacts)

    def add(self, contact):
        now = datetime.now(UTC).replace(tzinfo=None)
        contact.created_at = contact.created_at or now
        contact.updated_at = contact.updated_at or now
        self.contacts.append(contact)

    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def refresh(self, contact):
        return None

    async def execute(self, query):
        filters = self._filters(query)
        self.contacts = [contact for contact in self.contacts if not self._matches(contact, filters)]

    def _filters(self, query):
        whereclause = getattr(query, "whereclause", None)
        if whereclause is None:
            return {}

        clauses = getattr(whereclause, "clauses", [whereclause])
        filters = {clause.left.key: clause.right.value for clause in clauses}
        self.seen_filters.append(filters)
        return filters

    def _matches(self, contact, filters):
        return all(str(getattr(contact, key)) == str(value) for key, value in filters.items())


def test_contacts_are_isolated_per_user():
    async def scenario():
        session = FakeContactSession()

        user_a_contact = await add_contact_service(session, "user-a", "Shared@Example.com", "User A")
        user_b_contact = await add_contact_service(session, "user-b", "shared@example.com", "User B")

        assert user_a_contact is not None
        assert user_b_contact is not None

        user_a_contacts = await list_contacts_service(session, "user-a")
        user_b_contacts = await list_contacts_service(session, "user-b")

        assert [contact["email"] for contact in user_a_contacts] == ["shared@example.com"]
        assert [contact["name"] for contact in user_a_contacts] == ["User A"]
        assert [contact["email"] for contact in user_b_contacts] == ["shared@example.com"]
        assert [contact["name"] for contact in user_b_contacts] == ["User B"]
        assert all("user_id" in filters for filters in session.seen_filters)

    asyncio.run(scenario())


def test_duplicate_email_is_rejected_for_same_user():
    async def scenario():
        session = FakeContactSession()

        first_contact = await add_contact_service(session, "user-a", "person@example.com")
        duplicate_contact = await add_contact_service(session, "user-a", "PERSON@example.com")

        assert first_contact is not None
        assert duplicate_contact is None
        assert len(await list_contacts_service(session, "user-a")) == 1
        assert all("user_id" in filters for filters in session.seen_filters)

    asyncio.run(scenario())


def test_delete_only_removes_current_users_contact():
    async def scenario():
        session = FakeContactSession()

        user_a_contact = await add_contact_service(session, "user-a", "person@example.com")
        await add_contact_service(session, "user-b", "person@example.com")

        deleted_as_other_user = await delete_contact_service(session, "user-b", user_a_contact["id"])
        assert deleted_as_other_user is None
        assert len(await list_contacts_service(session, "user-a")) == 1
        assert len(await list_contacts_service(session, "user-b")) == 1

        deleted = await delete_contact_service(session, "user-a", user_a_contact["id"])
        assert deleted["email"] == "person@example.com"
        assert await list_contacts_service(session, "user-a") == []
        assert len(await list_contacts_service(session, "user-b")) == 1
        assert all("user_id" in filters for filters in session.seen_filters)

    asyncio.run(scenario())


def test_import_skips_duplicates_for_user():
    async def scenario():
        session = FakeContactSession()
        await add_contact_service(session, "user-a", "existing@example.com")

        result = await import_contacts_service(
            session,
            "user-a",
            ["existing@example.com", "new@example.com"],
        )

        assert result["created_count"] == 1
        assert result["duplicate_count"] == 1
        assert result["total_found"] == 2
        assert {contact["email"] for contact in await list_contacts_service(session, "user-a")} == {
            "existing@example.com",
            "new@example.com",
        }
        assert all("user_id" in filters for filters in session.seen_filters)

    asyncio.run(scenario())


def test_import_skips_invalid_contacts():
    async def scenario():
        session = FakeContactSession()

        result = await import_contacts_service(
            session,
            "user-a",
            ["valid@example.com", "not-an-email", "also-invalid"],
        )

        assert result["created_count"] == 1
        assert result["duplicate_count"] == 2
        assert result["total_found"] == 3
        assert [contact["email"] for contact in await list_contacts_service(session, "user-a")] == [
            "valid@example.com"
        ]
        assert all("user_id" in filters for filters in session.seen_filters)

    asyncio.run(scenario())
