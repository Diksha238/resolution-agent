"""
Scenario tests — these encode the "correct" answers for the three
required cases. Run with: python3 test_scenarios.py
"""

from data import BOOKINGS, CUSTOMERS, FARE_DIFFERENCE_WAIVER_LIMIT
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


def test_priya_cancellation_and_refund_choice():
    """Scenario 1: Priya (Gold, SK4821X) — SK-204 cancelled."""
    flight = BOOKINGS["SK4821X"][0]
    result = cancellation_options(flight)
    assert result.allowed is True
    assert "refund" in result.reason.lower()
    assert "rebook" in result.reason.lower()
    print("PASS: Priya gets free rebooking OR full refund (her choice)")


def test_priya_upgrade_request_is_prohibited():
    """Priya's ask for a free business-class upgrade on the UNAFFECTED return leg."""
    result = check_prohibited("extra_compensation")
    assert result.allowed is False
    assert result.escalate is True
    print("PASS: Free business-class upgrade is correctly refused/escalated")


def test_priya_tier_gives_priority_not_extra_comp():
    result = tier_benefit(CUSTOMERS["SK4821X"]["tier"])
    assert "no additional compensation" in result.reason.lower()
    print("PASS: Gold tier = priority rebooking only, no bonus comp")


def test_arvind_delay_gets_voucher_and_lounge_only():
    """Scenario 2: Arvind (Silver, TR1190B) — 4h delay."""
    flight = BOOKINGS["TR1190B"][0]
    result = delay_compensation(flight["delay_hours"])
    assert result.allowed is True
    assert "lounge" in result.reason.lower()
    assert "hotel" not in result.reason.lower()
    print("PASS: Arvind (4h delay) gets voucher + lounge, NOT hotel")


def test_arvind_hotel_request_is_declined():
    flight = BOOKINGS["TR1190B"][0]
    result = hotel_entitlement(flight["delay_hours"])
    assert result.allowed is False
    print("PASS: Arvind's hotel request correctly declined (under 5h threshold)")


def test_meher_delay_qualifies_for_partial_hotel():
    """Scenario 3: Meher (Platinum, WL7742) — 6h delay."""
    flight = BOOKINGS["WL7742"][0]
    result = delay_compensation(flight["delay_hours"])
    assert result.allowed is True
    assert "hotel" in result.reason.lower()
    assert "not a full night" in result.reason.lower()
    print("PASS: Meher (6h delay) gets hotel for delayed-hours only")


def test_meher_full_night_request_is_declined():
    result = full_night_hotel_request()
    assert result.allowed is False
    print("PASS: Meher's full-night-stay request correctly declined")


def test_meher_fare_difference_requires_escalation():
    """₹2,000 fare difference exceeds the ₹1,500 agent waiver limit."""
    result = fare_difference_check(2000)
    assert result.allowed is False
    assert result.escalate is True
    print(f"PASS: ₹2000 fare diff > ₹{FARE_DIFFERENCE_WAIVER_LIMIT} limit -> escalated to supervisor")


def test_fare_difference_within_limit_is_allowed():
    """Sanity check: amounts under the limit should NOT escalate."""
    result = fare_difference_check(1000)
    assert result.allowed is True
    assert result.escalate is False
    print("PASS: ₹1000 fare diff is within agent limit -> no escalation needed")


def test_legal_threat_detection():
    assert detect_legal_threat("I'm going to consider legal action") is True
    assert detect_legal_threat("This delay is really annoying") is False
    print("PASS: Legal threat detection works")


if __name__ == "__main__":
    tests = [
        test_priya_cancellation_and_refund_choice,
        test_priya_upgrade_request_is_prohibited,
        test_priya_tier_gives_priority_not_extra_comp,
        test_arvind_delay_gets_voucher_and_lounge_only,
        test_arvind_hotel_request_is_declined,
        test_meher_delay_qualifies_for_partial_hotel,
        test_meher_full_night_request_is_declined,
        test_meher_fare_difference_requires_escalation,
        test_fare_difference_within_limit_is_allowed,
        test_legal_threat_detection,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FAIL: {t.__name__} -> {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")