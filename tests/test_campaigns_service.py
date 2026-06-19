import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from src.models.models import Campaign, CampaignRecipient, Contact
from src.services.campaigns_service import (
    add_campaign_service,
    delete_campaign_service,
    get_campaign_service,
    list_campaigns_service,
    mark_campaign_sending_service,
    record_campaign_send_results_service,
    save_current_draft_service,
    serialize_campaign,
    update_campaign_service,
)


EXPECTED_FRONTEND_FIELDS = {
    "id",
    "user_id",
    "task_id",
    "subject",
    "body",
    "from_email",
    "from_name",
    "reply_to_email",
    "queued_recipients",
    "recipients",
    "status",
    "created_at",
    "batch_size",
    "per_batch_delay",
    "send_rate_per_second",
    "track_opens",
    "track_clicks",
    "category",
    "tags",
    "sent_count",
    "opened_count",
    "clicked_count",
    "updated_at",
    "sent_at",
}


class FakeScalarResult:
    def __init__(self, campaigns):
        self.campaigns = campaigns

    def all(self):
        return self.campaigns


class FakeCampaignSession:
    def __init__(self):
        self.campaigns = []
        self.seen_filters = []

    async def scalar(self, query):
        filters = self._filters(query)
        for campaign in self.campaigns:
            if self._matches(campaign, filters):
                return campaign
        return None

    async def scalars(self, query):
        queried_entities = {
            description.get("entity")
            for description in getattr(query, "column_descriptions", [])
        }
        if Contact in queried_entities:
            return FakeScalarResult([])

        filters = self._filters(query)
        campaigns = [campaign for campaign in self.campaigns if self._matches(campaign, filters)]
        campaigns.sort(key=lambda campaign: campaign.created_at, reverse=True)
        return FakeScalarResult(campaigns)

    def add(self, campaign):
        now = datetime.now(UTC).replace(tzinfo=None)
        campaign.id = campaign.id or uuid4()
        campaign.created_at = campaign.created_at or now
        campaign.updated_at = campaign.updated_at or now
        campaign.sent_count = campaign.sent_count or 0
        campaign.opened_count = campaign.opened_count or 0
        campaign.clicked_count = campaign.clicked_count or 0

        for recipient in campaign.recipients:
            recipient.id = recipient.id or uuid4()
            recipient.campaign_id = campaign.id
            recipient.created_at = recipient.created_at or now
            recipient.status = recipient.status or "queued"

        self.campaigns.append(campaign)

    async def commit(self):
        now = datetime.now(UTC).replace(tzinfo=None)
        for campaign in self.campaigns:
            campaign.updated_at = now
            for recipient in campaign.recipients:
                recipient.id = recipient.id or uuid4()
                recipient.campaign_id = campaign.id
                recipient.created_at = recipient.created_at or now
                recipient.status = recipient.status or "queued"

    async def refresh(self, campaign):
        return None

    async def flush(self):
        return None

    async def delete(self, campaign):
        self.campaigns = [stored_campaign for stored_campaign in self.campaigns if stored_campaign.id != campaign.id]

    def _filters(self, query):
        whereclause = getattr(query, "whereclause", None)
        if whereclause is None:
            return {}

        clauses = getattr(whereclause, "clauses", [whereclause])
        filters = {clause.left.key: clause.right.value for clause in clauses}
        self.seen_filters.append(filters)
        return filters

    def _matches(self, campaign, filters):
        return all(str(getattr(campaign, key)) == str(value) for key, value in filters.items())


def test_user_a_can_create_draft_campaign():
    async def scenario():
        session = FakeCampaignSession()

        campaign = await add_campaign_service(
            session,
            user_id="user-a",
            task_id="",
            subject="Draft subject",
            body="Draft body",
            from_email="sender@example.com",
            queued_recipients=2,
            recipients=["one@example.com", "two@example.com"],
            status="Draft",
        )

        assert campaign["user_id"] == "user-a"
        assert campaign["status"] == "Draft"
        assert campaign["task_id"] is None
        assert campaign["queued_recipients"] == 2
        assert campaign["recipients"] == ["one@example.com", "two@example.com"]
        assert campaign["sent_count"] == 0
        assert campaign["opened_count"] == 0
        assert campaign["clicked_count"] == 0
        assert campaign["sent_at"] is None
        assert EXPECTED_FRONTEND_FIELDS.issubset(campaign.keys())

    asyncio.run(scenario())


