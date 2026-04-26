"""
init_render_db.py
Runs on every container startup.
- Creates all DB tables
- If reviews table is empty, seeds 4,605 reviews across 12 weeks
- Inserts 12 weekly_run records
- Inserts 65 theme records (weeks 1-7: 5 themes, weeks 8-12: 6 themes)
"""

import sys
import os
import random
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from storage.db import get_engine
from storage.models import Base, Review, WeeklyRun, Theme

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WEEK_CONFIG = [
    (1,  280, "2026-01-05", {"T2": 6.5}),
    (2,  310, "2026-01-12", {"T2": 6.8}),
    (3,  295, "2026-01-19", {"T1": 7.0}),
    (4,  320, "2026-01-26", {"T2": 7.2}),
    (5,  340, "2026-02-02", {"T2": 7.5}),
    (6,  360, "2026-02-09", {"T2": 8.0}),
    (7,  380, "2026-02-16", {"T2": 8.5}),
    (8,  920, "2026-02-23", {"T2": 9.2}),
    (9,  400, "2026-03-02", {"T4": 7.5}),
    (10, 370, "2026-03-09", {"T4": 7.0}),
    (11, 330, "2026-03-16", {"T5": 6.5}),
    (12, 300, "2026-03-23", {"T3": 6.0}),
]

THEME_LABELS = {
    "T1": ("Onboarding & KYC",            6.8),
    "T2": ("Payments & Withdrawals",       8.0),
    "T3": ("Portfolio & Performance",      4.2),
    "T4": ("App Stability & UX",           7.2),
    "T5": ("Customer Support",             5.6),
    "T6": ("Fraud & Security Concerns",    5.8),
}

THEME_DETAILS = {
    "T1": {
        "keywords": ["kyc", "verification", "account", "documents", "onboarding"],
        "quotes": [
            "KYC verification stuck for 3 days. No update from team.",
            "Account blocked suddenly with no email or SMS notification.",
        ],
        "action": "Audit KYC document pipeline and add real-time status updates",
    },
    "T2": {
        "keywords": ["payment", "withdrawal", "upi", "transaction", "money"],
        "quotes": [
            "Money deducted from bank but investment not done.",
            "Withdrawal pending for 5 days. Urgently need money.",
        ],
        "action": "Investigate payment gateway delays and add proactive status notifications",
    },
    "T3": {
        "keywords": ["portfolio", "returns", "p&l", "holdings", "performance"],
        "quotes": [
            "P&L calculation is wrong after latest update.",
            "Returns shown are incorrect after portfolio sync.",
        ],
        "action": "Recalculate portfolio returns and add data validation checks",
    },
    "T4": {
        "keywords": ["crash", "slow", "login", "otp", "app"],
        "quotes": [
            "App crashes every time during market hours.",
            "OTP not received on registered mobile number.",
        ],
        "action": "Fix app stability issues and optimise performance during peak hours",
    },
    "T5": {
        "keywords": ["support", "customer", "response", "ticket", "chat"],
        "quotes": [
            "Customer support completely useless. Only bots reply.",
            "Chat support takes forever. Issue unresolved after follow-ups.",
        ],
        "action": "Add human escalation path and reduce first-response time to under 2 hours",
    },
    "T6": {
        "keywords": ["fraud", "security", "suspicious", "unauthorised", "hack"],
        "quotes": [
            "Suspicious transaction appeared on my account without my knowledge.",
            "Unauthorised login attempt — security needs improvement.",
        ],
        "action": "Strengthen 2FA enforcement and add anomaly detection on login events",
    },
}

REVIEW_POOL = [
    (1, "KYC verification stuck for 3 days. Documents uploaded but no update from team."),
    (1, "Money deducted from bank but investment not done. Transaction shows failed."),
    (1, "App crashes every time during market hours. Cannot place orders at all."),
    (1, "Withdrawal pending for 5 days. Urgently need money but no response from support."),
    (1, "UPI payment failed but amount debited from account. Need immediate refund."),
    (1, "Customer support completely useless. Only bots reply no human agent available."),
    (1, "Account blocked suddenly with no email or SMS notification. Cannot login."),
    (1, "Redemption amount not received after 7 days. Extremely poor payment processing."),
    (2, "App is extremely slow. Takes 30 seconds to load portfolio page every time."),
    (2, "OTP not received on registered mobile number. Cannot login to account."),
    (2, "P&L calculation is wrong after latest update. Returns shown are incorrect."),
    (2, "Bank account linking fails every time. Very difficult to add new bank."),
    (2, "Chat support takes forever. Issue unresolved after multiple follow-ups."),
    (2, "Nomination update not working. Getting error message every single time."),
    (3, "App is okay but customer support needs major improvement for all users."),
    (3, "Returns tracking decent but UI could be much better and more intuitive."),
    (3, "Some features good but app crashes occasionally during peak trading hours."),
    (4, "Good app overall but withdrawal process could be faster and smoother."),
    (4, "Nice interface and easy to use for mutual fund investment and SIP tracking."),
    (5, "Best investment app in India. Simple interface and great mutual fund options."),
    (5, "Excellent app for beginners. Started investment journey with Groww. Satisfied."),
    (5, "Love zero commission on direct mutual funds. Saving a lot on charges overall."),
    (5, "SIP setup is very easy and smooth. Returns tracking is excellent. Recommend."),
    (5, "Fast and reliable platform. Best app for stock trading and mutual funds."),
]

SUFFIXES = [
    "", "", "",
    " Please fix this urgently.",
    " Very frustrating experience.",
    " Not acceptable at all.",
    " Extremely disappointed.",
    " Hoping for a quick resolution.",
    " Will uninstall if not fixed.",
]

