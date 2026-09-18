"""
FastAPI orchestrator. The LLM never decides entitlements itself — it must
call the tools below, which wrap the deterministic policy engine. Every
tool call is logged to AUDIT_LOG with the rule that authorised it.
"""

import json
import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

from data import BOOKINGS, CUSTOMERS, STYLE_SAMPLES_ONLY
from policy import (
    cancellation_options,
    delay_compensation,
    hotel_entitlement,
    full_night_hotel_request,
    fare_difference_check,
    tier_benefit,
    check_prohibited,
    detect_legal_threat,
)

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
MODEL = "openai/gpt-oss-20b"
app = FastAPI(title="Airline Disruption Resolution Agent")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

AUDIT_LOG = []
SESSIONS: dict[str, list] = {}


# ---------------- Tool implementations ----------------

def _log(pnr, action, result_dict):
    AUDIT_LOG.append({
        "timestamp": datetime.utcnow().isoformat(),
        "pnr": pnr,
        "action": action,
        "result": result_dict,
    })


def tool_get_booking(pnr: str) -> dict:
    pnr = pnr.strip().upper()
    if pnr not in CUSTOMERS:
        return {"error": "No booking found for that reference. Please double-check the PNR."}
    return {
        "customer": CUSTOMERS[pnr]["name"],
        "tier": CUSTOMERS[pnr]["tier"],
        "flights": BOOKINGS[pnr],
    }


def tool_get_cancellation_options(pnr: str, flight_number: str) -> dict:
    pnr = pnr.strip().upper()
    flight = next((f for f in BOOKINGS.get(pnr, []) if f["flight"] == flight_number), None)
    if not flight:
        return {"error": "Flight not found on this booking."}
    r = cancellation_options(flight)
    out = r.__dict__
    _log(pnr, "cancellation_options", out)
    return out


def tool_get_delay_compensation(pnr: str, flight_number: str) -> dict:
    pnr = pnr.strip().upper()
    flight = next((f for f in BOOKINGS.get(pnr, []) if f["flight"] == flight_number), None)
    if not flight:
        return {"error": "Flight not found on this booking."}
    r = delay_compensation(flight.get("delay_hours", 0))
    out = r.__dict__
    _log(pnr, "delay_compensation", out)
    return out


def tool_check_hotel_request(pnr: str, flight_number: str, requesting_full_night: bool) -> dict:
    pnr = pnr.strip().upper()
    flight = next((f for f in BOOKINGS.get(pnr, []) if f["flight"] == flight_number), None)
    if not flight:
        return {"error": "Flight not found on this booking."}
    if requesting_full_night:
        r = full_night_hotel_request()
    else:
        r = hotel_entitlement(flight.get("delay_hours", 0))
    out = r.__dict__
    _log(pnr, "hotel_request", out)
    return out


def tool_check_fare_difference(pnr: str, amount_inr: float) -> dict:
    pnr = pnr.strip().upper()
    r = fare_difference_check(amount_inr)
    out = r.__dict__
    _log(pnr, "fare_difference", out)
    return out


def tool_get_tier_benefit(pnr: str) -> dict:
    pnr = pnr.strip().upper()
    if pnr not in CUSTOMERS:
        return {"error": "No booking found."}
    r = tier_benefit(CUSTOMERS[pnr]["tier"])
    out = r.__dict__
    _log(pnr, "tier_benefit", out)
    return out


def tool_escalate(pnr: str, reason: str) -> dict:
    out = {"escalated": True, "reason": reason}
    _log(pnr, "ESCALATE_TO_HUMAN", out)
    return out


def tool_check_prohibited(pnr: str, action_key: str) -> dict:
    r = check_prohibited(action_key)
    out = r.__dict__
    _log(pnr, f"prohibited_check:{action_key}", out)
    return out


TOOL_IMPLS = {
    "get_booking": tool_get_booking,
    "get_cancellation_options": tool_get_cancellation_options,
    "get_delay_compensation": tool_get_delay_compensation,
    "check_hotel_request": tool_check_hotel_request,
    "check_fare_difference": tool_check_fare_difference,
    "get_tier_benefit": tool_get_tier_benefit,
    "escalate": tool_escalate,
    "check_prohibited": tool_check_prohibited,
}