def test_saving_current_draft_replaces_existing_recipients_without_duplicates():
    async def scenario():
        session = FakeCampaignSession()

        first_save = await save_current_draft_service(
            session,
            user_id="user-a",
            subject="Draft subject",
            body="Draft body",
            from_email="sender@example.com",
            recipients=["one@example.com", "two@example.com"],
        )
        second_save = await save_current_draft_service(
            session,
            user_id="user-a",
            subject="Updated draft subject",
            body="Updated draft body",
            from_email="sender@example.com",
            recipients=["one@example.com", "two@example.com"],
        )

        assert first_save["id"] == second_save["id"]
        assert second_save["subject"] == "Updated draft subject"
        assert second_save["queued_recipients"] == 2
        assert second_save["recipients"] == ["one@example.com", "two@example.com"]
        assert len(session.campaigns) == 1
        assert len(session.campaigns[0].recipients) == 2

    asyncio.run(scenario())


def test_partial_draft_can_be_saved_without_recipients():
    async def scenario():
        session = FakeCampaignSession()

        campaign = await add_campaign_service(
            session,
            user_id="user-a",
            task_id="",
            subject="Work in progress",
            body="",
            from_email="",
            queued_recipients=999,
            recipients=[],
            status="Draft",
        )

        assert campaign["status"] == "Draft"
        assert campaign["subject"] == "Work in progress"
        assert campaign["body"] == ""
        assert campaign["from_email"] == ""
        assert campaign["queued_recipients"] == 0
        assert campaign["recipients"] == []
        assert campaign["sent_at"] is None

    asyncio.run(scenario())


def test_users_can_list_only_their_own_campaigns():
    async def scenario():
        session = FakeCampaignSession()
        await add_campaign_service(
            session,
            "user-a",
            "",
            "A",
            "Body",
            "sender@example.com",
            1,
            ["shared@example.com"],
            "Draft",
        )
        await add_campaign_service(
            session,
            "user-b",
            "",
            "B",
            "Body",
            "sender@example.com",
            1,
            ["shared@example.com"],
            "Draft",
        )

        user_a_campaigns = await list_campaigns_service(session, "user-a")
        user_b_campaigns = await list_campaigns_service(session, "user-b")

        assert [campaign["subject"] for campaign in user_a_campaigns] == ["A"]
        assert [campaign["subject"] for campaign in user_b_campaigns] == ["B"]
        assert all("user_id" in filters for filters in session.seen_filters)

    asyncio.run(scenario())


def test_user_b_cannot_access_or_send_user_a_draft():
    async def scenario():
        session = FakeCampaignSession()
        user_a_campaign = await add_campaign_service(
            session,
            "user-a",
            "",
            "Private draft",
            "Body",
            "sender@example.com",
            1,
            ["one@example.com"],
            "Draft",
        )

        assert await get_campaign_service(session, "user-b", user_a_campaign["id"]) is None

        updated = await update_campaign_service(
            session,
            "user-b",
            user_a_campaign["id"],
            status="Sent",
            task_id="task-b",
        )

        assert updated is None
        owner_campaign = serialize_campaign(session.campaigns[0])
        assert owner_campaign["status"] == "Draft"
        assert owner_campaign["task_id"] is None
        assert all("user_id" in filters for filters in session.seen_filters)

    asyncio.run(scenario())


def test_sent_campaign_is_stored_with_sent_status_and_recipients():
    async def scenario():
        session = FakeCampaignSession()

        campaign = await add_campaign_service(
            session,
            user_id="user-a",
            task_id="task-1",
            subject="Sent subject",
            body="Sent body",
            from_email="sender@example.com",
            queued_recipients=2,
            recipients=["one@example.com", "two@example.com"],
            status="Sent",
            batch_size=10,
            per_batch_delay=2.5,
        )

        assert campaign["status"] == "Sent"
        assert campaign["task_id"] == "task-1"
        assert campaign["queued_recipients"] == 2
        assert campaign["recipients"] == ["one@example.com", "two@example.com"]
        assert campaign["batch_size"] == 10
        assert campaign["per_batch_delay"] == 2.5
        assert campaign["sent_at"] is not None

    asyncio.run(scenario())


