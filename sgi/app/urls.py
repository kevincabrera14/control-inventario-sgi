from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Enrutador central en la raíz
    path('', views.dashboard, name='dashboard'),
    
    # SOLUCIÓN: Agregamos las alias de ruta que tus redirecciones de rol están buscando
    path('dashboard/admin/', views.dashboard, name='dashboard_admin'),
    path('dashboard/gerente/', views.dashboard, name='dashboard_gerente'),
    path('dashboard/bodeguero/', views.dashboard, name='dashboard_bodeguero'),

    # Productos
    path('productos/', views.ProductoListView.as_view(), name='producto-list'),
    path('productos/crear/', views.ProductoCreateView.as_view(), name='producto-create'),
    path('productos/editar/<int:pk>/', views.ProductoUpdateView.as_view(), name='producto-update'),
    path('productos/eliminar/<int:pk>/', views.producto_delete, name='producto-delete'),
    path('productos/<int:pk>/', views.ProductoDetailView.as_view(), name='producto-detail'),

    # Movimientos
    path('inventario/entrada/', views.entrada_create, name='entrada-create'),
    path('inventario/salida/', views.salida_create, name='salida-create'),
    path('inventario/historial/', views.historial_movimientos, name='historial-movimientos'),
    path('inventario/confirmar/', views.confirmar_movimiento, name='confirmar-movimiento'),

    # Proveedores
    path('proveedores/', views.ProveedorListView.as_view(), name='proveedor-list'),
    path('proveedores/crear/', views.ProveedorCreateView.as_view(), name='proveedor-create'),
    path('proveedores/editar/<int:pk>/', views.ProveedorUpdateView.as_view(), name='proveedor-update'),
    path('proveedores/<int:pk>/', views.ProveedorDetailView.as_view(), name='proveedor-detail'),

    # Reportes
    path('reportes/', views.reporte_inventario_excel, name='reportes-index'),
    path('reportes/inventario/excel/', views.reporte_inventario_excel, name='reporte-inventario-excel'),
    path('reportes/inventario/pdf/', views.reporte_inventario_pdf, name='reporte-inventario-pdf'),
    path('reportes/stock-bajo/pdf/', views.reporte_stock_bajo_pdf, name='reporte-stock-bajo-pdf'),
    path('reportes/movimientos/excel/', views.reporte_movimientos_excel, name='reporte-movimientos-excel'),

    # API endpoint for stock
    path('api/producto/<int:pk>/stock/', views.producto_stock_api, name='producto-stock-api'),

    path('informacion/', views.informacion, name='informacion'),
    path('revertir-movimiento/<int:mov_id>/', views.revertir_movimiento, name='revertir-movimiento'),




    path('productos/nuevo/', views.ProductoCreateView.as_view(), name='producto_crear'),
    path('productos/editar/<int:pk>/', views.ProductoUpdateView.as_view(), name='producto_editar'),

    path('bodeguero/productos/', views.bodeguero_lista_productos, name='bodeguero-lista-productos'),
    path('bodeguero/ventas/', views.bodeguero_reportes_ventas, name='bodeguero-reportes-ventas'),
    path('bodeguero/revertir/', views.bodeguero_revertir_venta, name='bodeguero-revertir-venta'),
    path('gerente/historial-financiero/', views.gerente_historial_financiero, name='gerente-historial-financiero'),
    path('gerente/stock-productos/',      views.gerente_stock_productos,       name='gerente-stock-productos'),
    path('gerente/utilidades/',           views.gerente_utilidades,            name='gerente-utilidades'),


    path('codigos-barras/',                views.codigos_barras,        name='codigos-barras'),
    path('codigos-barras/svg/<int:pk>/',   views.barcode_svg,           name='barcode-svg'),
    path('codigos-barras/buscar/',         views.buscar_por_codigo,     name='buscar-por-codigo'),
    path('codigos-barras/hoja/<str:ids>/', views.hoja_impresion_barras, name='hoja-impresion-barras'),
    path('api/crear-categoria/', views.api_crear_categoria, name='api-crear-categoria'),
    path('api/crear-proveedor/', views.api_crear_proveedor, name='api-crear-proveedor'),
]