from src.database.sqlalchemy import sync_session_factory
from src.services.campaigns_service import sync_record_campaign_send_results_service


def _record_campaign_results(
    campaign_id: str,
    user_id: str,
    results: list[dict],
):    
    
    with sync_session_factory() as db:
        sync_record_campaign_send_results_service(
            db,
            campaign_id=campaign_id,
            user_id=user_id,
            results=results,
        )



def record_campaign_results_from_worker(
    campaign_id: str,
    user_id: str,
    results: list[dict],
):
    _record_campaign_results(campaign_id, user_id, results)