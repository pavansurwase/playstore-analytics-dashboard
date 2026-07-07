"""
timegate.py
-----------
IST time-window gating shared by every task.

Each internship task is only allowed to render inside a specific IST window.
`in_window(start, end)` returns True when the current IST hour is within
[start, end)  (end-exclusive, so an 8 PM cut-off hides the chart at 20:00).
"""

from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

# start_hour, end_hour (24h) per task
WINDOWS = {
    1: (15, 17),  # 3 PM - 5 PM
    2: (18, 20),  # 6 PM - 8 PM
    3: (13, 14),  # 1 PM - 2 PM
    4: (18, 21),  # 6 PM - 9 PM
    5: (17, 19),  # 5 PM - 7 PM
    6: (16, 18),  # 4 PM - 6 PM
}


def now_ist() -> datetime:
    return datetime.now(IST)


def in_window(start_hour: int, end_hour: int, now: datetime | None = None) -> bool:
    now = now or now_ist()
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    return start_hour <= now.hour < end_hour


def window_label(task_id: int) -> str:
    s, e = WINDOWS[task_id]
    def fmt(h):
        ampm = "AM" if h < 12 else "PM"
        hr = h % 12 or 12
        return f"{hr} {ampm}"
    return f"{fmt(s)} – {fmt(e)} IST"


def task_visible(task_id: int, now: datetime | None = None) -> bool:
    s, e = WINDOWS[task_id]
    return in_window(s, e, now)