STORES    = ["ios", "android"]
VERSIONS  = ["3.2.1", "3.2.2", "3.3.0", "3.3.1", "3.4.0", "3.4.1"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _review_id(week: int, idx: int, text: str) -> str:
    key = f"{week}_{idx}_{text[:40]}"
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def _rating_weights(hot_urgency: float):
    if hot_urgency >= 8.5:
        return [40, 30, 12, 10, 8]
    if hot_urgency >= 7.5:
        return [30, 28, 18, 12, 12]
    if hot_urgency >= 6.5:
        return [22, 24, 22, 16, 16]
    return [12, 18, 25, 22, 23]


def _urgency_for(t_id: str, hot_theme: str, hot_val: float, week_num: int) -> float:
    _, base = THEME_LABELS[t_id]
    if t_id == hot_theme:
        return round(hot_val, 1)
    noise = random.uniform(-0.6, 0.6)
    week_drift = (week_num - 1) * 0.04
    return round(max(1.0, min(10.0, base + noise + week_drift)), 1)


def _trend(urgency: float, prev_urgency: float | None) -> str:
    if prev_urgency is None:
        return "stable"
    delta = urgency - prev_urgency
    if delta >= 0.4:
        return "worsening"
    if delta <= -0.4:
        return "improving"
    return "stable"


# ---------------------------------------------------------------------------
# Main seeding logic
# ---------------------------------------------------------------------------

def seed():
    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        existing = session.query(Review).count()
        if existing > 0:
            print(f"[init_render_db] DB already has {existing} reviews — skipping seed.")
            return

        print("[init_render_db] Empty DB detected — seeding full dataset …")
        random.seed(42)

        # ── 1. Weekly runs ────────────────────────────────────────────────
        run_ids: dict[int, int] = {}
        for week_num, vol, date_str, hot_themes in WEEK_CONFIG:
            week_date = datetime.strptime(date_str, "%Y-%m-%d")
            run = WeeklyRun(
                run_date=week_date,
                week_number=week_num,
                year=2026,
                reviews_fetched=vol,
                reviews_kept=int(vol * 0.92),
                english_count=int(vol * 0.87),
                noise_dropped=int(vol * 0.08),
                themes_found=5,
                status="completed",
                algorithm_used="llm",
                surge_mode=(vol > 500),
            )
            session.add(run)
            session.flush()
            run_ids[week_num] = run.id

        # ── 2. Reviews ────────────────────────────────────────────────────
        pool_by_rating: dict[int, list] = {}
        for rating in range(1, 6):
            pool_by_rating[rating] = [r[1] for r in REVIEW_POOL if r[0] == rating]

        total_reviews = 0
        for week_num, vol, date_str, hot_themes in WEEK_CONFIG:
            hot_theme  = list(hot_themes.keys())[0]
            hot_val    = list(hot_themes.values())[0]
            week_date  = datetime.strptime(date_str, "%Y-%m-%d")
            weights    = _rating_weights(hot_val)

            batch = []
            for i in range(vol):
                rating   = random.choices([1, 2, 3, 4, 5], weights=weights)[0]
                texts    = pool_by_rating.get(rating, pool_by_rating[1])
                base_txt = random.choice(texts)
                full_txt = base_txt + random.choice(SUFFIXES)
                day_off  = random.randint(0, 6)
                rev_date = (week_date + timedelta(days=day_off)).strftime("%Y-%m-%d")

                batch.append(Review(
                    review_id         = _review_id(week_num, i, full_txt),
                    store             = random.choice(STORES),
                    rating            = rating,
                    title             = None,
                    text              = full_txt,
                    date              = rev_date,
                    app_version       = random.choice(VERSIONS),
                    language_detected = "en",
                    language_confidence = 0.99,
                    is_duplicate      = False,
                    pii_stripped      = True,
                    week_number       = week_num,
                ))

            session.add_all(batch)
            total_reviews += vol
            print(f"  week {week_num:02d}: {vol} reviews inserted")

        # ── 3. Themes (65 total: weeks 1-7 → 5 each, weeks 8-12 → 6 each) ─
        base_themes  = ["T1", "T2", "T3", "T4", "T5"]
        surge_themes = base_themes + ["T6"]
        prev_urgency: dict[str, float] = {}
        total_themes = 0

        for week_num, vol, date_str, hot_themes in WEEK_CONFIG:
            hot_theme = list(hot_themes.keys())[0]
            hot_val   = list(hot_themes.values())[0]
            theme_set = surge_themes if week_num >= 8 else base_themes

            for t_id in theme_set:
                label, _ = THEME_LABELS[t_id]
                details  = THEME_DETAILS[t_id]
                urgency  = _urgency_for(t_id, hot_theme, hot_val, week_num)
                trend    = _trend(urgency, prev_urgency.get(t_id))
                prev_urgency[t_id] = urgency
                sentiment = round(max(-1.0, min(1.0, -(urgency / 10.0) + random.uniform(-0.05, 0.05))), 2)

                session.add(Theme(
                    run_id         = run_ids[week_num],
                    theme_id       = t_id,
                    label          = label,
                    urgency_score  = urgency,
                    sentiment_score= sentiment,
                    volume         = max(10, int(vol * random.uniform(0.12, 0.30))),
                    trend_direction= trend,
                    top_quote      = random.choice(details["quotes"]),
                    keywords       = details["keywords"],
                    action_idea    = details["action"],
                    labeling_method= "llm",
                ))
                total_themes += 1

        session.commit()
        print(f"\n[init_render_db] Seed complete:")
        print(f"  weekly_runs : 12")
        print(f"  reviews     : {total_reviews}")
        print(f"  themes      : {total_themes}")
        print("INIT SCRIPT READY")


if __name__ == "__main__":
    seed()
