# python
import flet as ft
# locales
from constants import *
from components.modal_pago import crear_modal_pago
from components.modal_detalle import crear_modal_detalles
from components.modal_confirmacion import crear_modal_confirmacion
from components.modal_rutina import crear_modal_rutina
from database_orm import session as db_session

class MemberCard(ft.Container):

    def __init__(self, page: ft.Page, name: str = "", status_text: str = "", status_color: str = "", payment_due: bool = False, miembro_id: int = 0, on_guardar=None, has_routine: bool = False):
        super().__init__()
        self.expand = True
        self.name = name
        self.status_text = status_text
        self.status_color = status_color
        self.payment_due = payment_due
        self.miembro_id = miembro_id
        self.on_guardar = on_guardar
        self.has_routine = has_routine
        self.page_ = page

        # Configuración del contenedor de la tarjeta
        self.bgcolor = THEME_CARD_BG
        self.border_radius = 12
        self.margin = ft.Margin.only(bottom=10)
        self.border = ft.Border(
            left=ft.BorderSide(8, self.status_color),
            top=None,
            right=None,
            bottom=None,
        )

        self.padding = ft.Padding(20, 20, 20, 20)

        # Determinar colores del botón "PAGAR" según el estado
        if self.payment_due:
            pagar_button_bgcolor = BTNS_BG
            pagar_button_color = THEME_TEAL_TEXT
        else:
            pagar_button_bgcolor = THEME_GREY_BUTTON_BG
            pagar_button_color = THEME_GREY_BUTTON_TEXT

        # Determinar colores del botón "RUTINA" según si tiene rutinas
        if self.has_routine:
            rutina_button_bgcolor = BTNS_BG
            rutina_button_color = THEME_TEAL_TEXT
        else:
            rutina_button_bgcolor = THEME_GREY_BUTTON_BG
            rutina_button_color = THEME_TEXT_PRIMARY

        # Datos del miembro (Nombre y Estado)
        name_text = ft.Text(
            self.name,
            color=THEME_TEXT_PRIMARY,
            size=24,
            weight="bold",
        )
        status_text = ft.Text(
            self.status_text,
            color=THEME_TEXT_SECONDARY,
            size=16,
        )

        # Botones de acción
        pagar_button = ft.FilledButton(
            content=ft.Text(value="PAGAR", no_wrap=True),
            bgcolor=pagar_button_bgcolor,
            color=pagar_button_color,
            style=ft.ButtonStyle(mouse_cursor=ft.MouseCursor.CLICK),
            on_click=lambda e: self._open_modal_pago(e),
        )
        rutina_button = ft.FilledButton(
            content=ft.Text(value="RUTINA", no_wrap=True),
            bgcolor=rutina_button_bgcolor,
            color=rutina_button_color,
            style=ft.ButtonStyle(mouse_cursor=ft.MouseCursor.CLICK),
            on_click=lambda e: self._open_modal_rutina(e),

        )
        detalles_button = ft.FilledButton(
            content=ft.Text(value="DETALLES", no_wrap=True),
            bgcolor=BTNS_BG,
            color=THEME_TEAL_TEXT,
            style=ft.ButtonStyle(mouse_cursor=ft.MouseCursor.CLICK),
            on_click=lambda e: self._crear_modal_detalles(e),
        )

        # Botón eliminar (icono rojo)
        delete_button = ft.IconButton(
            icon=ft.Icons.DELETE,
            icon_color=ft.Colors.RED,
            icon_size=20,
            tooltip="Eliminar miembro",
            mouse_cursor=ft.MouseCursor.CLICK,
            on_click=lambda e: self._confirmar_eliminar(e),
        )

        self.content = ft.ResponsiveRow(
            controls=[
                ft.Column(
                    controls=[name_text, status_text],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                    col={
                        ft.ResponsiveRowBreakpoint.XS: 12,
                        ft.ResponsiveRowBreakpoint.MD: 7,
                        ft.ResponsiveRowBreakpoint.LG: 8,
                    },
                    expand=True,
                ),
                ft.ResponsiveRow(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Container(content=pagar_button, width=110),
                                ft.Container(content=rutina_button, width=110),
                                ft.Container(content=detalles_button, width=110),
                                ft.Container(content=delete_button, width=110),
                            ],
                            spacing=10,
                            run_spacing=10,
                            wrap=True,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.CENTER,
                    col={
                        ft.ResponsiveRowBreakpoint.XS: 12,
                        ft.ResponsiveRowBreakpoint.MD: 5,
                        ft.ResponsiveRowBreakpoint.LG: 4,
                    },
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _open_modal_pago(self, e):
        modal = crear_modal_pago(self.name, self.page_, db_session, self.miembro_id, on_guardar=self.on_guardar)
        self.page_.show_dialog(modal)

    def _open_modal_rutina(self, e):
        modal = crear_modal_rutina(self.name, self.page_, db_session, self.miembro_id, on_guardar=self.on_guardar)
        self.page_.show_dialog(modal)

    def _confirmar_eliminar(self, e):
        """Abre el modal de confirmación para eliminar al miembro."""
        modal = crear_modal_confirmacion(self.name, self.page_, db_session, self.miembro_id, on_guardar=self.on_guardar)
        self.page_.show_dialog(modal)

    def _crear_modal_detalles(self, e):
        """Abre el modal de detalles con los datos reales del miembro desde la BD."""
        modal = crear_modal_detalles(self.name, self.page_, db_session, self.miembro_id, on_guardar=self.on_guardar)
        if modal:
            self.page_.show_dialog(modal)