import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import httpx
from .config import get_settings

logger = logging.getLogger(__name__)



@dataclass
class Appointment:
    id: str
    start: str


class CalendarAdapter:
    async def book(self, name: str, phone: str, service: str, requested_time: str) -> Appointment:
        # A deterministic, testable adapter. Implement Google/Microsoft Calendar here.
        start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        return Appointment(id=f"demo-{uuid4().hex[:10]}", start=start.isoformat())


class HubSpotAdapter:
    async def create_or_update_lead(self, *, name: str, phone: str, service: str, location: str, appointment_id: str) -> None:
        token = get_settings().hubspot_private_app_token
        if not token:
            return
        first, *rest = name.split(maxsplit=1)
        payload = {
            "properties": {
                "firstname": first,
                "lastname": rest[0] if rest else "",
                "phone": phone,
                "city": location,
                "lifecyclestage": "lead",
            }
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://api.hubapi.com/crm/v3/objects/contacts",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"}
                )
                if response.status_code not in (201, 409):
                    logger.warning("HubSpot API returned status %s: %s", response.status_code, response.text)
        except Exception as exc:
            logger.warning("HubSpot API error (lead still booked in DB): %s", exc)

