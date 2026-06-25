import io
import datetime
from django.http import HttpResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# Role helpers – centralized permission checks
# ---------------------------------------------------------------------------
def es_administrador(user):
    """Return True if the user is a superuser or belongs to the 'Administrador' group."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name='Administrador').exists()
    )

def es_gerente(user):
    """Return True if the user belongs to the 'Gerente' group."""
    return user.is_authenticated and user.groups.filter(name='Gerente').exists()

def es_bodeguero(user):
    """Return True if the user belongs to the 'Bodeguero' group."""
    return user.is_authenticated and user.groups.filter(name='Bodeguero').exists()

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def generar_excel_inventario(queryset):
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventario"
    headers = ['Código', 'Nombre', 'Categoría', 'Proveedor', 'Stock', 'Stock Mínimo', 'Precio Compra', 'Precio Venta', 'Valor Total']
    ws.append(headers)
    for p in queryset:
        valor_total = p.stock_actual * p.precio_venta
        ws.append([
            p.codigo_barras,
            p.nombre,
            p.categoria.nombre if p.categoria else '',
            p.proveedor.nombre if p.proveedor else '',
            float(p.stock_actual),
            float(p.stock_minimo),
            float(p.precio_compra),
            float(p.precio_venta),
            float(valor_total),
        ])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="inventario.xlsx"'
    return response

def generar_pdf_inventario(queryset):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    p.setFont('Helvetica-Bold', 12)
    p.drawString(50, height - 50, "SGI — Inventario General")
    p.setFont('Helvetica', 10)
    p.drawString(50, height - 70, f"Fecha: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y = height - 100
    headers = ['Código', 'Nombre', 'Categoría', 'Proveedor', 'Stock', 'Precio Venta', 'Valor Total']
    col_width = 80
    for i, header in enumerate(headers):
        p.drawString(50 + i * col_width, y, header)
    y -= 20
    for prod in queryset:
        row = [
            prod.codigo_barras or '',
            prod.nombre,
            prod.categoria.nombre if prod.categoria else '',
            prod.proveedor.nombre if prod.proveedor else '',
            str(prod.stock_actual),
            str(prod.precio_venta),
            str(prod.stock_actual * prod.precio_venta),
        ]
        for i, cell in enumerate(row):
            p.drawString(50 + i * col_width, y, cell)
        y -= 15
        if y < 50:
            p.showPage()
            y = height - 50
    p.showPage()
    p.save()
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="inventario.pdf"'
    return response