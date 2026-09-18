"""
Deterministic policy engine. The LLM NEVER decides entitlements directly —
it calls these functions and reports the result. This keeps every decision
auditable and testable independent of the model.
"""

from dataclasses import dataclass, field
from data import FARE_DIFFERENCE_WAIVER_LIMIT


@dataclass
class PolicyResult:
    allowed: bool
    action: str
    reason: str
    rule_cited: str
    escalate: bool = False
    escalation_reason: str = ""


# ---------- Cancellation ----------

def cancellation_options(flight: dict) -> PolicyResult:
    """Airline-caused cancellation -> free rebooking within 24h OR full refund, customer's choice."""
    if flight["status"] != "cancelled":
        return PolicyResult(
            allowed=False, action="cancellation_options",
            reason="Flight is not cancelled; this rule does not apply.",
            rule_cited="Cancellation Rebooking Rule",
        )
    return PolicyResult(
        allowed=True, action="cancellation_options",
        reason="Airline-caused cancellation. Customer may choose free rebooking "
               "on the next available flight within 24 hours, or a full refund "
               "to the original payment method (processed within 7 business days).",
        rule_cited="Cancellation Rebooking Rule; Refund Processing Rule",
    )


# ---------- Delay compensation ----------

def delay_compensation(delay_hours: float) -> PolicyResult:
    if delay_hours <= 0:
        return PolicyResult(
            allowed=False, action="delay_compensation",
            reason="No delay recorded; no compensation applies.",
            rule_cited="Delay Compensation Rule",
        )
    if delay_hours < 3:
        return PolicyResult(
            allowed=True, action="delay_compensation",
            reason="Delay under 3 hours: ₹500 meal voucher.",
            rule_cited="Delay Compensation Rule",
        )
    if delay_hours <= 5:
        return PolicyResult(
            allowed=True, action="delay_compensation",
            reason="Delay more than 3 hours: meal voucher + lounge access.",
            rule_cited="Delay Compensation Rule",
        )
    return PolicyResult(
        allowed=True, action="delay_compensation",
        reason="Delay more than 5 hours: meal voucher + lounge access + hotel "
               "accommodation, covering only the delayed hours (not a full night's stay).",
        rule_cited="Delay Compensation Rule",
    )


def hotel_entitlement(delay_hours: float) -> PolicyResult:
    """Explicit check for a hotel ask — used when a customer specifically requests one."""
    if delay_hours > 5:
        return PolicyResult(
            allowed=True, action="hotel_accommodation",
            reason="Delay exceeds 5 hours: hotel accommodation is covered, but "
                   "only for the delayed-hours portion — not a full night's stay.",
            rule_cited="Delay Compensation Rule",
        )
    return PolicyResult(
        allowed=False, action="hotel_accommodation",
        reason=f"Delay of {delay_hours}h does not meet the 5-hour threshold "
               "required for hotel accommodation.",
        rule_cited="Delay Compensation Rule",
    )


def full_night_hotel_request() -> PolicyResult:
    """A customer asking for a FULL NIGHT stay instead of delayed-hours-only coverage."""
    return PolicyResult(
        allowed=False, action="full_night_hotel",
        reason="Policy covers only the delayed-hours portion of a hotel stay, "
               "not a full night's accommodation.",
        rule_cited="Delay Compensation Rule",
    )


# ---------- Fare difference / voluntary rebook ----------

def fare_difference_check(amount_inr: float) -> PolicyResult:
    """
    Applies when a customer VOLUNTARILY rebooks to a higher-fare flight
    (i.e. their own flight was not cancelled by the airline).
    """
    if amount_inr <= FARE_DIFFERENCE_WAIVER_LIMIT:
        return PolicyResult(
            allowed=True, action="fare_difference",
            reason=f"Fare difference of ₹{amount_inr} is within the agent's "
                   f"waiver limit of ₹{FARE_DIFFERENCE_WAIVER_LIMIT}.",
            rule_cited="Fare Difference Rule",
        )
    return PolicyResult(
        allowed=False, action="fare_difference",
        reason=f"Fare difference of ₹{amount_inr} exceeds the ₹{FARE_DIFFERENCE_WAIVER_LIMIT} "
               "agent waiver limit and requires supervisor approval.",
        rule_cited="Fare Difference Rule",
        escalate=True,
        escalation_reason="Fare difference above agent waiver limit — needs supervisor approval.",
    )


# ---------- Loyalty tier ----------

def tier_benefit(tier: str) -> PolicyResult:
    return PolicyResult(
        allowed=True, action="tier_benefit",
        reason=f"{tier} tier gets priority rebooking (first access to next-available "
               "seats), but no additional compensation beyond the standard policy.",
        rule_cited="Loyalty Tier Rule",
    )


# ---------- Prohibited / must-escalate actions ----------

PROHIBITED_KEYWORDS = {
    "extra_compensation": "Approving compensation beyond stated policy amounts.",
    "non_airline_exception": "Making exceptions for non-airline-caused disruptions "
                              "(e.g. customer missed the flight).",
    "legal_threat": "Threats of legal action or formal complaints must be escalated immediately.",
    "different_payment_method": "Refunds cannot be processed to a different payment method "
                                 "than the original.",
}


def check_prohibited(action_key: str) -> PolicyResult:
    if action_key in PROHIBITED_KEYWORDS:
        return PolicyResult(
            allowed=False, action=action_key,
            reason=PROHIBITED_KEYWORDS[action_key],
            rule_cited="Allowed vs. Prohibited Actions",
            escalate=True,
            escalation_reason=PROHIBITED_KEYWORDS[action_key],
        )
    return PolicyResult(
        allowed=True, action=action_key,
        reason="No prohibition matched.",
        rule_cited="Allowed vs. Prohibited Actions",
    )


def detect_legal_threat(message: str) -> bool:
    triggers = ["legal action", "lawyer", "sue", "formal complaint", "consumer court", "legal notice"]
    m = message.lower()
    return any(t in m for t in triggers)