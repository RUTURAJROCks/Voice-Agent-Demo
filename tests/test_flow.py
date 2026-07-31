import asyncio
from app.database import Call
from app.flow import advance, extract_phone, is_valid_location


class DummySession:
    pass


def test_qualification_to_confirmation():
    call = Call(twilio_call_sid="CA123")
    async def run():
        assert (await advance(call, "Asha Patel", DummySession())).next_state == "service"
        assert (await advance(call, "AC repair", DummySession())).next_state == "location"
        assert (await advance(call, "Pune 411001", DummySession())).next_state == "time"
        assert (await advance(call, "Tomorrow morning", DummySession())).next_state == "phone"
        assert (await advance(call, "9876543210", DummySession())).next_state == "confirm"
        assert call.service == "AC repair"
        assert call.phone == "+91 9876543210"
    asyncio.run(run())


def test_invalid_location_guardrail():
    call = Call(twilio_call_sid="CA127", state="location")
    async def run():
        turn = await advance(call, "949", DummySession())
        assert turn.next_state == "location"
        assert "valid city name or postal code" in turn.text
    asyncio.run(run())


def test_invalid_phone_guardrail():
    call = Call(twilio_call_sid="CA125", state="phone", location="Shimla")
    async def run():
        turn = await advance(call, "Sasi", DummySession())
        assert turn.next_state == "phone"
        assert "valid phone number" in turn.text
    asyncio.run(run())


def test_off_topic_guardrail():
    call = Call(twilio_call_sid="CA126", state="welcome")
    async def run():
        turn = await advance(call, "What is the weather today?", DummySession())
        assert "home services" in turn.text.lower()
    asyncio.run(run())


def test_human_request_escalates():
    call = Call(twilio_call_sid="CA124")
    turn = asyncio.run(advance(call, "I need a human representative", DummySession()))
    assert turn.should_escalate is True
    assert call.state == "escalated"
