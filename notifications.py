try:
    from flet_android_notifications import FletAndroidNotifications
    NOTIFICATIONS_AVAILABLE = True
except Exception:
    NOTIFICATIONS_AVAILABLE = False

from datetime import datetime, timedelta
from database import get_setting
from utils import ALL_DAYS, MAX_TIMES_PER_DAY, get_schedule_map, next_occurrence

def setup_notifications(page):
    notifications = FletAndroidNotifications() if NOTIFICATIONS_AVAILABLE else None
    if notifications:
        page.services.append(notifications)
    return notifications

async def refresh_scheduled_notifications(page, notifications):
    if not notifications:
        return
    try:
        await notifications.request_permissions()
    except Exception:
        pass
    try:
        await notifications.request_exact_alarm_permission()
    except Exception:
        pass
    schedule_map = get_schedule_map()
    for weekday_index, day in enumerate(ALL_DAYS):
        times = schedule_map.get(day, [])
        for slot in range(MAX_TIMES_PER_DAY):
            notif_id = (weekday_index + 1) * 100 + slot
            try:
                if slot < len(times):
                    hour, minute = (int(x) for x in times[slot].split(":"))
                    when = next_occurrence(weekday_index, hour, minute)
                    await notifications.schedule_notification(
                        notification_id=notif_id,
                        title="⏰ Time to save!",
                        body="Don't forget to save today.",
                        scheduled_time=when,
                        match_date_time_components="day_of_week_and_time",
                    )
                else:
                    await notifications.cancel(notif_id)
            except Exception:
                pass

async def fire_goal_reached_notification(notifications, goal_id, goal_name):
    if not notifications:
        return
    try:
        await notifications.schedule_notification(
            notification_id=9000 + goal_id,
            title="🎉 Goal Reached!",
            body=f"You've saved enough for: {goal_name}!",
            scheduled_time=datetime.now() + timedelta(seconds=1),
        )
    except Exception:
        pass