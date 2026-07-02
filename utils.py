import json
from datetime import datetime, timedelta
from database import get_setting, save_setting

ALL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
QUICK_AMOUNTS = [5, 10, 20]
MAX_TIMES_PER_DAY = 8

def to_24h(hour_12, minute, period):
    hour_12 = int(hour_12)
    minute = int(minute)
    if period == "AM":
        hour_24 = 0 if hour_12 == 12 else hour_12
    else:
        hour_24 = 12 if hour_12 == 12 else hour_12 + 12
    return f"{hour_24:02d}:{minute:02d}"

def from_24h(time_str):
    try:
        h, m = (int(x) for x in time_str.split(":"))
    except Exception:
        h, m = 18, 0
    period = "AM" if h < 12 else "PM"
    hour_12 = h % 12
    if hour_12 == 0:
        hour_12 = 12
    return hour_12, m, period

def format_12h(time_str):
    h, m, p = from_24h(time_str)
    return f"{h}:{m:02d} {p}"

def get_schedule_map():
    raw = get_setting("schedule_map", "")
    if raw:
        try:
            data = json.loads(raw)
            return {
                day: sorted(set(t for t in times if isinstance(t, str)))
                for day, times in data.items() if day in ALL_DAYS
            }
        except Exception:
            pass
    return {}

def save_schedule_map(schedule_map):
    cleaned = {day: sorted(set(times)) for day, times in schedule_map.items() if times}
    save_setting("schedule_map", json.dumps(cleaned))

def next_occurrence(weekday_index, hour, minute):
    now = datetime.now()
    days_ahead = (weekday_index - now.weekday()) % 7
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate