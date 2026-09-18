"""
Hardcoded data pack. Source: Assignment 3 Data Pack (AIONOS).
Exercise date: Wed 23 Sep 2026.
"""

CUSTOMERS = {
    "SK4821X": {
        "name": "Priya Nair",
        "tier": "Gold",
        "pnr": "SK4821X",
        "email": "priya.nair@example.com",
        "phone": "+91-98xxxxxxx1",
        "history": {"flights_last_12mo": 6, "prior_complaints": 1,
                     "notes": "delayed baggage, resolved with voucher"},
    },
    "TR1190B": {
        "name": "Arvind Kulkarni",
        "tier": "Silver",
        "pnr": "TR1190B",
        "email": "arvind.kulkarni@example.com",
        "phone": "+91-98xxxxxxx2",
        "history": {"flights_last_12mo": 3, "prior_complaints": 0, "notes": None},
    },
    "WL7742": {
        "name": "Meher Kaur",
        "tier": "Platinum",
        "pnr": "WL7742",
        "email": "meher.kaur@example.com",
        "phone": "+91-98xxxxxxx3",
        "history": {"flights_last_12mo": 10, "prior_complaints": 1,
                     "notes": "overbooking, resolved with tier-status upgrade"},
    },
}

# Each booking keyed by pnr -> list of flight legs
BOOKINGS = {
    "SK4821X": [
        {
            "flight": "SK-204",
            "route": "Delhi -> Goa",
            "date": "2026-09-23",
            "scheduled_departure": "18:40",
            "status": "cancelled",
            "status_reason": "operational reasons",
            "delay_hours": 0,
        },
        {
            "flight": "Return",
            "route": "Goa -> Delhi",
            "date": "2026-09-25",
            "scheduled_departure": "16:20",
            "status": "unaffected",
            "status_reason": None,
            "delay_hours": 0,
        },
    ],
    "TR1190B": [
        {
            "flight": "SK-118",
            "route": "Mumbai -> Bengaluru",
            "date": "2026-09-23",
            "scheduled_departure": "07:10",
            "new_departure": "11:10",
            "status": "delayed",
            "status_reason": None,
            "delay_hours": 4,
        },
    ],
    "WL7742": [
        {
            "flight": "SK-305",
            "route": "Delhi -> Hyderabad",
            "date": "2026-09-23",
            "scheduled_departure": "14:00",
            "new_departure": "20:00",
            "status": "delayed",
            "status_reason": None,
            "delay_hours": 6,
        },
    ],
}

# Sample prior conversations — TONE/STYLE REFERENCE ONLY.
STYLE_SAMPLES_ONLY = [
    {
        "customer": "I completely understand the frustration...",
        "agent": "I completely understand the frustration — I can see flight "
                 "SK-190 was cancelled due to operational reasons. I can rebook "
                 "you on the next available flight at no extra cost, or process "
                 "a full refund. Which would you prefer?",
    },
    {
        "customer": "I want compensation, this delay ruined my whole day.",
        "agent": "I'm sorry for the disruption. Your flight was delayed 3 hours "
                 "40 minutes, which qualifies for a meal voucher and lounge "
                 "access under our policy. I've applied both to your account now.",
    },
    {
        "customer": "This is unacceptable, I'm going to file a formal complaint "
                     "and consider legal action.",
        "agent": "I hear you, and I'm sorry this has been such a frustrating "
                 "experience. I want to make sure this gets the right attention "
                 "— I'm escalating this to our specialist support team right "
                 "now, and they'll reach out to you directly.",
    },
]

FARE_DIFFERENCE_WAIVER_LIMIT = 1500  