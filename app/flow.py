from dataclasses import dataclass
import re
from sqlalchemy.orm import Session
from .config import get_settings
from .database import Call
from .integrations import CalendarAdapter, HubSpotAdapter

INDIAN_CITIES = {
    "mumbai", "delhi", "bangalore", "bengaluru", "hyderabad", "pune",
    "shimla", "chennai", "kolkata", "ahmedabad", "jaipur", "surat",
    "lucknow", "chandigarh", "india"
}


@dataclass
class Turn:
    text: str
    next_state: str
    should_hang_up: bool = False
    should_escalate: bool = False


def normalized(value: str) -> str:
    return " ".join(value.strip().split())


def extract_phone(speech: str, location: str | None = None) -> str | None:
    digits = re.sub(r"\D", "", speech)
    if len(digits) >= 7:
        if len(digits) == 10:
            return f"+91 {digits}"
        if speech.startswith("+"):
            return f"+{digits}"
        loc = (location or "").lower()
        if any(city in loc for city in INDIAN_CITIES) or not loc:
            return f"+91 {digits[-10:]}"
        return f"+{digits}"
    return None


def is_valid_location(speech: str) -> bool:
    s = speech.strip()
    digits = re.sub(r"\D", "", s)
    if digits == s:  # purely numeric input like 949 or 12
        return len(digits) in (5, 6)
    cleaned = re.sub(r"[^a-zA-Z\s,.-]", "", s).strip()
    return len(cleaned) >= 3


async def advance(call: Call, speech: str, db: Session) -> Turn:
    speech = normalized(speech)
    call.transcript = (call.transcript or "") + f"Caller: {speech}\n"
    call.state = call.state or "welcome"
    lower = speech.lower()

    # Human Escalation Guardrail
    if any(phrase in lower for phrase in ("representative", "human", "agent", "emergency", "manager")):
        call.state = "escalated"
        return Turn("I will connect you with a team member now.", "escalated", should_escalate=True)

    # Irrelevant chatter / off-topic guardrail
    if any(phrase in lower for phrase in ("weather", "joke", "meaning of life", "who are you", "who made you", "president", "crypto", "bitcoin")):
        return Turn(f"I am the AI assistant for {get_settings().business_name}. I can help you book home services like AC repair, cleaning, or plumbing. What service do you need?", call.state)

    # Welcome State -> Collect Name
    if call.state == "welcome":
        if re.match(r"^\d+$", speech):
            return Turn("I didn't quite catch your name. May I have your full name, please?", "welcome")
        call.name = speech
        call.state = "service"
        return Turn(f"Thanks, {call.name}. What service do you need help with?", "service")

    # Service State -> Collect Service
    if call.state == "service":
        call.service = speech
        call.state = "location"
        return Turn("What city or postcode is the service for?", "location")

    # Location State -> Collect & Validate Location
    if call.state == "location":
        if not is_valid_location(speech):
            return Turn("That doesn't seem like a valid city name or postal code. Could you please provide a valid city name (like Mumbai, Pune, Shimla) or a 6-digit pincode?", "location")
        call.location = speech
        call.state = "time"
        return Turn("What day and time would you prefer? For example, tomorrow morning or evening.", "time")


    # Time State -> Collect Preferred Time
    if call.state == "time":
        call.requested_time = speech
        call.state = "phone"
        return Turn("Finally, what is your mobile phone number for confirmation?", "phone")

    # Phone State -> Collect & Validate Phone Number
    if call.state == "phone":
        phone_num = extract_phone(speech, call.location)
        if not phone_num:
            return Turn("That doesn't seem like a valid phone number. Could you please provide your mobile phone number with digits?", "phone")
        call.phone = phone_num
        call.state = "confirm"
        return Turn(f"I have your {call.service} request in {call.location} for {call.requested_time}, contact number {call.phone}. Should I book this appointment?", "confirm")

    # Confirmation State -> Handle Confirmation
    if call.state == "confirm":
        affirmative_words = ("yes", "yeah", "yep", "correct", "please", "book", "sure", "ok", "okay", "confirm", "do it", "go ahead")
        if any(word in lower for word in affirmative_words):
            appointment = await CalendarAdapter().book(call.name or "Unknown", call.phone or "", call.service or "", call.requested_time or "")
            await HubSpotAdapter().create_or_update_lead(name=call.name or "Unknown", phone=call.phone or "", service=call.service or "", location=call.location or "", appointment_id=appointment.id)
            call.appointment_id, call.state = appointment.id, "booked"
            return Turn("You are booked. Our team will send a confirmation shortly. Thank you for calling.", "booked", should_hang_up=True)

        # If user provides an updated time or correction during confirmation
        call.requested_time = speech
        call.state = "confirm"
        return Turn(f"Got it. Updated your preferred time to {speech}. Should I book this appointment now?", "confirm")

    return Turn("I am sorry, I could not continue that request. Let me connect you with our team.", "escalated", should_escalate=True)
