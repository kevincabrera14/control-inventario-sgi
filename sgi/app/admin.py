from django.contrib import admin
from .models import Negocio, PerfilUsuario, Categoria, Proveedor, Producto, MovimientoInventario

@admin.register(Negocio)
class NegocioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nit_o_rut', 'telefono', 'creado_en')
    search_fields = ('nombre', 'nit_o_rut')

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'negocio')
    search_fields = ('user__username', 'negocio__nombre')
    list_filter = ('negocio',)

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'negocio')
    search_fields = ('nombre',)
    list_filter = ('negocio',)

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'email', 'activo', 'negocio')
    search_fields = ('nombre',)
    list_filter = ('activo', 'negocio')

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_barras', 'categoria', 'precio_venta', 'stock_actual', 'stock_minimo', 'activo', 'negocio')
    list_filter = ('activo', 'categoria', 'negocio')
    search_fields = ('nombre', 'codigo_barras')
    # Nota: He dejado stock_actual como solo lectura, pero he quitado stock_minimo 
    # de readonly_fields para que puedas editarlo desde el admin.
    readonly_fields = ('stock_actual',)

@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('producto', 'tipo', 'cantidad', 'costo_unitario', 'stock_antes', 'stock_despues', 'fecha', 'usuario')
    list_filter = ('tipo', 'fecha')
    # Mantiene tu lógica de campos de solo lectura dinámicos
    readonly_fields = tuple([field.name for field in MovimientoInventario._meta.fields])