import flet as ft
import sqlite3
import json
from datetime import datetime, timedelta

try:
    from flet_android_notifications import FletAndroidNotifications
    NOTIFICATIONS_AVAILABLE = True
except Exception:
    NOTIFICATIONS_AVAILABLE = False

def init_db():
    conn = sqlite3.connect("savings_app.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL,
            type TEXT,
            description TEXT,
            date TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            target_amount REAL,
            reached INTEGER DEFAULT 0,
            created_date TEXT
        )
    """)
    conn.commit()
    return conn

conn = init_db()

ALL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
QUICK_AMOUNTS = [5, 10, 20]
MAX_TIMES_PER_DAY = 8


def main(page: ft.Page):
    page.title = "SaveMate"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.GREEN)
    page.window.width = 390
    page.window.height = 844
    page.window.resizable = False

    notifications = FletAndroidNotifications() if NOTIFICATIONS_AVAILABLE else None
    if notifications:
        page.services.append(notifications)

    def open_dialog(dialog_control):
        page.show_dialog(dialog_control)

    def close_dialog(dialog_control):
        page.pop_dialog()

    def show_snack(message, bgcolor=None):
        page.show_dialog(ft.SnackBar(content=ft.Text(message), bgcolor=bgcolor))

    def get_total_savings():
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM history")
        res = cursor.fetchone()[0]
        return res if res is not None else 0.0

    def get_history():
        cursor = conn.cursor()
        cursor.execute("SELECT amount, type, description, date FROM history ORDER BY id DESC")
        return cursor.fetchall()

    def get_setting(key, default=""):
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        res = cursor.fetchone()
        return res[0] if res else default

    def save_setting(key, value):
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()

    def get_goals():
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, target_amount, reached, created_date FROM goals ORDER BY id DESC")
        return cursor.fetchall()

    def add_goal_to_db(name, target_amount):
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO goals (name, target_amount, reached, created_date) VALUES (?, ?, 0, ?)",
            (name, target_amount, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()

    def delete_goal_from_db(goal_id):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM goals WHERE id=?", (goal_id,))
        conn.commit()

    def mark_goal_reached(goal_id):
        cursor = conn.cursor()
        cursor.execute("UPDATE goals SET reached=1 WHERE id=?", (goal_id,))
        conn.commit()

    def log_goal_completion_to_history(name, target_amount):
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO history (amount, type, description, date) VALUES (?, 'Goal Achieved', ?, ?)",
            (0, f"🏁 Achieved goal: {name} (₱{target_amount:,.2f})", datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()

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

    async def refresh_scheduled_notifications():
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

    page.run_task(refresh_scheduled_notifications)

    async def fire_goal_reached_notification(goal_id, goal_name):
        """Fire an Android push notification when a goal is reached."""
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

    def check_goals_reached():
        """Check all un-reached goals and fire notifications for any that are now met."""
        current_savings = get_total_savings()
        goals = get_goals()
        for goal_id, name, target, reached, _ in goals:
            if reached == 0 and current_savings >= target:
                mark_goal_reached(goal_id)
                show_snack(f"🎉 Goal reached: {name}! You've saved ₱{target:,.2f}!", bgcolor=ft.Colors.GREEN_800)
                page.run_task(fire_goal_reached_notification, goal_id, name)

    def update_dashboard():
        balance_text.value = f"₱{get_total_savings():,.2f}"
        history_list.controls.clear()
        transactions = get_history()

        if not transactions:
            history_list.controls.append(
                ft.Text("No transactions yet.", color=ft.Colors.GREY_500, size=14)
            )
        else:
            for amount, t_type, desc, date_str in transactions:
                if t_type == "Goal Achieved":
                    history_list.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.EMOJI_EVENTS, color=ft.Colors.AMBER_400),
                                ft.Column([
                                    ft.Text(desc, weight=ft.FontWeight.BOLD, size=14),
                                    ft.Text(date_str, size=11, color=ft.Colors.GREY_400),
                                ], expand=True, spacing=2),
                            ], alignment=ft.MainAxisAlignment.START),
                            padding=10,
                            border_radius=8,
                            bgcolor=ft.Colors.SURFACE_CONTAINER,
                        )
                    )
                    continue
                is_deposit = t_type == "Deposit"
                history_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(
                                ft.Icons.ARROW_UPWARD if is_deposit else ft.Icons.ARROW_DOWNWARD,
                                color=ft.Colors.GREEN_400 if is_deposit else ft.Colors.RED_400
                            ),
                            ft.Column([
                                ft.Text(desc, weight=ft.FontWeight.BOLD, size=14),
                                ft.Text(date_str, size=11, color=ft.Colors.GREY_400),
                            ], expand=True, spacing=2),
                            ft.Text(
                                f"+ ₱{amount:,.2f}" if is_deposit else f"- ₱{abs(amount):,.2f}",
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREEN_400 if is_deposit else ft.Colors.RED_400
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=10,
                        border_radius=8,
                        bgcolor=ft.Colors.SURFACE_CONTAINER
                    )
                )
        check_goals_reached()
        update_goals_view()
        page.update()

    def update_goals_view():
        """Rebuild the goals list UI."""
        goals_list.controls.clear()
        goals = get_goals()
        current_savings = get_total_savings()

        if not goals:
            goals_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.FLAG_OUTLINED, size=48, color=ft.Colors.GREY_600),
                        ft.Text("No goals yet", size=16, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
                        ft.Text("Tap the + button to add your first goal.", size=13, color=ft.Colors.GREY_600),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                )
            )
        else:
            for goal_id, name, target, reached, created_date in goals:
                progress = min(current_savings / target, 1.0) if target > 0 else 0
                is_reached = reached == 1 or current_savings >= target
                bar_color = ft.Colors.GREEN_400 if is_reached else ft.Colors.AMBER_400

                goal_card = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE if is_reached else ft.Icons.FLAG_CIRCLE,
                                color=ft.Colors.GREEN_400 if is_reached else ft.Colors.AMBER_400,
                                size=28,
                            ),
                            ft.Column([
                                ft.Text(name, weight=ft.FontWeight.BOLD, size=15),
                                ft.Text(f"Created {created_date}", size=10, color=ft.Colors.GREY_500),
                            ], expand=True, spacing=2),
                            ft.IconButton(
                                ft.Icons.CHECK_CIRCLE_OUTLINE,
                                icon_size=20,
                                icon_color=ft.Colors.GREEN_400,
                                tooltip="Mark as completed",
                                on_click=lambda e, gid=goal_id, gname=name, gtarget=target: handle_complete_goal(gid, gname, gtarget),
                            ),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                icon_size=20,
                                icon_color=ft.Colors.RED_300,
                                tooltip="Delete goal",
                                on_click=lambda e, gid=goal_id, gname=name: confirm_delete_goal(gid, gname),
                            ),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.Text(
                                f"₱{current_savings:,.2f}",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREEN_400 if is_reached else ft.Colors.WHITE,
                            ),
                            ft.Text(
                                f"/ ₱{target:,.2f}",
                                size=13,
                                color=ft.Colors.GREY_400,
                            ),
                        ], spacing=4),
                        ft.ProgressBar(
                            value=progress,
                            color=bar_color,
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                            bar_height=8,
                            border_radius=4,
                        ),
                        ft.Row([
                            ft.Text(
                                f"{progress * 100:.0f}%",
                                size=12,
                                color=ft.Colors.GREY_400,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    "✅ Reached!" if is_reached else f"₱{max(target - current_savings, 0):,.2f} to go",
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.GREEN_400 if is_reached else ft.Colors.AMBER_300,
                                ),
                            ),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], spacing=8),
                    padding=14,
                    border_radius=12,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                )
                goals_list.controls.append(goal_card)

    def set_quick_amount(amount):
        amount_input.value = str(amount)
        amount_input.error_text = None
        page.update()

    def handle_add_savings(e):
        try:
            amt = float(amount_input.value)
            desc = desc_input.value if desc_input.value else "Manual Deposit"
            if amt <= 0:
                raise ValueError

            cursor = conn.cursor()
            cursor.execute("INSERT INTO history (amount, type, description, date) VALUES (?, 'Deposit', ?, ?)",
                           (amt, desc, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()

            amount_input.value = ""
            desc_input.value = ""
            amount_input.error_text = None
            close_dialog(add_dialog)
            update_dashboard()
        except ValueError:
            amount_input.error_text = "Please enter a valid amount"
            page.update()

    def handle_adjust_balance(e):
        try:
            target_balance = float(adjust_input.value)
            current_balance = get_total_savings()
            difference = target_balance - current_balance

            if difference != 0:
                t_type = "Deposit" if difference > 0 else "Withdrawal"
                cursor = conn.cursor()
                cursor.execute("INSERT INTO history (amount, type, description, date) VALUES (?, ?, 'Balance Adjustment', ?)",
                               (difference, t_type, datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit()

            adjust_input.value = ""
            adjust_input.error_text = None
            close_dialog(adjust_dialog)
            update_dashboard()
        except ValueError:
            adjust_input.error_text = "Please enter a valid balance"
            page.update()

    def handle_log_spend(e):
        try:
            amt = float(spend_amount_input.value)
            desc = spend_desc_input.value if spend_desc_input.value else "Spending"
            if amt <= 0:
                raise ValueError

            current = get_total_savings()
            if amt > current:
                spend_amount_input.error_text = f"Can't spend more than ₱{current:,.2f}"
                page.update()
                return

            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO history (amount, type, description, date) VALUES (?, 'Withdrawal', ?, ?)",
                (-amt, desc, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            conn.commit()

            spend_amount_input.value = ""
            spend_desc_input.value = ""
            spend_amount_input.error_text = None
            close_dialog(spend_dialog)
            update_dashboard()
        except ValueError:
            spend_amount_input.error_text = "Please enter a valid amount"
            page.update()

    def handle_reset_balance(e):
        if full_reset_checkbox.value:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history")
            cursor.execute("DELETE FROM goals")
            conn.commit()
            full_reset_checkbox.value = False
            close_dialog(reset_dialog)
            update_dashboard()
            show_snack("Entire database wiped: all history and goals deleted.")
            return

        current = get_total_savings()
        if current != 0:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO history (amount, type, description, date) VALUES (?, 'Withdrawal', 'Balance Reset to ₱0', ?)",
                (-current, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            conn.commit()
        close_dialog(reset_dialog)
        update_dashboard()
        show_snack("Balance has been reset to ₱0.00. History preserved.")

    def handle_add_goal(e):
        goal_name = goal_name_input.value.strip() if goal_name_input.value else ""
        if not goal_name:
            goal_name_input.error_text = "Please enter a goal name"
            page.update()
            return
        try:
            target = float(goal_amount_input.value)
            if target <= 0:
                raise ValueError
        except (ValueError, TypeError):
            goal_amount_input.error_text = "Please enter a valid amount"
            page.update()
            return

        add_goal_to_db(goal_name, target)
        goal_name_input.value = ""
        goal_amount_input.value = ""
        goal_name_input.error_text = None
        goal_amount_input.error_text = None
        close_dialog(add_goal_dialog)
        check_goals_reached()
        update_goals_view()
        page.update()

    def handle_complete_goal(goal_id, goal_name, target_amount):
        log_goal_completion_to_history(goal_name, target_amount)
        delete_goal_from_db(goal_id)
        update_dashboard()
        show_snack(f"🏁 \"{goal_name}\" completed and added to your history!", bgcolor=ft.Colors.AMBER_700)

    def confirm_delete_goal(goal_id, goal_name):
        delete_goal_dialog.title = ft.Text(f"Delete Goal?")
        delete_goal_dialog.content = ft.Text(
            f'Are you sure you want to delete "{goal_name}"? This cannot be undone.',
            size=14,
        )
        delete_goal_dialog.actions = [
            ft.TextButton("Cancel", on_click=lambda _: close_dialog(delete_goal_dialog)),
            ft.Button(
                "Delete",
                bgcolor=ft.Colors.RED_700,
                color=ft.Colors.WHITE,
                on_click=lambda e, gid=goal_id: handle_delete_goal(gid),
            ),
        ]
        open_dialog(delete_goal_dialog)

    def handle_delete_goal(goal_id):
        delete_goal_from_db(goal_id)
        close_dialog(delete_goal_dialog)
        update_goals_view()
        page.update()
        show_snack("Goal deleted.")

    amount_input = ft.TextField(label="Amount (₱)", keyboard_type=ft.KeyboardType.NUMBER)
    desc_input = ft.TextField(label="Description (e.g., Weekly Allowance)")
    quick_amount_row = ft.Row(
        [
            ft.OutlinedButton(f"₱{amt}", on_click=lambda e, a=amt: set_quick_amount(a))
            for amt in QUICK_AMOUNTS
        ],
        spacing=8,
    )
    add_dialog = ft.AlertDialog(
        title=ft.Text("Add Savings"),
        content=ft.Column(
            [quick_amount_row, amount_input, desc_input],
            height=190,
            spacing=10,
            tight=True,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: close_dialog(add_dialog)),
            ft.Button("Save", on_click=handle_add_savings)
        ]
    )

    adjust_input = ft.TextField(label="Prior Savings (₱)", keyboard_type=ft.KeyboardType.NUMBER)
    adjust_dialog = ft.AlertDialog(
        title=ft.Text("Prior Savings"),
        content=ft.Column([
            ft.Text("Fix your starting amount if you already had money saved before using the app.", size=13, color=ft.Colors.GREY_400),
            adjust_input
        ], height=150, spacing=10),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: close_dialog(adjust_dialog)),
            ft.Button("Save", on_click=handle_adjust_balance)
        ]
    )

    spend_amount_input = ft.TextField(label="Amount Spent (₱)", keyboard_type=ft.KeyboardType.NUMBER)
    spend_desc_input = ft.TextField(label="Description (e.g., Bought headset)")
    spend_dialog = ft.AlertDialog(
        title=ft.Text("Spending"),
        content=ft.Column([
            ft.Text("Record money you spent from your savings.", size=13, color=ft.Colors.GREY_400),
            spend_amount_input,
            spend_desc_input,
        ], height=190, spacing=10, tight=True),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: close_dialog(spend_dialog)),
            ft.Button("Spend", on_click=handle_log_spend, bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE),
        ]
    )

    full_reset_checkbox = ft.Checkbox(value=False)
    reset_dialog = ft.AlertDialog(
        title=ft.Text("Reset Balance?"),
        content=ft.Column([
            ft.Text(
                "This will record a withdrawal that sets your balance to ₱0. Your transaction history will NOT be erased.",
                size=13,
            ),
            ft.Divider(),
            ft.Row([
                full_reset_checkbox,
                ft.Container(
                    content=ft.Text("Also wipe entire database (deletes ALL history & goals)", size=13),
                    expand=True,
                ),
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text(
                "Check this only if you want to permanently delete everything instead - no balance, no history, no goals. This cannot be undone.",
                size=12,
                color=ft.Colors.RED_300,
            ),
        ], spacing=8, tight=True, width=300),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: close_dialog(reset_dialog)),
            ft.Button("Reset", on_click=handle_reset_balance, bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE),
        ]
    )

    goal_name_input = ft.TextField(label="Goal Name (e.g., Headset)")
    goal_amount_input = ft.TextField(label="Target Amount (₱)", keyboard_type=ft.KeyboardType.NUMBER)
    add_goal_dialog = ft.AlertDialog(
        title=ft.Text("Add Goal"),
        content=ft.Column([
            ft.Text("Set something you want to save up for.", size=13, color=ft.Colors.GREY_400),
            goal_name_input,
            goal_amount_input,
        ], height=190, spacing=10, tight=True),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: close_dialog(add_goal_dialog)),
            ft.Button("Add Goal", on_click=handle_add_goal),
        ]
    )

    delete_goal_dialog = ft.AlertDialog(
        title=ft.Text("Delete Goal?"),
        content=ft.Text(""),
    )

    balance_text = ft.Text(value="₱0.00", size=36, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    history_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

    home_view = ft.Column([
        ft.Container(
            content=ft.Column([
                ft.Text("Total Savings", size=14, color=ft.Colors.GREY_400),
                balance_text,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
            alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=16,
        ),
        ft.Row([
            ft.Text("History Log", size=18, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.IconButton(
                    ft.Icons.MONEY_OFF,
                    tooltip="Log spending",
                    icon_color=ft.Colors.RED_300,
                    on_click=lambda _: open_dialog(spend_dialog),
                ),
                ft.IconButton(
                    ft.Icons.RESTART_ALT,
                    tooltip="Reset balance to ₱0",
                    icon_color=ft.Colors.ORANGE_300,
                    on_click=lambda _: open_dialog(reset_dialog),
                ),
                ft.IconButton(
                    ft.Icons.EDIT_NOTE,
                    tooltip="Adjust baseline balance",
                    on_click=lambda _: open_dialog(adjust_dialog),
                ),
            ], spacing=0),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        history_list
    ], spacing=15, expand=True)

    goals_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    goals_view = ft.Column([
        ft.Row([
            ft.Text("Goals", size=18, weight=ft.FontWeight.BOLD),
            ft.IconButton(
                ft.Icons.ADD_CIRCLE_OUTLINE,
                tooltip="Add a new goal",
                icon_color=ft.Colors.GREEN_400,
                icon_size=28,
                on_click=lambda _: open_dialog(add_goal_dialog),
            ),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Text("Track things you want to save up for.", size=13, color=ft.Colors.GREY_400),
        goals_list,
    ], spacing=12, expand=True, visible=False)

    initial_schedule = get_schedule_map()

    day_checkboxes = {}     
    day_sections = {}       
    day_rows_columns = {}   
    day_time_rows = {}      

    def remove_time_row(day, row_ctrl):
        if row_ctrl in day_time_rows[day]:
            day_time_rows[day].remove(row_ctrl)
        if row_ctrl in day_rows_columns[day].controls:
            day_rows_columns[day].controls.remove(row_ctrl)
        page.update()

    def create_time_row(day, hour=6, minute=0, period="PM"):
        hour_dd = ft.DropdownM2(
            value=str(hour), width=68, dense=True,
            color=ft.Colors.WHITE,
            border_color=ft.Colors.GREY_700,
            options=[ft.dropdown.Option(str(h)) for h in range(1, 13)]
        )
        minute_dd = ft.DropdownM2(
            value=f"{minute:02d}", width=78, dense=True,
            color=ft.Colors.WHITE,
            border_color=ft.Colors.GREY_700,
            options=[ft.dropdown.Option(f"{m:02d}") for m in range(0, 60, 5)]
        )
        period_dd = ft.DropdownM2(
            value=period, width=78, dense=True,
            color=ft.Colors.WHITE,
            border_color=ft.Colors.GREY_700,
            options=[ft.dropdown.Option("AM"), ft.dropdown.Option("PM")]
        )
        row_ctrl = ft.Row(spacing=6)
        remove_btn = ft.IconButton(
            ft.Icons.CLOSE, icon_size=18,
            on_click=lambda e: remove_time_row(day, row_ctrl)
        )
        row_ctrl.controls = [hour_dd, ft.Text(":"), minute_dd, period_dd, remove_btn]
        row_ctrl.data = {"hour": hour_dd, "minute": minute_dd, "period": period_dd}

        day_rows_columns[day].controls.append(row_ctrl)
        day_time_rows[day].append(row_ctrl)
        return row_ctrl

    def add_time_row_clicked(day):
        if len(day_time_rows[day]) >= MAX_TIMES_PER_DAY:
            show_snack(f"You can add up to {MAX_TIMES_PER_DAY} times per day.")
            return
        create_time_row(day)
        page.update()

    def on_day_toggle(day, e):
        enabled = e.control.value
        day_sections[day].visible = enabled
        if enabled and not day_time_rows[day]:
            create_time_row(day)
        page.update()

    day_cards = []
    for day in ALL_DAYS:
        existing_times = initial_schedule.get(day, [])
        enabled = bool(existing_times)

        day_rows_columns[day] = ft.Column(spacing=4)
        day_time_rows[day] = []

        checkbox = ft.Checkbox(label=day, value=enabled)
        checkbox.on_change = lambda e, d=day: on_day_toggle(d, e)
        day_checkboxes[day] = checkbox

        for t in existing_times:
            h, m, p = from_24h(t)
            create_time_row(day, h, m, p)

        add_time_btn = ft.TextButton(
            "+ Add another time",
            icon=ft.Icons.ADD,
            on_click=lambda e, d=day: add_time_row_clicked(d)
        )

        section = ft.Column([day_rows_columns[day], add_time_btn], visible=enabled, spacing=2)
        day_sections[day] = section

        day_cards.append(
            ft.Container(
                content=ft.Column([checkbox, section], spacing=4),
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
            )
        )

    async def handle_save_settings(e):
        new_schedule = {}
        for day in ALL_DAYS:
            if not day_checkboxes[day].value:
                continue
            times = []
            for row in day_time_rows[day]:
                d = row.data
                times.append(to_24h(d["hour"].value, d["minute"].value, d["period"].value))
            if times:
                new_schedule[day] = times

        save_schedule_map(new_schedule)
        await refresh_scheduled_notifications()

        if new_schedule:
            show_snack("Schedule saved! You'll get phone notifications at those times.")
        else:
            show_snack("Schedule cleared - no reminders are set.")

    settings_view = ft.Column(
        [
            ft.Text("Reminder Schedule", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Pick any days and add one or more reminder times for each.", size=13, color=ft.Colors.GREY_400),
            *day_cards,
            ft.Button("Save Schedule", icon=ft.Icons.SAVE, on_click=handle_save_settings, width=float("inf"))
        ],
        spacing=12,
        visible=False,
        scroll=ft.ScrollMode.AUTO,
    )

    body_container = ft.Container(content=home_view, expand=True, padding=15)

    def on_nav_change(e):
        idx = e.control.selected_index
        home_view.visible = idx == 0
        goals_view.visible = idx == 1
        settings_view.visible = idx == 2

        if idx == 0:
            body_container.content = home_view
        elif idx == 1:
            update_goals_view()
            body_container.content = goals_view
        else:
            body_container.content = settings_view

        page.floating_action_button = fab if idx == 0 else None
        page.update()

    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.ACCOUNT_BALANCE_WALLET, label="Home"),
            ft.NavigationBarDestination(icon=ft.Icons.FLAG, label="Goals"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label="Schedule"),
        ],
        on_change=on_nav_change
    )

    fab = ft.FloatingActionButton(
        content=ft.Row(
            [ft.Icon(ft.Icons.ADD)],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=5
        ),
        bgcolor=ft.Colors.GREEN_600,
        on_click=lambda _: open_dialog(add_dialog),
        width=50
    )
    page.floating_action_button = fab

    page.add(body_container)
    update_dashboard()

ft.run(main)