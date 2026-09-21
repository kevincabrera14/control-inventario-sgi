from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
import secrets

# ── CONSTANTES GLOBALES ────────────────────────────────────────────────────────
PAYMENT_METHOD_CHOICES = [
    ('E', 'Efectivo'),
    ('N', 'Nequi'),
    ('B', 'Bancolombia'),
    ('O', 'Otros Bancos'),
]

# ── MODELO: Control de Empresas/Negocios ────────────────────────────────────────
class Negocio(models.Model):
    nombre = models.CharField(max_length=150)
    nit_o_rut = models.CharField(max_length=50, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    # NUEVO: contador interno para numerar facturas de forma consecutiva y
    # exclusiva por negocio (independiente del id autoincremental de Django,
    # que es global a toda la base de datos y no sirve como número de factura).
    siguiente_numero_factura = models.PositiveIntegerField(
        default=1,
        help_text='Próximo número de factura a asignar para este negocio.'
    )

    def __str__(self):
        return self.nombre

# ── MODELO: Perfil de Usuario vinculado a un Negocio ─────────────────────────────
class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name='usuarios')

    def __str__(self):
        return f"{self.user.username} ({self.negocio.nombre})"

# ── MODELOS EXISTENTES DEL SISTEMA ────────────────────────────────────────────
class Categoria(models.Model):
    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name='categorias', null=True, blank=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre

class Proveedor(models.Model):
    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name='proveedores', null=True, blank=True)
    nombre = models.CharField(max_length=200)
    contacto = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name='productos', null=True, blank=True)
    codigo_barras = models.CharField(max_length=50, blank=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, null=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    precio_compra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    IVA_CHOICES = [
        (0, '0%'),
        (5, '5%'),
        (19, '19%'),
    ]
    iva = models.IntegerField(choices=IVA_CHOICES, default=19)
    # NUEVO: campo favorito para filtrado rápido
    favorito = models.BooleanField(default=False, help_text='Marca el producto como favorito para filtros rápidos.')
    stock_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        # El código de barras es único ÚNICAMENTE dentro de la misma empresa
        constraints = [
            models.UniqueConstraint(fields=['negocio', 'codigo_barras'], name='unique_codigo_por_negocio')
        ]

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo

    def __str__(self):
        return self.nombre

# ── MODELO: Venta / Factura ─────────────────────────────────────────────────────
class Venta(models.Model):
    """Agrupa varios movimientos (salidas) y guarda datos de facturación."""
    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name='ventas')
    # NUEVO: número de factura consecutivo, único por negocio. Se asigna en
    # el momento del checkout tomando y avanzando Negocio.siguiente_numero_factura
    # dentro de una transacción atómica (ver views.checkout_venta).
    numero_factura = models.PositiveIntegerField(
        blank=True, null=True, editable=False,
        help_text='Consecutivo de factura, único dentro del negocio.'
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                               help_text='Bodeguero que realizó la venta')
    cliente_nombre = models.CharField(max_length=200, blank=True, null=True,
                                      help_text='Nombre del cliente (opcional)')
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                   help_text='Descuento en moneda local (valor absoluto)')
    iva = models.IntegerField(choices=Producto.IVA_CHOICES, default=19,
                               help_text='IVA aplicado a la venta')
    total_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                     help_text='Suma de precio_venta * cantidad antes de descuento/IVA')
    total_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                    help_text='Resultado después de aplicar descuento e IVA')
    payment_method = models.CharField(max_length=1, choices=PAYMENT_METHOD_CHOICES, default='E',
                                      help_text='Método de pago usado en la venta completa')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['negocio', 'numero_factura'],
                name='unique_numero_factura_por_negocio'
            )
        ]

    def __str__(self):
        return f"Factura #{self.numero_factura or self.id} – {self.fecha:%Y-%m-%d %H:%M}"

# ── MODELO: Movimiento de Inventario ────────────────────────────────────────────
class MovimientoInventario(models.Model):
    TIPO_CHOICES = [
        ('E', 'Entrada'),
        ('S', 'Salida'),
        ('A', 'Ajuste'),
    ]
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # NUEVO: precio de VENTA unitario al momento de la transacción (solo aplica
    # a tipo 'S' generadas desde el POS). Sin esto, el ticket tendría que
    # recalcular con el precio_venta ACTUAL del producto, que puede haber
    # cambiado desde que se hizo la venta -> factura históricamente incorrecta.
    precio_unitario_venta = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                                help_text='Precio de venta unitario al momento de la venta (solo tipo S vía POS).')
    stock_antes = models.DecimalField(max_digits=12, decimal_places=2)
    stock_despues = models.DecimalField(max_digits=12, decimal_places=2)
    referencia = models.CharField(max_length=100, blank=True)
    # NUEVO: método de pago (solo tiene sentido para tipo 'S')
    payment_method = models.CharField(max_length=1, choices=PAYMENT_METHOD_CHOICES,
                                      blank=True, null=True,
                                      help_text='Método de pago usado en la venta (solo para tipo S).')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    # Relación opcional a la venta que agrupa este movimiento
    venta = models.ForeignKey('Venta', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos')

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.producto.nombre} ({self.cantidad})"

# ── MODELO: Dispositivo recordado (auto-login persistente) ───────────────────────
class DispositivoRecordado(models.Model):
    """
    Guarda un token único por dispositivo/navegador. Mientras la cookie
    'sgi_device_token' con este valor exista en el navegador, el usuario
    entra automáticamente sin pedir usuario/contraseña, incluso después
    de cerrar sesión manualmente.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dispositivos_recordados')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(auto_now=True)
    user_agent = models.CharField(max_length=255, blank=True)

    @classmethod
    def generar_para(cls, user, user_agent=''):
        token = secrets.token_urlsafe(48)
        return cls.objects.create(user=user, token=token, user_agent=user_agent[:255])

    def __str__(self):
        return f"Dispositivo de {self.user.username} ({self.creado_en:%d/%m/%Y})"