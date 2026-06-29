import flet as ft

PRIMARY_COLOR = "#4CAF50"


def light_theme():
    return ft.Theme(
        color_scheme_seed=PRIMARY_COLOR,
        use_material3=True,
    )


def dark_theme():
    return ft.Theme(
        color_scheme_seed=PRIMARY_COLOR,
        use_material3=True,
    )