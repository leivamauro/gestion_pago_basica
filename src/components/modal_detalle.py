# python
import io
from datetime import datetime
from pathlib import Path
import flet as ft
from flet import FilePicker, FilePickerFileType
# reportlab
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors as rl_colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# locales
from constants import *
from database_orm import (
    Miembro, HistorialPago,
    _estado_semaforo, _ultimo_pago,
    _calcular_vencimiento, _dias_restantes, _dias_pasados,
    _inicio_ciclo_pago, _leer_configuracion, _fecha_vencimiento,
)


def crear_modal_detalles(nombre_miembro: str, page: ft.Page, session, miembro_id: int, on_guardar=None):
    """
    Crea un AlertDialog con los detalles reales del miembro desde la BD.
    ---
    Entrada:
        nombre_miembro (str): Nombre del miembro.
        page (ft.Page): Página de Flet.
        session (Session): Sesión activa de SQLAlchemy.
        miembro_id (int): ID del miembro en la BD.
        on_guardar (callable, opcional): Callback al editar el vencimiento (refresca la UI).
    Salida:
        ft.AlertDialog: Modal de detalles del miembro.
    """
    is_mobile = page.width is not None and page.width < 600

    # Cargar datos reales del miembro desde la BD
    miembro = session.query(Miembro).filter_by(id=miembro_id).first()
    if miembro is None:
        return None

    estado = _estado_semaforo(miembro, session)
    ultimo_pago = _ultimo_pago(miembro_id, session)
    precio = float(_leer_configuracion("precio_mensual", session, "3000"))

    # --- Header del modal (unificado) ---
    header = ft.Container(
        content=ft.Text(
            f"Detalles del Miembro - {nombre_miembro}",
            size=14,
            weight="bold",
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
        modal_detalles.open = False
        page.update()

    # --- Refrescar modal y lista principal tras editar el vencimiento ---
    def refrescar():
        if on_guardar:
            on_guardar()
        nuevo = crear_modal_detalles(
            nombre_miembro, page, session, miembro_id, on_guardar=on_guardar
        )
        if nuevo:
            page.show_dialog(nuevo)

    # --- Generar PDF ---
    async def _generar_pdf(e):
        fecha_venc = _fecha_vencimiento(miembro, session)
        fecha_ultimo = ultimo_pago.fecha_pago.strftime('%d/%m/%Y') if ultimo_pago else "—"

        fecha_reg = miembro.fecha_registro.strftime('%d/%m/%Y') if miembro.fecha_registro else "—"
        fecha_venc_str = fecha_venc.strftime('%d/%m/%Y') if fecha_venc else "—"

        if estado == "vencido":
            texto_estado_pdf = "Adeuda"
            color_estado_pdf = rl_colors.HexColor("#C62828")
            dias_texto = f"Vencido hace {_dias_pasados(miembro, session)} días"
            color_dias = rl_colors.HexColor("#C62828")
        elif estado == "en_prueba":
            texto_estado_pdf = "Período de prueba"
            color_estado_pdf = rl_colors.HexColor("#F9A825")
            inicio = _inicio_ciclo_pago(miembro)
            dias_prueba = (inicio - datetime.now()).days
            dias_texto = f"Prueba - {dias_prueba} días restantes"
            color_dias = rl_colors.HexColor("#F9A825")
        else:
            texto_estado_pdf = "Al día"
            color_estado_pdf = rl_colors.HexColor("#2E7D32")
            dias_texto = f"Vence en {_dias_restantes(miembro, session)} días"
            color_dias = rl_colors.HexColor("#2E7D32")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()

        subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Normal'],
                                         fontSize=12, textColor=rl_colors.HexColor("#666666"),
                                         alignment=1, spaceAfter=20)

        elementos = []
        logo_path = str(ASSETS_DIR / "images" / "recoverfit_banner.png")
        logo = Image(logo_path, width=180, height=60, kind='proportional')
        logo.hAlign = 'CENTER'
        elementos.append(logo)
        elementos.append(Spacer(1, 10))
        elementos.append(Paragraph("Comprobante de Pago", subtitulo_style))

        data = [
            ["Nombre", "Fecha Registro", "Último Pago", "Vencimiento"],
            [miembro.nombre, fecha_reg, fecha_ultimo, fecha_venc_str],
        ]
        col_widths = [doc.width * 0.30, doc.width * 0.20, doc.width * 0.25, doc.width * 0.25]

        tabla = Table(data, colWidths=col_widths)
        tabla_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor("#1B6CA8")),
            ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 1), (-1, 1), rl_colors.HexColor("#F0F0F0")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ])
        tabla.setStyle(tabla_style)
        elementos.append(tabla)
        elementos.append(Spacer(1, 24))

        info_style = ParagraphStyle('Info', parent=styles['Normal'],
                                    fontSize=11, leading=18)
        elementos.append(Paragraph(
            f"<b>Estado:</b> <font color='{color_estado_pdf.hexval()}'>"
            f"{texto_estado_pdf}</font>", info_style))
        elementos.append(Paragraph(
            f"<b>Días:</b> <font color='{color_dias.hexval()}'>"
            f"{dias_texto}</font>", info_style))
        elementos.append(Spacer(1, 30))

        fecha_gen = datetime.now().strftime('%d/%m/%Y')
        pie_style = ParagraphStyle('Pie', parent=styles['Normal'],
                                   fontSize=9, textColor=rl_colors.HexColor("#999999"),
                                   alignment=1)
        elementos.append(Paragraph(f"Generado el {fecha_gen}", pie_style))
        elementos.append(Paragraph("RecoverFit - Gestión de Clientes", pie_style))

        doc.build(elementos)
        pdf_bytes = buffer.getvalue()

        name_clean = miembro.nombre.replace(' ', '_')
        name_clean = "".join(c for c in name_clean if c.isalnum() or c in ('_', '-'))
        fecha_str = datetime.now().strftime("%Y%m%d")
        nombre_archivo = f"Comprobante_{name_clean}_{fecha_str}.pdf"

        picker = FilePicker()
        es_mobile = page.platform is not None and page.platform.is_mobile()

        if page.web or es_mobile:
            await picker.save_file(
                dialog_title="Guardar Comprobante PDF",
                file_name=nombre_archivo,
                file_type=FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf"],
                src_bytes=pdf_bytes,
            )
        else:
            ruta = await picker.save_file(
                dialog_title="Guardar Comprobante PDF",
                file_name=nombre_archivo,
                file_type=FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf"],
            )
            if ruta:
                Path(ruta).write_bytes(pdf_bytes)

        page.snack_bar = ft.SnackBar(
            content=ft.Text("PDF creado!"),
            bgcolor=THEME_TEAL,
            duration=3000,
        )
        page.snack_bar.open = True
        page.update()

    cancelar_btn = ft.OutlinedButton(
        content=ft.Text("Cancelar"),
        style=ft.ButtonStyle(
            color=THEME_TEXT_PRIMARY,
            side=ft.BorderSide(1, THEME_BORDER_COLOR),
            mouse_cursor=ft.MouseCursor.CLICK,
        ),
        on_click=cerrar_modal,
    )

    pdf_btn = ft.FilledButton(
        content=ft.Row(
            controls=[ft.Icon(ft.Icons.PICTURE_AS_PDF, size=16, color=THEME_TEAL_TEXT), ft.Text("Baucher")],
            spacing=4,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=BTNS_BG,
        color=THEME_TEAL_TEXT,
        style=ft.ButtonStyle(mouse_cursor=ft.MouseCursor.CLICK),
        on_click=_generar_pdf,
    )

    # --- Texto de estado y colores ---
    if estado == "vencido":
        texto_estado = "Vencido"
        color_estado = ft.Colors.RED
    elif estado == "en_prueba":
        texto_estado = "En período de prueba"
        color_estado = ft.Colors.YELLOW
    else:
        texto_estado = "Al día"
        color_estado = ft.Colors.GREEN

    # --- Último pago formateado ---
    if ultimo_pago:
        texto_ultimo_pago = (
            f"Último Pago: {ultimo_pago.fecha_pago.strftime('%d/%m/%Y')} "
            f"(${ultimo_pago.monto:.0f})"
        )
    else:
        texto_ultimo_pago = "Último Pago: Sin pagos"

    # --- Líneas dinámicas de deuda / días ---
    lineas_deuda = []
    if estado == "vencido":
        meses = _calcular_vencimiento(miembro, session)
        deuda = meses * precio
        dias = _dias_pasados(miembro, session)
        lineas_deuda.append(
            ft.Text(f"Debe {meses} meses (${deuda:.0f})", color=ft.Colors.RED, size=14,
                    overflow=ft.TextOverflow.ELLIPSIS)
        )
        lineas_deuda.append(
            ft.Text(f"Vencido hace {dias} días", color=ft.Colors.RED, size=14,
                    overflow=ft.TextOverflow.ELLIPSIS)
        )
    elif estado == "en_prueba":
        # Mostrar días restantes de prueba (no el primer vencimiento)
        inicio = _inicio_ciclo_pago(miembro)
        dias_prueba = (inicio - datetime.now()).days
        lineas_deuda.append(
            ft.Text(f"Prueba - {dias_prueba} días restantes", color=color_estado, size=14,
                    overflow=ft.TextOverflow.ELLIPSIS)
        )
    else:
        dias = _dias_restantes(miembro, session)
        lineas_deuda.append(
            ft.Text(f"Vence en {dias} días", color=color_estado, size=14,
                    overflow=ft.TextOverflow.ELLIPSIS)
        )

    # --- Columna Izquierda: Información Detallada ---
    columna_izquierda = ft.Column(
        controls=[
            ft.Text("Información Detallada", size=18, color=THEME_TEXT_PRIMARY),
            ft.Container(height=5),
            ft.Text(f"Nombre: {nombre_miembro}", color=THEME_TEXT_PRIMARY, size=15,
                    overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(
                f"Fecha Registro: {miembro.fecha_registro.strftime('%d/%m/%Y')}",
                color=THEME_TEXT_PRIMARY, size=15,
            ),
            ft.Text(texto_ultimo_pago, color=THEME_TEXT_PRIMARY, size=15,
                    overflow=ft.TextOverflow.ELLIPSIS),
            ft.Row(
                controls=[
                    ft.Container(
                        width=14, height=14, border_radius=7,
                        bgcolor=color_estado,
                    ),
                    ft.Text(f"Estado actual: {texto_estado}",
                            color=THEME_TEXT_PRIMARY, size=15,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            *lineas_deuda,
        ],
        spacing=8,
    )

    # --- Columna Derecha: Últimos 12 pagos desde la BD ---
    pagos = (
        session.query(HistorialPago)
        .filter_by(miembro_id=miembro_id)
        .order_by(HistorialPago.fecha_pago.desc())
        .limit(12)
        .all()
    )

    # Vencimiento global actual del miembro (override o cálculo automático)
    venc_actual = _fecha_vencimiento(miembro, session)
    venc_texto = venc_actual.strftime('%d/%m/%Y') if venc_actual else "—"

    # --- Diálogo para editar la fecha de vencimiento global ---
    def abrir_editor_vencimiento(e):
        date_picker = ft.DatePicker(
            value=venc_actual,
            first_date=datetime(2000, 1, 1),
            last_date=datetime(2100, 12, 31),
            help_text="Fecha de vencimiento",
            confirm_text="Guardar",
            cancel_text="Cancelar",
        )

        def _confirmar(ev):
            # on_change se dispara al pulsar "Guardar" con el valor ya actualizado
            valor = date_picker.value
            if valor is None or valor == venc_actual:
                return
            miembro.fecha_vencimiento = valor
            session.commit()
            modal_detalles.open = False
            page.update()
            refrescar()

        date_picker.on_change = _confirmar
        page.show_dialog(date_picker)

    def _crear_card_pago(pago):
        monto_texto = f"${pago.monto:.0f}" if pago.monto == int(pago.monto) else f"${pago.monto:.2f}"
        meses = pago.meses_abonados
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.CALENDAR_MONTH, size=15, color=THEME_TEAL),
                                    ft.Text(pago.fecha_pago.strftime('%d/%m/%Y'),
                                            color=THEME_TEXT_PRIMARY, size=14, weight="bold"),
                                ],
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(f"Monto: {monto_texto}",
                                    color=THEME_TEXT_SECONDARY, size=13),
                            ft.Text(f"Meses abonados: {meses} {'mes' if meses == 1 else 'meses'}",
                                    color=THEME_TEXT_SECONDARY, size=13),
                            ft.Text(f"Vencimiento: {venc_texto}",
                                    color=THEME_TEXT_SECONDARY, size=13),
                        ],
                        spacing=3,
                        alignment=ft.MainAxisAlignment.CENTER,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT,
                        icon_color=THEME_TEAL,
                        icon_size=18,
                        tooltip="Editar fecha de vencimiento",
                        mouse_cursor=ft.MouseCursor.CLICK,
                        on_click=abrir_editor_vencimiento,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=THEME_BG,
            border=ft.Border.all(1, THEME_BORDER_COLOR),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            margin=ft.Margin.only(bottom=8),
        )

    cards_historial = [_crear_card_pago(pago) for pago in pagos]

    # Si no hay pagos, mostrar mensaje pero permitir editar el vencimiento
    if not cards_historial:
        cards_historial.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text("Sin historial de pagos",
                                        color=THEME_TEXT_SECONDARY, size=14, italic=True),
                                ft.Text(f"Vencimiento: {venc_texto}",
                                        color=THEME_TEXT_SECONDARY, size=13),
                            ],
                            spacing=3,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            icon_color=THEME_TEAL,
                            icon_size=18,
                            tooltip="Editar fecha de vencimiento",
                            mouse_cursor=ft.MouseCursor.CLICK,
                            on_click=abrir_editor_vencimiento,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(vertical=10),
            )
        )

    if is_mobile:
        columna_derecha = ft.Column(
            controls=[
                ft.Text("Historial de Pagos", size=18, color=THEME_TEXT_PRIMARY),
                ft.Container(height=5),
                ft.Column(controls=cards_historial, scroll=ft.ScrollMode.AUTO, spacing=0),
                ft.Container(expand=True),
                ft.Row(controls=[ft.Container(expand=True), pdf_btn, cancelar_btn]),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.START,
            spacing=8,
        )

        ancho_modal = page.width * 0.9 if page.width else None

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
                ft.Text("Historial de Pagos", size=18, color=THEME_TEXT_PRIMARY),
                ft.Container(height=5),
                ft.Column(controls=cards_historial, scroll=ft.ScrollMode.AUTO, expand=True, spacing=0),
                ft.Row(controls=[ft.Container(expand=True), pdf_btn, cancelar_btn]),
            ],
            spacing=8,
        )

        contenido = ft.Column(
            controls=[
                header,
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(content=columna_izquierda,
                                         padding=ft.Padding(20, 20, 20, 20),
                                         expand=True),
                            ft.VerticalDivider(width=1, color=THEME_BORDER_COLOR),
                            ft.Container(content=columna_derecha,
                                         padding=ft.Padding(20, 20, 20, 20),
                                         expand=True),
                        ],
                        expand=True,
                    ),
                    expand=True,
                ),
            ],
        )

    modal_detalles = ft.AlertDialog(
        modal=True,
        bgcolor=THEME_CARD_BG,
        shape=ft.RoundedRectangleBorder(radius=12),
        content=ft.Container(
            content=contenido,
            width=ancho_modal if is_mobile else 700,
            height=None if is_mobile else 380,
        ),
        content_padding=ft.Padding.all(0),
    )

    return modal_detalles