TOOLS = [
    {"type": "function", "function": {
        "name": "get_booking", "description": "Look up a customer's booking by PNR.",
        "parameters": {"type": "object", "properties": {
            "pnr": {"type": "string"}}, "required": ["pnr"]}}},
    {"type": "function", "function": {
        "name": "get_cancellation_options",
        "description": "Get entitlement options for a cancelled flight.",
        "parameters": {"type": "object", "properties": {
            "pnr": {"type": "string"}, "flight_number": {"type": "string"}},
            "required": ["pnr", "flight_number"]}}},
    {"type": "function", "function": {
        "name": "get_delay_compensation",
        "description": "Get standard delay compensation entitlement for a flight.",
        "parameters": {"type": "object", "properties": {
            "pnr": {"type": "string"}, "flight_number": {"type": "string"}},
            "required": ["pnr", "flight_number"]}}},
    {"type": "function", "function": {
        "name": "check_hotel_request",
        "description": "Check whether a hotel request (full night or delayed-hours) is entitled.",
        "parameters": {"type": "object", "properties": {
            "pnr": {"type": "string"}, "flight_number": {"type": "string"},
            "requesting_full_night": {"type": "boolean"}},
            "required": ["pnr", "flight_number", "requesting_full_night"]}}},
    {"type": "function", "function": {
        "name": "check_fare_difference",
        "description": "Check if a fare-difference amount is within the agent's waiver limit "
                        "(only applies to a VOLUNTARY rebook, not an airline-caused disruption).",
        "parameters": {"type": "object", "properties": {
            "pnr": {"type": "string"}, "amount_inr": {"type": "number"}},
            "required": ["pnr", "amount_inr"]}}},
    {"type": "function", "function": {
        "name": "get_tier_benefit", "description": "Get the customer's loyalty tier benefit.",
        "parameters": {"type": "object", "properties": {
            "pnr": {"type": "string"}}, "required": ["pnr"]}}},
    {"type": "function", "function": {
        "name": "escalate",
        "description": "Escalate the conversation to a human agent. Use for legal threats, "
                        "formal complaints, requests beyond policy limits, or any prohibited action.",
        "parameters": {"type": "object", "properties": {
            "pnr": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["pnr", "reason"]}}},
    {"type": "function", "function": {
        "name": "check_prohibited",
        "description": "Check if a requested action falls under prohibited actions. "
                        "ALWAYS call this before agreeing to ANY request that is not "
                        "explicitly listed in the standard entitlements (e.g. free "
                        "upgrades, extra compensation, cash beyond policy, exceptions "
                        "for self-inflicted/non-airline issues, refunds to a different "
                        "payment method).",
        "parameters": {"type": "object", "properties": {
            "pnr": {"type": "string"},
            "action_key": {
                "type": "string",
                "enum": ["extra_compensation", "non_airline_exception",
                         "legal_threat", "different_payment_method"],
                "description": "extra_compensation: any bonus/upgrade/cash beyond "
                                "stated policy (e.g. free upgrade 'for the trouble'). "
                                "non_airline_exception: exception requested for a "
                                "non-airline-caused issue. legal_threat: legal/formal "
                                "complaint threats. different_payment_method: refund "
                                "requested to a different payment method.",
            }},
            "required": ["pnr", "action_key"]}}},
]

SYSTEM_PROMPT = """You are a customer-facing airline disruption resolution agent.

HARD RULES:
1. You NEVER decide entitlements yourself. You MUST call the provided tools
   for every factual/policy claim (booking status, compensation, refunds,
   fare differences, tier benefits). Never state an entitlement without
   having called the matching tool first.
2. You must always verify identity via a booking reference (PNR) before
   discussing any booking details. Never reveal one customer's data to
   another customer.
3. If a customer mentions legal action, lawyers, suing, or a formal
   complaint, call `escalate` immediately and stop trying to resolve it
   yourself.
4. If a customer asks for something beyond policy (extra compensation, a
   free upgrade, an exception for a non-airline-caused issue, a refund to
   a different payment method, or a fare-difference waiver above the
   limit), you MUST call `check_prohibited` (for upgrades/extra comp/
   exceptions/payment-method changes) or `check_fare_difference` (for
   voluntary higher-fare rebooking) BEFORE responding. Never grant a
   free upgrade or "for the trouble" compensation just because the
   customer is upset — it is never something you can approve yourself.
   Follow the tool's result exactly: if not allowed, explain warmly what
   they ARE entitled to instead, and escalate if the tool says to.
5. Below are sample PRIOR conversations from OTHER, unrelated customers.
   They exist ONLY to show tone and phrasing style. They are NOT a source
   of policy, fact, or precedent. Never cite them, never reuse their
   specific numbers/decisions as if they applied to the current customer.

STYLE SAMPLES (tone reference only, not factual/policy grounding):
{samples}

After each tool call, explain the result to the customer in plain,
empathetic language, and end your reply with a line in this exact format:
[[POLICY: <rule_cited>]]

CRITICAL for the POLICY tag: <rule_cited> must be copied EXACTLY from the
"rule_cited" field returned by the tool(s) you called in this turn — never
invent a name, never reference these numbered HARD RULES above, and never
write things like "Hard Rule 1". If you called more than one tool with
different rule_cited values, join them with "; ", e.g.
[[POLICY: Delay Compensation Rule; Fare Difference Rule]]
""".format(samples=json.dumps(STYLE_SAMPLES_ONLY, indent=2))


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.post("/chat")
def chat(req: ChatRequest):
    history = SESSIONS.setdefault(req.session_id, [{"role": "system", "content": SYSTEM_PROMPT}])

    user_msg = req.message
    if detect_legal_threat(user_msg):
        # Belt-and-braces: force escalation path even if the model misses it.
        tool_escalate("UNKNOWN", "Legal threat / formal complaint detected in customer message.")

    history.append({"role": "user", "content": user_msg})

    # Tool-calling loop
    for _ in range(10):
        resp = client.chat.completions.create(
            model=MODEL, messages=history, tools=TOOLS, tool_choice="auto",
        )
        msg = resp.choices[0].message
        history.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            return {"reply": msg.content, "audit_log": AUDIT_LOG[-5:]}

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            result = TOOL_IMPLS.get(fn_name, lambda **_: {"error": "unknown tool"})(**args)
            history.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(result, default=str),
            })

    return {"reply": "I need to escalate this to a human agent to resolve properly.",
            "audit_log": AUDIT_LOG[-5:]}


@app.get("/audit")
def get_audit():
    return AUDIT_LOG


@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html") as f:
        return f.read()


if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")