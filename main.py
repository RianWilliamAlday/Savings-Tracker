import flet as ft
from database import (
    init_db, set_global_conn, get_total_savings, get_history, 
    get_goals, delete_goal_from_db, mark_goal_reached, 
    log_goal_completion_to_history
)
from utils import (
    ALL_DAYS, MAX_TIMES_PER_DAY, from_24h, to_24h, 
    get_schedule_map, save_schedule_map
)
from notifications import (
    setup_notifications, refresh_scheduled_notifications, 
    fire_goal_reached_notification
)
from ui_components import (
    create_add_dialog, create_adjust_dialog, create_spend_dialog, 
    create_reset_dialog, create_add_goal_dialog, create_delete_goal_dialog
)

def main(page: ft.Page):
    page.title = "SaveMate"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.GREEN)
    page.window.width = 390
    page.window.height = 844
    page.window.resizable = False

    conn = init_db()
    set_global_conn(conn)

    notifications = setup_notifications(page)

    def open_dialog(dialog_control):
        page.show_dialog(dialog_control)

    def close_dialog(dialog_control):
        page.pop_dialog()

    def show_snack(message, bgcolor=None):
        snack = ft.SnackBar(content=ft.Text(message), bgcolor=bgcolor)
        page.show_dialog(snack)

    async def refresh_notifications_wrapper():
        await refresh_scheduled_notifications(page, notifications)

    page.run_task(refresh_notifications_wrapper)

    def check_goals_reached():
        current_savings = get_total_savings()
        goals = get_goals()
        for goal_id, name, target, reached, _ in goals:
            if reached == 0 and current_savings >= target:
                mark_goal_reached(goal_id)
                show_snack(f"🎉 Goal reached: {name}! You've saved ₱{target:,.2f}!", bgcolor=ft.Colors.GREEN_800)
                page.run_task(fire_goal_reached_notification, notifications, goal_id, name)

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
        update_goals_page()
        page.update()

    def update_goals_page():
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

    add_dialog = create_add_dialog(page, update_dashboard, close_dialog)
    adjust_dialog = create_adjust_dialog(page, update_dashboard, close_dialog)
    spend_dialog = create_spend_dialog(page, update_dashboard, close_dialog)
    reset_dialog = create_reset_dialog(page, update_dashboard, close_dialog, show_snack)
    add_goal_dialog = create_add_goal_dialog(page, check_goals_reached, update_goals_page, close_dialog)

    def handle_delete_goal_confirmed(goal_id, dialog):
        delete_goal_from_db(goal_id)
        close_dialog(dialog)
        update_goals_page()
        page.update()
        show_snack("Goal deleted.")

    delete_goal_dialog, confirm_delete_goal = create_delete_goal_dialog(
        open_dialog, close_dialog, handle_delete_goal_confirmed
    )

    def handle_complete_goal(goal_id, goal_name, target_amount):
        log_goal_completion_to_history(goal_name, target_amount)
        delete_goal_from_db(goal_id)
        update_dashboard()
        show_snack(f"🏁 \"{goal_name}\" achieved and added to your history!", bgcolor=ft.Colors.AMBER_700)

    balance_text = ft.Text(value="₱0.00", size=36, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    history_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

    home_page = ft.Column([
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
            ft.Text("History", size=18, weight=ft.FontWeight.BOLD),
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
    goals_page = ft.Column([
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
            options=[ft.dropdown.Option(str(h)) for h in range(1, 13)]
        )
        minute_dd = ft.DropdownM2(
            value=f"{minute:02d}", width=78, dense=True,
            options=[ft.dropdown.Option(f"{m:02d}") for m in range(0, 60, 5)]
        )
        period_dd = ft.DropdownM2(
            value=period, width=78, dense=True,
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
        await refresh_scheduled_notifications(page, notifications)
        if new_schedule:
            show_snack("Schedule saved! You'll get phone notifications at those times.")
        else:
            show_snack("Schedule cleared - no reminders are set.")

    schedule_page = ft.Column(
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

    body_container = ft.Container(content=home_page, expand=True, padding=15)

    def on_nav_change(e):
        idx = e.control.selected_index
        home_page.visible = idx == 0
        goals_page.visible = idx == 1
        schedule_page.visible = idx == 2
        if idx == 0:
            body_container.content = home_page
        elif idx == 1:
            update_goals_page()
            body_container.content = goals_page
        else:
            body_container.content = schedule_page
        page.floating_action_button = fab if idx == 0 else None
        page.update()

    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME, label="Home"),
            ft.NavigationBarDestination(icon=ft.Icons.FLAG, label="Goals"),
            ft.NavigationBarDestination(icon=ft.Icons.ACCESS_TIME, label="Schedule"),
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
    page.add(ft.SafeArea(content=body_container, expand=True))
    update_dashboard()

if __name__ == "__main__":
    ft.run(main)