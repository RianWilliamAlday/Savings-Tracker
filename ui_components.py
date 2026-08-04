from datetime import datetime
import flet as ft
from database import get_total_savings, add_goal_to_db
from utils import QUICK_AMOUNTS


def create_add_dialog(page, update_dashboard, close_dialog):
    amount_input = ft.TextField(label="Amount (₱)", keyboard_type=ft.KeyboardType.NUMBER)
    desc_input = ft.TextField(label="Description (e.g., Weekly Allowance)")

    def set_quick_amount(amount):
        amount_input.value = str(amount)
        amount_input.error_text = None
        page.update()

    quick_amount_row = ft.Row(
        [
            ft.OutlinedButton(f"₱{amt}", on_click=lambda e, a=amt: set_quick_amount(a))
            for amt in QUICK_AMOUNTS
        ],
        spacing=8,
    )

    def handle_add_savings(e):
        try:
            amt = float(amount_input.value)
            desc = desc_input.value if desc_input.value else "Saved"
            if amt <= 0:
                raise ValueError
            from database import conn
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO history (amount, type, description, date) VALUES (?, 'Deposit', ?, ?)",
                (amt, desc, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            conn.commit()
            amount_input.value = ""
            desc_input.value = ""
            amount_input.error_text = None
            close_dialog(add_dialog)
            update_dashboard()
        except ValueError:
            amount_input.error_text = "Please enter a valid amount"
            page.update()

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
    return add_dialog


def create_adjust_dialog(page, update_dashboard, close_dialog):
    adjust_input = ft.TextField(label="Prior Savings (₱)", keyboard_type=ft.KeyboardType.NUMBER)

    def handle_adjust_balance(e):
        try:
            target_balance = float(adjust_input.value)
            current_balance = get_total_savings()
            difference = target_balance - current_balance
            if difference != 0:
                t_type = "Deposit" if difference > 0 else "Withdrawal"
                from database import conn
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO history (amount, type, description, date) VALUES (?, ?, 'Initial Savings', ?)",
                    (difference, t_type, datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
            adjust_input.value = ""
            adjust_input.error_text = None
            close_dialog(adjust_dialog)
            update_dashboard()
        except ValueError:
            adjust_input.error_text = "Please enter a valid balance"
            page.update()

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
    return adjust_dialog


def create_spend_dialog(page, update_dashboard, close_dialog):
    spend_amount_input = ft.TextField(label="Amount Spent (₱)", keyboard_type=ft.KeyboardType.NUMBER)
    spend_desc_input = ft.TextField(label="Description (e.g., Bought headset)")

    def handle_log_spend(e):
        try:
            amt = float(spend_amount_input.value)
            desc = spend_desc_input.value if spend_desc_input.value else "Spent"
            if amt <= 0:
                raise ValueError
            current = get_total_savings()
            if amt > current:
                spend_amount_input.error_text = f"Can't spend more than ₱{current:,.2f}"
                page.update()
                return
            from database import conn
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
    return spend_dialog


def create_reset_dialog(page, update_dashboard, close_dialog, show_snack):
    full_reset_checkbox = ft.Checkbox(value=False)

    def handle_reset_balance(e):
        if full_reset_checkbox.value:
            from database import conn
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
            from database import conn
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO history (amount, type, description, date) VALUES (?, 'Withdrawal', 'Balance Reset to ₱0', ?)",
                (-current, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            conn.commit()
        close_dialog(reset_dialog)
        update_dashboard()
        show_snack("Balance has been reset to ₱0.00. History preserved.")

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
    return reset_dialog


def create_add_goal_dialog(page, check_goals_reached, update_goals_view, close_dialog):
    goal_name_input = ft.TextField(label="Goal Name (e.g., Headset)")
    goal_amount_input = ft.TextField(label="Target Amount (₱)", keyboard_type=ft.KeyboardType.NUMBER)

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
    return add_goal_dialog


def create_delete_goal_dialog(open_dialog, close_dialog, on_delete_confirmed):
    delete_goal_dialog = ft.AlertDialog(
        title=ft.Text("Delete Goal?"),
        content=ft.Text(""),
    )

    def confirm_delete_goal(goal_id, goal_name):
        delete_goal_dialog.title = ft.Text("Delete Goal?")
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
                on_click=lambda e, gid=goal_id: on_delete_confirmed(gid, delete_goal_dialog),
            ),
        ]
        open_dialog(delete_goal_dialog)

    return delete_goal_dialog, confirm_delete_goal