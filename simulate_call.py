"""Interactive terminal simulator to test the Voice AI agent without incurring phone charges."""
import sys
import xml.etree.ElementTree as ET
import httpx

BASE_URL = "http://127.0.0.1:8000"


def parse_twiml(xml_str: str) -> str:
    try:
        root = ET.fromstring(xml_str)
        says = [elem.text for elem in root.iter("Say") if elem.text]
        return " ".join(says)
    except Exception:
        return xml_str


def main():
    print("==========================================")
    print("   VOICE AI AGENT TERMINAL SIMULATOR     ")
    print("==========================================")
    print("Connecting to local FastAPI server at http://127.0.0.1:8000...\n")

    client = httpx.Client(base_url=BASE_URL, timeout=10.0)
    call_sid = "CA_simulated_demo"
    caller_phone = "+919876543210"

    try:
        res = client.post("/voice/incoming", data={"CallSid": call_sid, "From": caller_phone})
    except httpx.HTTPError as exc:
        print(f"Failed to connect to server: {exc}")
        print("Please ensure '.venv/bin/uvicorn app.main:app --reload' is running!")
        return

    if res.status_code != 200:
        print(f"Error starting call: {res.status_code} {res.text}")
        return

    agent_speech = parse_twiml(res.text)
    print(f"🤖 AI AGENT: {agent_speech}\n")

    # Determine call_id from response or database
    call_id = 1
    try:
        root = ET.fromstring(res.text)
        gather = root.find("Gather")
        if gather is not None and "action" in gather.attrib:
            action = gather.attrib["action"]
            call_id = action.rstrip("/").split("/")[-1]
    except Exception:
        pass

    while True:
        try:
            user_input = input("🗣️ YOU SAY: ")
        except (KeyboardInterrupt, EOFError):
            print("\nCall ended.")
            break

        if not user_input.strip():
            continue

        res = client.post(f"/voice/gather/{call_id}", data={"SpeechResult": user_input})
        if res.status_code != 200:
            print(f"Error: {res.status_code} {res.text}")
            break

        agent_speech = parse_twiml(res.text)
        print(f"\n🤖 AI AGENT: {agent_speech}\n")

        if "<Hangup" in res.text or "<Dial" in res.text:
            print("==========================================")
            print("         CALL ENDED / COMPLETED           ")
            print("==========================================")
            break


if __name__ == "__main__":
    main()
