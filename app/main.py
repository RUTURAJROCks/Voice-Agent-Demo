import logging
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Dial, Gather, VoiceResponse
from .config import get_settings
from .database import Call, get_db, init_db
from .flow import advance
from .llm import polish_spoken_reply

import os

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Voice AI Lead Qualification Agent", version="1.0.0")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
def startup() -> None:
    try:
        init_db()
    except Exception as exc:
        logging.warning("Startup DB initialization warning: %s", exc)



def verify_twilio(request: Request, form: dict) -> None:
    settings = get_settings()
    if not settings.twilio_validate_signatures or settings.environment == "development":
        return
    signature = request.headers.get("X-Twilio-Signature", "")
    if not settings.twilio_auth_token or not RequestValidator(settings.twilio_auth_token).validate(str(request.url), form, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


def gather_response(prompt: str, call_id: int, *, end: bool = False) -> Response:
    settings = get_settings()
    voice = VoiceResponse()
    voice.say(prompt, voice="Polly.Aditi", language="en-IN")
    if end:
        voice.hangup()
    else:
        gather = Gather(input="speech", action=f"{settings.public_base_url}/voice/gather/{call_id}", method="POST", speech_timeout="auto", language="en-IN")
        gather.say("Please say that after the tone.", voice="Polly.Aditi", language="en-IN")
        voice.append(gather)
        voice.redirect(f"{settings.public_base_url}/voice/retry/{call_id}", method="POST")
    return Response(str(voice), media_type="application/xml")


@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "static", "index.html"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "static", "index.html"),
        "app/static/index.html",
    ]
    for p in possible_paths:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as page:
                return HTMLResponse(page.read())
    return HTMLResponse("<h1>Voice AI Lead Qualification Agent</h1><p>Website active.</p>")




@app.get("/api/status")
def status() -> dict:
    settings = get_settings()
    return {"service": "online", "ai_enabled": bool(settings.openrouter_api_key), "primary_model": settings.openrouter_primary_model, "fallback_models": settings.openrouter_models}


@app.get("/api/calls")
def get_calls(db: Session = Depends(get_db)) -> list[dict]:
    calls = db.query(Call).order_by(Call.id.desc()).limit(5).all()

    return [
        {
            "id": c.id,
            "call_sid": c.twilio_call_sid,
            "state": c.state,
            "name": c.name,
            "phone": c.phone,
            "service": c.service,
            "location": c.location,
            "requested_time": c.requested_time,
            "appointment_id": c.appointment_id,
            "transcript": c.transcript,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in calls
    ]



@app.post("/voice/incoming")
async def incoming(request: Request, CallSid: str = Form(...), From: str = Form(""), db: Session = Depends(get_db)):
    verify_twilio(request, dict(await request.form()))
    call = db.query(Call).filter(Call.twilio_call_sid == CallSid).one_or_none()
    if not call:
        call = Call(twilio_call_sid=CallSid, phone=From)
        db.add(call)
        db.commit()
        db.refresh(call)
    return gather_response(f"Thank you for calling {get_settings().business_name}. I can help book an appointment. May I have your name?", call.id)


@app.post("/voice/gather/{call_id}")
async def gather(
    call_id: int,
    request: Request,
    SpeechResult: str = Form(""),
    provider: str = Form("openrouter"),
    api_key: str = Form(""),
    db: Session = Depends(get_db)
):
    verify_twilio(request, dict(await request.form()))
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if not SpeechResult:
        return gather_response("I did not catch that. Please say it again.", call.id)
    turn = await advance(call, SpeechResult, db)
    spoken_reply, routed_model = await polish_spoken_reply(
        turn.text,
        state=turn.next_state,
        provider=provider,
        api_key=api_key
    )

    if routed_model:
        logging.info("Call %s used OpenRouter model %s", call.id, routed_model)
    db.commit()
    if turn.should_escalate:
        response = VoiceResponse()
        response.say(spoken_reply, voice="Polly.Aditi", language="en-IN")
        if get_settings().escalation_phone_number:
            response.append(Dial(get_settings().escalation_phone_number))
        else:
            response.say("Our team will call you back shortly.", voice="Polly.Aditi", language="en-IN")
        return Response(str(response), media_type="application/xml")
    return gather_response(spoken_reply, call.id, end=turn.should_hang_up)


@app.post("/voice/retry/{call_id}")
async def retry(call_id: int):
    return gather_response("I did not hear a response. Please say that again, or say representative to speak with our team.", call_id)
