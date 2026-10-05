# python
from datetime import datetime
import flet as ft
# local
from constants import *
from database_orm import _leer_configuracion, HistorialPago, Miembro


def crear_modal_pago(nombre_miembro: str, page: ft.Page, session, miembro_id: int, on_guardar=None):
    """
    Crea un AlertDialog para registrar un pago.
    El dropdown muestra hasta 12 meses con precios calculados desde la config.
    Al confirmar, registra el pago desde la fecha del último vencimiento.
    ---
    Entrada:
        nombre_miembro (str): Nombre del miembro (solo display).
        page (ft.Page): Página de Flet.
        session (Session): Sesión activa de SQLAlchemy.
        miembro_id (int): ID del miembro en la BD.
        on_guardar (callable, opcional): Callback al guardar (refresca la UI).
    """
    is_mobile = page.width is not None and page.width < 600

    # --- Header del modal ---
    header = ft.Container(
        content=ft.Text(
            f"Registrar Pago - {nombre_miembro}",
            size=14, weight="bold",
            color=THEME_TEXT_PRIMARY,
            text_align=ft.TextAlign.CENTER,
        ),
        bgcolor=THEME_HEADER_BG_MODAL,
        padding=ft.Padding(20, 14, 20, 14),
        alignment=ft.Alignment.CENTER,
        border_radius=ft.BorderRadius.only(top_left=12, top_right=12),
    )

    # --- Acción cerrar ---
    def cerrar_modal(e):
        modal_pago.open = False
        page.update()

    # --- Precio mensual desde la configuración ---
    precio = float(_leer_configuracion("precio_mensual", session, "3000"))

    def _formatear_precio(valor: float) -> str:
        """Formatea el precio: sin decimales si es entero, con 2 si tiene centavos."""
        if valor == int(valor):
            return f"${int(valor)}"
        return f"${valor:.2f}"

    # --- Dropdown con 12 meses y precios dinámicos ---
    opciones_meses = []
    for i in range(1, 13):
        total = precio * i
        texto = f"{i} mes{'es' if i > 1 else ''} ({_formatear_precio(total)})"
        opciones_meses.append(ft.dropdown.Option(key=str(i), text=texto))

    dropdown = ft.Dropdown(
        label="Meses a abonar",
        options=opciones_meses,
        value="1",  # 1 mes por defecto
        width=280,
        border_color=THEME_BORDER_COLOR,
        focused_border_color=THEME_TEAL,
        color=THEME_TEXT_PRIMARY,
    )

    # --- Total dinámico ---
    total_text = ft.Text(
        f"Total: {_formatear_precio(precio)}",
        size=32, weight="bold", color=THEME_TEXT_PRIMARY,
    )

    def actualizar_total(e):
        """Actualiza el texto del total al cambiar el dropdown."""
        meses = int(dropdown.value)
        total_text.value = f"Total: {_formatear_precio(precio * meses)}"
        total_text.update()

    dropdown.on_change = actualizar_total

    columna_izquierda = ft.Column(
        controls=[
            dropdown,
            ft.Container(expand=True),
            total_text,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )

    # --- QR, Texto y Botones ---
    confirmar_btn = ft.FilledButton(
        content=ft.Text("Confirmar Pago"),
        bgcolor=BTNS_BG,
        color=THEME_TEAL_TEXT,
        style=ft.ButtonStyle(mouse_cursor=ft.MouseCursor.CLICK),
    )

    cancelar_btn = ft.OutlinedButton(
        content=ft.Text("Cancelar"),
        style=ft.ButtonStyle(
            color=THEME_TEXT_PRIMARY,
            side=ft.BorderSide(1, THEME_BORDER_COLOR),
            mouse_cursor=ft.MouseCursor.CLICK,
        ),
        on_click=cerrar_modal,
    )

    # --- Lógica de pago ---
    def confirmar_pago(e):
        meses = int(dropdown.value)
        monto = precio * meses

        miembro = session.query(Miembro).filter_by(id=miembro_id).first()
        if miembro is None:
            return

        # El pago se registra con la fecha real del día del pago
        fecha_pago = datetime.now()

        # Un nuevo pago recalcula el vencimiento: descarta el override manual
        miembro.fecha_vencimiento = None

        pago = HistorialPago(
            miembro_id=miembro_id,
            fecha_pago=fecha_pago,
            monto=monto,
            meses_abonados=meses,
        )
        session.add(pago)
        session.commit()

        cerrar_modal(e)
        if on_guardar:
            on_guardar()

    confirmar_btn.on_click = confirmar_pago

    alias = _leer_configuracion("alias", session, "")

    alias_display = ft.Text(
        f"Alias: {alias}" if alias else "Sin alias configurado",
        size=16,
        color=THEME_TEXT_PRIMARY,
        text_align=ft.TextAlign.CENTER,
    )

    if is_mobile:
        ancho_modal = page.width * 0.9 if page.width else None

        columna_derecha = ft.Column(
            controls=[
                ft.Container(expand=True),
                alias_display,
                ft.Container(expand=True),
                ft.Row(
                    controls=[confirmar_btn, cancelar_btn],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15,
        )

        contenido = ft.Column(
            controls=[
                header,
                ft.Container(content=columna_izquierda, padding=ft.Padding(20, 20, 20, 10)),
                ft.Container(content=columna_derecha, padding=ft.Padding(20, 10, 20, 20)),
            ],
            scroll=ft.ScrollMode.AUTO,
        )
    else:
        columna_derecha = ft.Column(
            controls=[
                ft.Container(expand=True),
                alias_display,
                ft.Container(expand=True),
                ft.Row(
                    controls=[confirmar_btn, cancelar_btn],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15,
        )

        contenido = ft.Column(
            controls=[
                header,
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=columna_izquierda,
                                padding=ft.Padding(20, 20, 20, 20),
                                expand=True,
                            ),
                            ft.VerticalDivider(width=1, color=THEME_BORDER_COLOR),
                            ft.Container(
                                content=columna_derecha,
                                padding=ft.Padding(20, 20, 20, 20),
                                expand=True,
                            ),
                        ],
                        expand=True,
                    ),
                    expand=True,
                ),
            ],
        )

    modal_pago = ft.AlertDialog(
        modal=True,
        bgcolor=THEME_CARD_BG,
        shape=ft.RoundedRectangleBorder(radius=12),
        content=ft.Container(
            content=contenido,
            width=ancho_modal if is_mobile else 650,
            height=None if is_mobile else 380,
        ),
        content_padding=ft.Padding.all(0),
    )

    return modal_pago