def test_campaign_identity_and_settings_are_stored():
    async def scenario():
        session = FakeCampaignSession()

        campaign = await add_campaign_service(
            session,
            user_id="user-a",
            task_id="task-1",
            subject="Settings subject",
            body="Settings body",
            from_email="sender@example.com",
            queued_recipients=1,
            recipients=["one@example.com"],
            status="Ready",
            from_name=" Sender Name ",
            reply_to_email=" replies@example.com ",
            send_rate_per_second=2.5,
            track_opens=False,
            track_clicks=True,
        )

        assert campaign["from_name"] == "Sender Name"
        assert campaign["reply_to_email"] == "replies@example.com"
        assert campaign["send_rate_per_second"] == 2.5
        assert campaign["track_opens"] is False
        assert campaign["track_clicks"] is True

    asyncio.run(scenario())


def test_campaign_category_and_tags_are_stored_normalized():
    async def scenario():
        session = FakeCampaignSession()

        campaign = await add_campaign_service(
            session,
            user_id="user-a",
            task_id="",
            subject="Tagged subject",
            body="Body",
            from_email="sender@example.com",
            queued_recipients=1,
            recipients=["one@example.com"],
            status="Ready",
            category=" Newsletter ",
            tags=["Promo", " promo ", "", "VIP"],
        )

        assert campaign["category"] == "Newsletter"
        assert campaign["tags"] == ["Promo", "VIP"]

    asyncio.run(scenario())


def test_empty_campaign_identity_values_are_normalized_to_none():
    async def scenario():
        session = FakeCampaignSession()

        campaign = await add_campaign_service(
            session,
            user_id="user-a",
            task_id="",
            subject="Empty identity",
            body="Body",
            from_email="sender@example.com",
            queued_recipients=1,
            recipients=["one@example.com"],
            status="Draft",
            from_name=" ",
            reply_to_email="",
        )

        assert campaign["from_name"] is None
        assert campaign["reply_to_email"] is None

    asyncio.run(scenario())


def test_mark_campaign_sending_updates_task_and_status():
    async def scenario():
        session = FakeCampaignSession()
        campaign = await add_campaign_service(
            session,
            "user-a",
            "",
            "Sending subject",
            "Body",
            "sender@example.com",
            1,
            ["one@example.com"],
            "Draft",
        )

        updated = await mark_campaign_sending_service(
            session,
            "user-a",
            campaign["id"],
            "task-1",
        )

        assert updated["status"] == "Sending"
        assert updated["task_id"] == "task-1"
        assert updated["sent_count"] == 0
        assert updated["sent_at"] is None

    asyncio.run(scenario())


def test_queued_recipients_matches_stored_recipient_count():
    async def scenario():
        session = FakeCampaignSession()

        campaign = await add_campaign_service(
            session,
            user_id="user-a",
            task_id="task-1",
            subject="Count subject",
            body="Count body",
            from_email="sender@example.com",
            queued_recipients=999,
            recipients=["one@example.com", "two@example.com", "three@example.com"],
            status="Sent",
        )

        assert campaign["queued_recipients"] == 3
        assert len(session.campaigns[0].recipients) == 3

    asyncio.run(scenario())


def test_record_all_success_sets_campaign_sent_and_recipient_sent_at():
    async def scenario():
        session = FakeCampaignSession()
        campaign = await add_campaign_service(
            session,
            "user-a",
            "task-1",
            "All good",
            "Body",
            "sender@example.com",
            2,
            ["one@example.com", "two@example.com"],
            "Sending",
        )

        updated = await record_campaign_send_results_service(
            session,
            campaign["id"],
            [
                {"email": "one@example.com", "status": "sent"},
                {"email": "two@example.com", "status": "sent"},
            ],
            user_id="user-a",
        )

        assert updated["status"] == "Sent"
        assert updated["sent_count"] == 2
        assert updated["queued_recipients"] == 2
        assert updated["opened_count"] == 0
        assert updated["clicked_count"] == 0
        assert updated["sent_at"] is not None
        assert [recipient.status for recipient in session.campaigns[0].recipients] == ["sent", "sent"]
        assert all(recipient.sent_at is not None for recipient in session.campaigns[0].recipients)

    asyncio.run(scenario())


