import flet as ft

from config import APP_NAME
from database import db
from theme import light_theme


def main(page: ft.Page):
    page.title = APP_NAME
    page.theme = light_theme()
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 400
    page.window.height = 800
    page.window.min_width = 350
    page.window.min_height = 700
    page.padding = 0
    page.spacing = 0

    db.initialize()

    page.add(
        ft.Container(
            content=ft.Text(
                "Welcome to SaveUp!",
                size=24,
                weight=ft.FontWeight.BOLD,
            ),
            alignment=ft.Alignment(0, 0),
            expand=True,
        )
    )


ft.run(main)