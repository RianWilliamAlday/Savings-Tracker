import flet as ft
from database import get_total_savings, get_history, get_goals, mark_goal_reached, delete_goal_from_db, log_goal_completion_to_history
from utils import QUICK_AMOUNTS, ALL_DAYS
from notifications import fire_goal_reached_notification

def create_add_dialog(page, update_dashboard, close_dialog):
    amount_input = ft.TextField(label="Amount (₱)", keyboard_type=ft.KeyboardType.NUMBER)
    desc_input = ft.TextField(label="Description (e.g., Weekly Allowance)")
    quick_amount_row = ft.Row(
        [
            ft.OutlinedButton(f"₱{amt}", on_click=lambda e, a=amt: set_quick_amount(a, amount_input, page))
            for amt in QUICK_AMOUNTS
        ],
        spacing=8,
    )

    def handle_add_savings(e):
        try:
            amt = float(amount_input.value)
            desc = desc_input.value if desc_input.value else "Manual Deposit"
            if amt <= 0:
                raise ValueError
            from database import conn
            cursor = conn.cursor()
            cursor.execute("INSERT INTO history (amount, type, description, date) VALUES (?, 'Deposit', ?, ?)",
                           (amt, desc, __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M")))
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
    return add_dialog, amount_input

def set_quick_amount(amount, amount_input, page):
    amount_input.value = str(amount)
    amount_input.error_text = None
    page.update()