def test_record_partial_failure_sets_partially_sent_and_error_message():
    async def scenario():
        session = FakeCampaignSession()
        campaign = await add_campaign_service(
            session,
            "user-a",
            "task-1",
            "Mixed",
            "Body",
            "sender@example.com",
            2,
            ["one@example.com", "two@example.com"],
            "Sending",
        )

        updated = await record_campaign_send_results_service(
            session,
            campaign["id"],
            [
                {"email": "one@example.com", "status": "sent"},
                {"email": "two@example.com", "status": "failed", "error_message": "SMTP rejected"},
            ],
            user_id="user-a",
        )

        failed_recipient = session.campaigns[0].recipients[1]
        assert updated["status"] == "Partially Sent"
        assert updated["sent_count"] == 1
        assert failed_recipient.status == "failed"
        assert failed_recipient.error_message == "SMTP rejected"
        assert failed_recipient.sent_at is None

    asyncio.run(scenario())


def test_record_all_failure_sets_failed_status():
    async def scenario():
        session = FakeCampaignSession()
        campaign = await add_campaign_service(
            session,
            "user-a",
            "task-1",
            "All bad",
            "Body",
            "sender@example.com",
            2,
            ["one@example.com", "two@example.com"],
            "Sending",
        )

        updated = await record_campaign_send_results_service(
            session,
            campaign["id"],
            [
                {"email": "one@example.com", "status": "failed", "error_message": "No route"},
                {"email": "two@example.com", "status": "failed", "error_message": "Mailbox missing"},
            ],
            user_id="user-a",
        )

        assert updated["status"] == "Failed"
        assert updated["sent_count"] == 0
        assert [recipient.status for recipient in session.campaigns[0].recipients] == ["failed", "failed"]

    asyncio.run(scenario())


def test_draft_send_updates_only_owners_campaign():
    async def scenario():
        session = FakeCampaignSession()
        user_a_campaign = await add_campaign_service(
            session,
            "user-a",
            "",
            "A",
            "Body",
            "sender@example.com",
            1,
            ["one@example.com"],
            "Draft",
        )
        user_b_campaign = await add_campaign_service(
            session,
            "user-b",
            "",
            "B",
            "Body",
            "sender@example.com",
            1,
            ["two@example.com"],
            "Draft",
        )

        updated = await mark_campaign_sending_service(
            session,
            "user-a",
            user_a_campaign["id"],
            "task-a",
        )

        assert updated["status"] == "Sending"
        assert updated["task_id"] == "task-a"

        user_b_model = await get_campaign_service(session, "user-b", user_b_campaign["id"])
        user_b_serialized = serialize_campaign(user_b_model)
        assert user_b_serialized["status"] == "Draft"
        assert user_b_serialized["task_id"] is None

    asyncio.run(scenario())


def test_campaign_recipients_do_not_require_contact_ids():
    async def scenario():
        session = FakeCampaignSession()
        campaign = await add_campaign_service(
            session,
            "user-a",
            "",
            "No contact ids",
            "Body",
            "sender@example.com",
            1,
            ["loose-email@example.com"],
            "Draft",
        )

        stored_recipient: CampaignRecipient = session.campaigns[0].recipients[0]
        assert stored_recipient.contact_id is None
        assert campaign["recipients"] == ["loose-email@example.com"]

    asyncio.run(scenario())


def test_user_can_delete_own_ready_campaign():
    async def scenario():
        session = FakeCampaignSession()
        campaign = await add_campaign_service(
            session,
            "user-a",
            "",
            "Delete me",
            "Body",
            "sender@example.com",
            1,
            ["one@example.com"],
            "Ready",
        )

        result = await delete_campaign_service(session, "user-a", campaign["id"])

        assert result == "deleted"
        assert session.campaigns == []

    asyncio.run(scenario())


def test_user_cannot_delete_active_campaign():
    async def scenario():
        session = FakeCampaignSession()
        campaign = await add_campaign_service(
            session,
            "user-a",
            "task-a",
            "Active",
            "Body",
            "sender@example.com",
            1,
            ["one@example.com"],
            "Sending",
        )

        result = await delete_campaign_service(session, "user-a", campaign["id"])

        assert result == "active"
        assert len(session.campaigns) == 1

    asyncio.run(scenario())
