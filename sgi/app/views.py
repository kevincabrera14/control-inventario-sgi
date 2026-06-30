from django.shortcuts import render, redirect, get_object_or_404
from django.db import models, IntegrityError
from django.urls import reverse_lazy
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db import transaction
from django.db.models import F, Sum, Count
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import date, timedelta
import json

from .models import Producto, MovimientoInventario, Categoria, Proveedor, Negocio, PerfilUsuario
from .forms import (
    LoginForm,
    ProductoForm,
    EntradaForm,
    SalidaForm,
    ProveedorForm,
    FiltroHistorialForm,
)
from .utils import (
    es_administrador,
    es_gerente,
    es_bodeguero,
)

def group_required(*group_names):
    def in_groups(u):
        if u.is_authenticated:
            return u.groups.filter(name__in=group_names).exists() or u.is_superuser
        return False
    return user_passes_test(in_groups)

class LoginView(View):
    def get(self, request):
        form = LoginForm()
        return render(request, 'app/login.html', {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(username=form.cleaned_data['username'], password=form.cleaned_data['password'])
            if user is not None:
                login(request, user)
                return redirect('dashboard')
        return render(request, 'app/login.html', {'form': form, 'error': 'Credenciales inválidas'})

def logout_view(request):
    logout(request)
    return redirect('login')

# ── ENRUTADOR CENTRAL PARA LA URL '/' ─────────────────────────────────
@login_required
def dashboard(request):
    user = request.user
    perfil = getattr(user, 'perfil', None)
    
    if not perfil:
        if user.is_superuser:
            productos_qs = Producto.objects.filter(activo=True)
            movimientos_qs = MovimientoInventario.objects.all()
        else:
            return HttpResponse("Su usuario no posee un Perfil de Negocio asignado. Contacte soporte.")
    else:
        negocio = perfil.negocio
        productos_qs = Producto.objects.filter(activo=True, negocio=negocio)
        movimientos_qs = MovimientoInventario.objects.filter(producto__negocio=negocio)

    if es_administrador(user):
        total_productos = productos_qs.count()
        productos_stock_bajo = productos_qs.filter(stock_actual__lte=F('stock_minimo'))
        valor_total = sum(p.stock_actual * p.precio_venta for p in productos_qs)
        ultimos_movimientos = movimientos_qs.select_related('producto', 'usuario').order_by('-fecha')[:10]
        context = {
            'productos': productos_qs,
            'total_productos': total_productos,
            'productos_stock_bajo': productos_stock_bajo,
            'valor_total': valor_total,
            'ultimos_movimientos': ultimos_movimientos,
        }
        return render(request, 'app/dashboard_admin.html', context)

    elif es_gerente(user):
        total_productos = productos_qs.count()
        productos_stock_bajo = productos_qs.filter(stock_actual__lte=F('stock_minimo'))
        ultimos_movimientos = movimientos_qs.select_related('producto', 'usuario').order_by('-fecha')[:5]
        context = {
            'productos': productos_qs,
            'total_productos': total_productos,
            'productos_stock_bajo': productos_stock_bajo,
            'ultimos_movimientos': ultimos_movimientos,
        }
        return render(request, 'app/dashboard_gerente.html', context)

    elif es_bodeguero(user):
        productos_stock_bajo = productos_qs.filter(stock_actual__lte=F('stock_minimo'))
        ultimos_movimientos = movimientos_qs.select_related('producto', 'usuario').order_by('-fecha')[:10]
        context = {
            'productos': productos_qs,
            'productos_stock_bajo': productos_stock_bajo,
            'ultimos_movimientos': ultimos_movimientos,
        }
        return render(request, 'app/dashboard_bodeguero.html', context)

    else:
        return redirect('login')


# ── DASHBOARDS DE TRABAJO SEPARADOS POR ROL Y TENANT ─────────────────

@login_required
@group_required('Administrador')
def dashboard_admin(request):
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        if request.user.is_superuser:
            productos = Producto.objects.filter(activo=True)
            return render(request, 'app/dashboard_admin.html', {
                'productos': productos,
                'total_productos': productos.count(),
                'productos_stock_bajo': [p for p in productos if p.stock_bajo],
                'valor_total': sum(p.stock_actual * p.precio_compra for p in productos),
                'ultimos_movimientos': MovimientoInventario.objects.all().order_by('-fecha')[:10],
            })
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado. Contacte soporte.")

    negocio = perfil.negocio
    productos = Producto.objects.filter(activo=True, negocio=negocio)
    total_productos = productos.count()
    productos_stock_bajo = [p for p in productos if p.stock_bajo]
    valor_total = sum(p.stock_actual * p.precio_compra for p in productos)
    ultimos_movimientos = MovimientoInventario.objects.filter(
        producto__negocio=negocio
    ).order_by('-fecha')[:10]

    return render(request, 'app/dashboard_admin.html', {
        'productos': productos,
        'total_productos': total_productos,
        'productos_stock_bajo': productos_stock_bajo,
        'valor_total': valor_total,
        'ultimos_movimientos': ultimos_movimientos,
    })


@login_required
@group_required('Administrador', 'Gerente')
def dashboard_gerente(request):
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")
        
    negocio = perfil.negocio
    productos = Producto.objects.filter(activo=True, negocio=negocio)
    total_productos = productos.count()
    productos_stock_bajo = [p for p in productos if p.stock_bajo]
    ultimos_movimientos = MovimientoInventario.objects.filter(
        producto__negocio=negocio
    ).order_by('-fecha')[:10]

    return render(request, 'app/dashboard_gerente.html', {
        'productos': productos,
        'total_productos': total_productos,
        'productos_stock_bajo': productos_stock_bajo,
        'ultimos_movimientos': ultimos_movimientos,
    })


@login_required
@group_required('Administrador', 'Bodeguero')
def dashboard_bodeguero(request):
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")
        
    negocio = perfil.negocio
    productos = Producto.objects.filter(activo=True, negocio=negocio)
    productos_stock_bajo = [p for p in productos if p.stock_bajo]
    ultimos_movimientos = MovimientoInventario.objects.filter(
        producto__negocio=negocio
    ).order_by('-fecha')[:10]

    return render(request, 'app/dashboard_bodeguero.html', {
        'productos': productos,
        'productos_stock_bajo': productos_stock_bajo,
        'ultimos_movimientos': ultimos_movimientos,
    })


# ── VISTAS DEL PRODUCTO FILTRADAS POR TENANT ──────────────────────────

@method_decorator(login_required, name='dispatch')
class ProductoListView(ListView):
    model = Producto
    template_name = 'app/productos/lista.html'
    paginate_by = 20

    def get_queryset(self):
        perfil = getattr(self.request.user, 'perfil', None)
        if not perfil:
            return Producto.objects.none()
        qs = Producto.objects.filter(activo=True, negocio=perfil.negocio).order_by('nombre')
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(
                models.Q(nombre__icontains=search) |
                models.Q(codigo_barras__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context


@method_decorator(login_required, name='dispatch')
class ProductoDetailView(DetailView):
    model = Producto
    template_name = 'app/productos/detalle.html'
    context_object_name = 'producto'

    def get_queryset(self):
        perfil = getattr(self.request.user, 'perfil', None)
        if not perfil:
            return Producto.objects.none()
        return Producto.objects.filter(negocio=perfil.negocio)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ultimos_movimientos'] = self.object.movimientos.order_by('-fecha')[:10]
        return context


@method_decorator([login_required, group_required('Administrador', 'Gerente', 'Bodeguero')], name='dispatch')
class ProductoCreateView(CreateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'app/productos/form.html'
    success_url = reverse_lazy('dashboard')

    def get_form_kwargs(self):
        """Pass the current negocio to the form for barcode validation."""
        kwargs = super().get_form_kwargs()
        perfil = getattr(self.request.user, 'perfil', None)
        if perfil:
            kwargs['negocio'] = perfil.negocio
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        perfil = getattr(self.request.user, 'perfil', None)
        if perfil:
            form.fields['categoria'].queryset = Categoria.objects.filter(negocio=perfil.negocio)
            form.fields['proveedor'].queryset = Proveedor.objects.filter(negocio=perfil.negocio)
        return form

    def form_valid(self, form):
        perfil = getattr(self.request.user, 'perfil', None)
        if perfil:
            form.instance.negocio = perfil.negocio
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error('codigo_barras', 'Ya existe un producto con este código de barras en su negocio.')
            return self.form_invalid(form)


@method_decorator([login_required, group_required('Administrador', 'Gerente', 'Bodeguero')], name='dispatch')
class ProductoUpdateView(UpdateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'app/productos/form.html'
    success_url = reverse_lazy('dashboard')

    def get_form_kwargs(self):
        """Pass the current negocio to the form for barcode validation."""
        kwargs = super().get_form_kwargs()
        perfil = getattr(self.request.user, 'perfil', None)
        if perfil:
            kwargs['negocio'] = perfil.negocio
        return kwargs

    def get_queryset(self):
        perfil = getattr(self.request.user, 'perfil', None)
        if not perfil:
            return Producto.objects.none()
        return Producto.objects.filter(negocio=perfil.negocio)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        perfil = getattr(self.request.user, 'perfil', None)
        if perfil:
            form.fields['categoria'].queryset = Categoria.objects.filter(negocio=perfil.negocio)
            form.fields['proveedor'].queryset = Proveedor.objects.filter(negocio=perfil.negocio)
        return form

    def form_valid(self, form):
        perfil = getattr(self.request.user, 'perfil', None)
        if perfil:
            form.instance.negocio = perfil.negocio
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error('codigo_barras', 'Ya existe un producto con este código de barras en su negocio.')
            return self.form_invalid(form)


@login_required
@group_required('Administrador', 'Gerente')
def producto_delete(request, pk):
    """
    Elimina (desactiva) un producto y registra un movimiento de pérdida
    por el stock restante antes de ocultarlo del inventario activo.
    URL name: 'producto-delete'
    """
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.", status=403)

    producto = get_object_or_404(Producto, pk=pk, negocio=perfil.negocio)

    if request.method == 'POST':
        with transaction.atomic():
            stock_restante = producto.stock_actual

            # Registrar pérdida solo si había stock en existencia
            if stock_restante > 0:
                MovimientoInventario.objects.create(
                    producto=producto,
                    tipo='A',                          # Ajuste = pérdida por baja
                    cantidad=-stock_restante,           # Negativo: salida total
                    costo_unitario=producto.precio_compra,
                    stock_antes=stock_restante,
                    stock_despues=0,
                    referencia=f'BAJA DE PRODUCTO – eliminado por {request.user.username}',
                    usuario=request.user,
                )
                producto.stock_actual = 0

            # Marcar como inactivo (soft delete)
            producto.activo = False
            producto.save()

        # Redirigir al listado del gerente si viene de ahí, si no al general
        referer = request.META.get('HTTP_REFERER', '')
        if 'gerente' in referer:
            return redirect('gerente-stock-productos')
        return redirect('producto-list')

    # GET: no debería llegar aquí, pero redirigimos por seguridad
    return redirect('gerente-stock-productos')


# ── PROCESOS DE INVENTARIO SEGUROS ───────────────────────────────────

@login_required
def entrada_create(request):
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")
    
    negocio = perfil.negocio
    if request.method == 'POST':
        form = EntradaForm(request.POST)
        if form.is_valid():
            producto = form.cleaned_data['producto']
            if producto.negocio != negocio:
                return HttpResponse("Error de seguridad: Producto no pertenece a su negocio.", status=403)
                
            cantidad = form.cleaned_data['cantidad']
            costo = form.cleaned_data['costo_unitario']
            with transaction.atomic():
                stock_antes = producto.stock_actual
                producto.stock_actual += cantidad
                producto.save()

                MovimientoInventario.objects.create(
                    producto=producto,
                    tipo='E',
                    cantidad=cantidad,
                    costo_unitario=costo,
                    stock_antes=stock_antes,
                    stock_despues=producto.stock_actual,
                    referencia=form.cleaned_data.get('referencia', ''),
                    usuario=request.user
                )
            return redirect('producto-list')
    else:
        producto_id = request.GET.get('producto_id')
        initial = {}
        if producto_id:
            initial['producto'] = producto_id
        form = EntradaForm(initial=initial)
        form.fields['producto'].queryset = Producto.objects.filter(activo=True, negocio=negocio)
    return render(request, 'app/movimientos/entrada.html', {'form': form})


@login_required
def salida_create(request):
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")
        
    negocio = perfil.negocio
    if request.method == 'POST':
        form = SalidaForm(request.POST)
        if form.is_valid():
            producto = form.cleaned_data['producto']
            if producto.negocio != negocio:
                return HttpResponse("Error de seguridad: Producto no pertenece a su negocio.", status=403)

            cantidad = form.cleaned_data['cantidad']
            if producto.stock_actual >= cantidad:
                with transaction.atomic():
                    stock_antes = producto.stock_actual
                    producto.stock_actual -= cantidad
                    producto.save()

                    MovimientoInventario.objects.create(
                        producto=producto,
                        tipo='S',
                        cantidad=cantidad,
                        costo_unitario=0,
                        stock_antes=stock_antes,
                        stock_despues=producto.stock_actual,
                        referencia=form.cleaned_data.get('referencia', ''),
                        usuario=request.user
                    )
                return redirect('producto-list')
            else:
                form.add_error('cantidad', 'Stock insuficiente.')
    else:
        producto_id = request.GET.get('producto_id')
        initial = {}
        if producto_id:
            initial['producto'] = producto_id
        form = SalidaForm(initial=initial)
        form.fields['producto'].queryset = Producto.objects.filter(activo=True, negocio=negocio)
    return render(request, 'app/movimientos/salida.html', {'form': form})


@login_required
def confirmar_movimiento(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            perfil = getattr(request.user, 'perfil', None)
            if not perfil:
                return JsonResponse({'status': 'error', 'message': 'Usuario sin negocio asignado.'}, status=400)
            
            negocio = perfil.negocio
            with transaction.atomic():
                for item in items:
                    producto = get_object_or_404(Producto, pk=item['producto_id'], negocio=negocio)
                    from decimal import Decimal
                    cantidad = Decimal(str(item['cantidad']))
                    
                    if producto.stock_actual < cantidad:
                        return JsonResponse({'status': 'error', 'message': f'Stock insuficiente para {producto.nombre}'}, status=400)

                    stock_antes = producto.stock_actual
                    producto.stock_actual -= cantidad
                    producto.save()
                    
                    MovimientoInventario.objects.create(
                        producto=producto,
                        tipo='S',
                        cantidad=cantidad,
                        costo_unitario=0,
                        stock_antes=stock_antes,
                        stock_despues=producto.stock_actual,
                        referencia="Salida POS Lote",
                        usuario=request.user
                    )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@login_required
def historial_movimientos(request):
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")
        
    negocio = perfil.negocio
    form = FiltroHistorialForm(request.GET or None)
    movimientos = MovimientoInventario.objects.filter(
        producto__negocio=negocio
    ).select_related('producto', 'usuario').order_by('-fecha')

    if form.is_valid():
        if form.cleaned_data.get('producto'):
            movimientos = movimientos.filter(producto=form.cleaned_data['producto'])
        if form.cleaned_data.get('tipo'):
            movimientos = movimientos.filter(tipo=form.cleaned_data['tipo'])
        if form.cleaned_data.get('fecha_desde'):
            movimientos = movimientos.filter(fecha__date__gte=form.cleaned_data['fecha_desde'])
        if form.cleaned_data.get('fecha_hasta'):
            movimientos = movimientos.filter(fecha__date__lte=form.cleaned_data['fecha_hasta'])

    form.fields['producto'].queryset = Producto.objects.filter(negocio=negocio)
    
    from django.core.paginator import Paginator
    paginator = Paginator(movimientos, 30)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    
    return render(request, 'app/movimientos/historial.html', {'form': form, 'page_obj': page_obj})


# ── NUEVA VISTA: LISTA DE PRODUCTOS CON CRUD COMPLETO (BODEGUERO) ─────

@login_required
@group_required('Administrador', 'Gerente', 'Bodeguero')
def bodeguero_lista_productos(request):
    """
    Lista de productos con búsqueda y acciones CRUD accesibles para el bodeguero.
    Muestra stock actual, estado y accesos directos a editar/eliminar.
    """
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")

    negocio = perfil.negocio
    search = request.GET.get('search', '').strip()
    categoria_id = request.GET.get('categoria', '')
    stock_filtro = request.GET.get('stock', '')

    productos = Producto.objects.filter(activo=True, negocio=negocio).select_related('categoria', 'proveedor').order_by('nombre')

    if search:
        productos = productos.filter(
            models.Q(nombre__icontains=search) |
            models.Q(codigo_barras__icontains=search)
        )

    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)

    if stock_filtro == 'bajo':
        productos = productos.filter(stock_actual__lte=F('stock_minimo'))
    elif stock_filtro == 'sin':
        productos = productos.filter(stock_actual=0)

    categorias = Categoria.objects.filter(negocio=negocio)

    from django.core.paginator import Paginator
    paginator = Paginator(productos, 25)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    context = {
        'page_obj': page_obj,
        'search': search,
        'categorias': categorias,
        'categoria_seleccionada': categoria_id,
        'stock_filtro': stock_filtro,
        'total_productos': productos.count(),
    }
    return render(request, 'app/bodeguero/lista_productos.html', context)


# ── NUEVA VISTA: REPORTES DE VENTAS POR DÍA (BODEGUERO) ──────────────

@login_required
@group_required('Administrador', 'Gerente', 'Bodeguero')
def bodeguero_reportes_ventas(request):
    """
    Vista de reportes de ventas agrupados por día.
    Muestra los últimos 30 días con movimientos de salida (ventas).
    El usuario puede expandir cada día para ver el detalle de productos vendidos.
    """
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")

    negocio = perfil.negocio

    # Rango de fechas: últimos 30 días por defecto, o el que el usuario seleccione
    fecha_hasta = request.GET.get('fecha_hasta', '')
    fecha_desde = request.GET.get('fecha_desde', '')

    try:
        from datetime import datetime
        fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date() if fecha_hasta else date.today()
        fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date() if fecha_desde else date.today() - timedelta(days=29)
    except ValueError:
        fecha_hasta_obj = date.today()
        fecha_desde_obj = date.today() - timedelta(days=29)

    # Movimientos de salida (ventas) en el rango seleccionado
    movimientos_ventas = MovimientoInventario.objects.filter(
        producto__negocio=negocio,
        tipo='S',
        fecha__date__gte=fecha_desde_obj,
        fecha__date__lte=fecha_hasta_obj,
    ).select_related('producto', 'usuario').order_by('-fecha')

    # Agrupar movimientos por día usando Python para incluir detalle completo
    from collections import defaultdict
    dias = defaultdict(lambda: {'movimientos': [], 'total_items': 0, 'total_unidades': 0})

    for mov in movimientos_ventas:
        dia_key = mov.fecha.date()
        dias[dia_key]['movimientos'].append(mov)
        dias[dia_key]['total_items'] += 1
        dias[dia_key]['total_unidades'] += float(mov.cantidad)

    # Convertir a lista ordenada de más reciente a más antigua
    dias_lista = sorted(
        [{'fecha': k, **v} for k, v in dias.items()],
        key=lambda x: x['fecha'],
        reverse=True
    )

    # Resumen general del período
    total_ventas_periodo = sum(d['total_items'] for d in dias_lista)
    total_unidades_periodo = sum(d['total_unidades'] for d in dias_lista)
    dias_con_ventas = len(dias_lista)

    # Producto más vendido del período
    from django.db.models import Sum as DjSum
    top_productos = (
        MovimientoInventario.objects.filter(
            producto__negocio=negocio,
            tipo='S',
            fecha__date__gte=fecha_desde_obj,
            fecha__date__lte=fecha_hasta_obj,
        )
        .values('producto__nombre')
        .annotate(total_vendido=DjSum('cantidad'))
        .order_by('-total_vendido')[:5]
    )

    context = {
        'dias_lista': dias_lista,
        'fecha_desde': fecha_desde_obj.strftime('%Y-%m-%d'),
        'fecha_hasta': fecha_hasta_obj.strftime('%Y-%m-%d'),
        'total_ventas_periodo': total_ventas_periodo,
        'total_unidades_periodo': total_unidades_periodo,
        'dias_con_ventas': dias_con_ventas,
        'top_productos': top_productos,
    }
    return render(request, 'app/bodeguero/reportes_ventas.html', context)


# ── NUEVA VISTA: ÚLTIMOS MOVIMIENTOS CON REVERTIR (BODEGUERO) ────────

@login_required
@group_required('Administrador', 'Gerente', 'Bodeguero')
def bodeguero_revertir_venta(request):
    """
    Página dedicada con los últimos movimientos de inventario del negocio.
    Permite revertir salidas (ventas) directamente desde aquí.
    Template: app/bodeguero/revertir_venta.html
    """
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")

    negocio = perfil.negocio
    ultimos_movimientos = (
        MovimientoInventario.objects
        .filter(producto__negocio=negocio)
        .select_related('producto', 'usuario')
        .order_by('-fecha')[:50]
    )

    return render(request, 'app/bodeguero/revertir_venta.html', {
        'ultimos_movimientos': ultimos_movimientos,
    })


# ── VISTAS DE PROVEEDORES FILTRADAS POR TENANT ────────────────────────

@method_decorator(login_required, name='dispatch')
class ProveedorListView(ListView):
    model = Proveedor
    template_name = 'app/proveedores/lista.html'
    paginate_by = 20

    def get_queryset(self):
        perfil = getattr(self.request.user, 'perfil', None)
        if not perfil:
            return Proveedor.objects.none()
        return Proveedor.objects.filter(activo=True, negocio=perfil.negocio)

@method_decorator([login_required, group_required('Administrador')], name='dispatch')
class ProveedorCreateView(CreateView):
    model = Proveedor
    form_class = ProveedorForm
    template_name = 'app/proveedores/form.html'
    success_url = reverse_lazy('proveedor-list')

    def form_valid(self, form):
        perfil = getattr(self.request.user, 'perfil', None)
        if perfil:
            form.instance.negocio = perfil.negocio
        return super().form_valid(form)

@method_decorator([login_required, group_required('Administrador')], name='dispatch')
class ProveedorUpdateView(UpdateView):
    model = Proveedor
    form_class = ProveedorForm
    template_name = 'app/proveedores/form.html'
    success_url = reverse_lazy('proveedor-list')

    def get_queryset(self):
        perfil = getattr(self.request.user, 'perfil', None)
        if not perfil:
            return Proveedor.objects.none()
        return Proveedor.objects.filter(negocio=perfil.negocio)

@method_decorator(login_required, name='dispatch')
class ProveedorDetailView(DetailView):
    model = Proveedor
    template_name = 'app/proveedores/detalle.html'
    context_object_name = 'proveedor'

    def get_queryset(self):
        perfil = getattr(self.request.user, 'perfil', None)
        if not perfil:
            return Proveedor.objects.none()
        return Proveedor.objects.filter(negocio=perfil.negocio)

# ── ALIASES DE COMPATIBILIDAD CON URLS.PY antiguas ───────────────────
entrada_inventario = entrada_create
salida_inventario = salida_create
HistorialMovimientosView = historial_movimientos

# ── REPORTES EXPORTABLES FILTRADOS POR NEGOCIO ───────────────────────
@login_required
@group_required('Administrador', 'Gerente')
def reporte_inventario_excel(request):
    from .utils import generar_excel_inventario
    perfil = getattr(request.user, 'perfil', None)
    queryset = Producto.objects.filter(activo=True, negocio=perfil.negocio if perfil else None)
    return generar_excel_inventario(queryset)

@login_required
@group_required('Administrador', 'Gerente')
def reporte_inventario_pdf(request):
    from .utils import generar_pdf_inventario
    perfil = getattr(request.user, 'perfil', None)
    queryset = Producto.objects.filter(activo=True, negocio=perfil.negocio if perfil else None)
    return generar_pdf_inventario(queryset)

@login_required
@group_required('Administrador', 'Gerente')
def reporte_stock_bajo_pdf(request):
    from .utils import generar_pdf_inventario
    perfil = getattr(request.user, 'perfil', None)
    queryset = Producto.objects.filter(activo=True, negocio=perfil.negocio if perfil else None, stock_actual__lte=F('stock_minimo'))
    return generar_pdf_inventario(queryset)

@login_required
@group_required('Administrador', 'Gerente')
def reporte_movimientos_excel(request):
    return HttpResponse('Reporte movimientos Excel placeholder')

# ── UTILERÍAS / API ───────────────────────────────────────────────────

@login_required
def producto_stock_api(request, pk):
    perfil = getattr(request.user, 'perfil', None)
    producto = get_object_or_404(Producto, pk=pk, negocio=perfil.negocio if perfil else None)
    return JsonResponse({'stock_actual': float(producto.stock_actual), 'nombre': producto.nombre})


def informacion(request):
    return render(request, 'app/informacion.html')

@login_required
@require_POST
def revertir_movimiento(request, mov_id):
    perfil = getattr(request.user, 'perfil', None)
    movimiento = get_object_or_404(
        MovimientoInventario,
        id=mov_id,
        producto__negocio=perfil.negocio if perfil else None
    )
    
    if movimiento.tipo == 'S':
        producto = movimiento.producto
        with transaction.atomic():
            producto.stock_actual += movimiento.cantidad
            producto.save()
            movimiento.delete()
        return JsonResponse({'status': 'success', 'message': 'Venta revertida y stock restaurado exitosamente.'})
    else:
        return JsonResponse(
            {'status': 'error', 'message': 'Solo se pueden revertir movimientos de salida (ventas).'},
            status=400
        )
    

    # ─────────────────────────────────────────────────────────────────────────────
# NUEVAS VISTAS PARA EL DASHBOARD GERENTE
# Agregar estas funciones en views.py (dentro del archivo existente)
#
# En urls.py agregar:
#   path('gerente/historial-financiero/', views.gerente_historial_financiero, name='gerente-historial-financiero'),
#   path('gerente/stock-productos/',      views.gerente_stock_productos,       name='gerente-stock-productos'),
#   path('gerente/utilidades/',           views.gerente_utilidades,            name='gerente-utilidades'),
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date, timedelta
from collections import defaultdict
from django.db.models import Sum, Count, F, Q


# ── VISTA 1: HISTORIAL FINANCIERO ─────────────────────────────────────────────

@login_required
@group_required('Administrador', 'Gerente')
def gerente_historial_financiero(request):
    """
    Muestra ventas (S), compras (E) y flujo de caja agrupados por día y mes.
    Template: app/gerente/historial_financiero.html
    """
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")

    negocio = perfil.negocio

    # ── Resolución de rango de fechas ──────────────────────────────────────
    periodo = request.GET.get('periodo', '')
    hoy = date.today()

    if periodo == 'hoy':
        fecha_desde_obj = hoy
        fecha_hasta_obj = hoy
    elif periodo == 'semana':
        fecha_desde_obj = hoy - timedelta(days=hoy.weekday())
        fecha_hasta_obj = hoy
    elif periodo == 'mes':
        fecha_desde_obj = hoy.replace(day=1)
        fecha_hasta_obj = hoy
    elif periodo == 'mes_anterior':
        primer_dia_mes_actual = hoy.replace(day=1)
        fecha_hasta_obj = primer_dia_mes_actual - timedelta(days=1)
        fecha_desde_obj = fecha_hasta_obj.replace(day=1)
    elif periodo == 'trimestre':
        fecha_desde_obj = hoy - timedelta(days=90)
        fecha_hasta_obj = hoy
    else:
        # Fechas manuales o default (últimos 30 días)
        from datetime import datetime
        try:
            f_desde = request.GET.get('fecha_desde', '')
            f_hasta = request.GET.get('fecha_hasta', '')
            fecha_desde_obj = datetime.strptime(f_desde, '%Y-%m-%d').date() if f_desde else hoy - timedelta(days=29)
            fecha_hasta_obj = datetime.strptime(f_hasta, '%Y-%m-%d').date() if f_hasta else hoy
        except ValueError:
            fecha_desde_obj = hoy - timedelta(days=29)
            fecha_hasta_obj = hoy

    tipo_filtro = request.GET.get('tipo', '')

    # ── Queryset base ──────────────────────────────────────────────────────
    qs = MovimientoInventario.objects.filter(
        producto__negocio=negocio,
        fecha__date__gte=fecha_desde_obj,
        fecha__date__lte=fecha_hasta_obj,
    ).select_related('producto', 'usuario').order_by('-fecha')

    if tipo_filtro in ('E', 'S'):
        qs = qs.filter(tipo=tipo_filtro)

    # ── Resumen del período ────────────────────────────────────────────────
    todos = list(qs)

    def calcular_valor(mov):
        """Valor monetario de un movimiento: cantidad × precio relevante."""
        if mov.tipo == 'E':
            return float(mov.cantidad) * float(mov.costo_unitario)
        elif mov.tipo == 'S':
            return float(mov.cantidad) * float(mov.producto.precio_venta)
        return 0

    total_ingresos = sum(calcular_valor(m) for m in todos if m.tipo == 'S')
    total_egresos  = sum(calcular_valor(m) for m in todos if m.tipo == 'E')

    resumen = {
        'total_ingresos': total_ingresos,
        'total_egresos':  total_egresos,
        'flujo_neto':     total_ingresos - total_egresos,
        'total_salidas':  sum(1 for m in todos if m.tipo == 'S'),
        'total_entradas': sum(1 for m in todos if m.tipo == 'E'),
        'dias_con_actividad': len(set(m.fecha.date() for m in todos)),
    }

    # ── Agrupación por día ─────────────────────────────────────────────────
    dias_dict = defaultdict(lambda: {'ingresos': 0, 'egresos': 0, 'total_movimientos': 0})
    for mov in todos:
        d = mov.fecha.date()
        dias_dict[d]['total_movimientos'] += 1
        if mov.tipo == 'S':
            dias_dict[d]['ingresos'] += calcular_valor(mov)
        elif mov.tipo == 'E':
            dias_dict[d]['egresos'] += calcular_valor(mov)

    dias_lista = sorted(
        [{'fecha': k, 'flujo': v['ingresos'] - v['egresos'], **v} for k, v in dias_dict.items()],
        key=lambda x: x['fecha'], reverse=True
    )

    # ── Agrupación por mes ────────────────────────────────────────────────
    meses_dict = defaultdict(lambda: {'ingresos': 0, 'egresos': 0, 'total_movimientos': 0})
    MESES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    for mov in todos:
        clave = (mov.fecha.year, mov.fecha.month)
        meses_dict[clave]['total_movimientos'] += 1
        if mov.tipo == 'S':
            meses_dict[clave]['ingresos'] += calcular_valor(mov)
        elif mov.tipo == 'E':
            meses_dict[clave]['egresos'] += calcular_valor(mov)

    meses_lista = sorted(
        [{
            'clave': k,
            'nombre_mes': f"{MESES_ES[k[1]]} {k[0]}",
            'flujo': v['ingresos'] - v['egresos'],
            **v
        } for k, v in meses_dict.items()],
        key=lambda x: x['clave'], reverse=True
    )

    # ── Paginación para tab de detalle ─────────────────────────────────────
    from django.core.paginator import Paginator

    # Enriquecer movimientos con campo 'total'
    for mov in todos:
        mov.total = calcular_valor(mov)

    paginator = Paginator(todos, 40)
    page = request.GET.get('page', 1)
    movimientos_detalle = paginator.get_page(page)

    return render(request, 'app/gerente/historial_financiero.html', {
        'resumen':             resumen,
        'dias_lista':          dias_lista,
        'meses_lista':         meses_lista,
        'movimientos_detalle': movimientos_detalle,
        'fecha_desde':         fecha_desde_obj.strftime('%Y-%m-%d'),
        'fecha_hasta':         fecha_hasta_obj.strftime('%Y-%m-%d'),
        'tipo_filtro':         tipo_filtro,
    })


# ── VISTA 2: STOCK Y PRODUCTOS ────────────────────────────────────────────────

@login_required
@group_required('Administrador', 'Gerente')
def gerente_stock_productos(request):
    """
    Listado de productos con KPIs de stock, filtros y accesos directos CRUD.
    Template: app/gerente/stock_productos.html
    """
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")

    negocio = perfil.negocio

    search         = request.GET.get('search', '').strip()
    categoria_id   = request.GET.get('categoria', '')
    stock_filtro   = request.GET.get('stock', '')

    productos = (
        Producto.objects
        .filter(activo=True, negocio=negocio)
        .select_related('categoria', 'proveedor')
        .order_by('nombre')
    )

    if search:
        productos = productos.filter(
            Q(nombre__icontains=search) | Q(codigo_barras__icontains=search)
        )

    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)

    if stock_filtro == 'bajo':
        productos = productos.filter(stock_actual__lte=F('stock_minimo'))
    elif stock_filtro == 'sin':
        productos = productos.filter(stock_actual=0)

    # KPIs
    todos_productos = Producto.objects.filter(activo=True, negocio=negocio)
    total_productos    = todos_productos.count()
    productos_stock_bajo = todos_productos.filter(stock_actual__lte=F('stock_minimo')).count()
    productos_sin_stock  = todos_productos.filter(stock_actual=0).count()
    valor_inventario     = sum(
        float(p.stock_actual) * float(p.precio_venta)
        for p in todos_productos
    )

    categorias = Categoria.objects.filter(negocio=negocio)

    from django.core.paginator import Paginator
    paginator = Paginator(productos, 25)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    return render(request, 'app/gerente/stock_productos.html', {
        'page_obj':              page_obj,
        'search':                search,
        'categorias':            categorias,
        'categoria_seleccionada': categoria_id,
        'stock_filtro':          stock_filtro,
        'total_productos':       total_productos,
        'productos_stock_bajo':  productos_stock_bajo,
        'productos_sin_stock':   productos_sin_stock,
        'valor_inventario':      valor_inventario,
    })


# ── VISTA 3: UTILIDADES Y PROYECCIONES ───────────────────────────────────────

@login_required
@group_required('Administrador', 'Gerente')
def gerente_utilidades(request):
    """
    Análisis de margen bruto, utilidad por producto y simulador de proyecciones.
    Template: app/gerente/utilidades.html
    """
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")

    negocio = perfil.negocio

    # ── Rango de fechas ────────────────────────────────────────────────────
    from datetime import datetime
    hoy = date.today()
    periodo = request.GET.get('periodo', 'mes')

    if periodo == 'mes':
        fecha_desde_obj = hoy.replace(day=1)
        fecha_hasta_obj = hoy
    elif periodo == 'trimestre':
        fecha_desde_obj = hoy - timedelta(days=90)
        fecha_hasta_obj = hoy
    elif periodo == 'año':
        fecha_desde_obj = hoy.replace(month=1, day=1)
        fecha_hasta_obj = hoy
    else:
        try:
            f_desde = request.GET.get('fecha_desde', '')
            f_hasta = request.GET.get('fecha_hasta', '')
            fecha_desde_obj = datetime.strptime(f_desde, '%Y-%m-%d').date() if f_desde else hoy.replace(day=1)
            fecha_hasta_obj = datetime.strptime(f_hasta, '%Y-%m-%d').date() if f_hasta else hoy
        except ValueError:
            fecha_desde_obj = hoy.replace(day=1)
            fecha_hasta_obj = hoy

    # ── Movimientos del período ────────────────────────────────────────────
    ventas_qs = MovimientoInventario.objects.filter(
        producto__negocio=negocio,
        tipo='S',
        fecha__date__gte=fecha_desde_obj,
        fecha__date__lte=fecha_hasta_obj,
    ).select_related('producto')

    compras_qs = MovimientoInventario.objects.filter(
        producto__negocio=negocio,
        tipo='E',
        fecha__date__gte=fecha_desde_obj,
        fecha__date__lte=fecha_hasta_obj,
    ).select_related('producto')

    # Ingresos = cantidad × precio_venta del producto
    ingresos_brutos = sum(float(m.cantidad) * float(m.producto.precio_venta) for m in ventas_qs)
    costo_ventas    = sum(float(m.cantidad) * float(m.costo_unitario) for m in compras_qs)
    utilidad_bruta  = ingresos_brutos - costo_ventas
    margen_bruto    = (utilidad_bruta / ingresos_brutos * 100) if ingresos_brutos else 0

    # Días del período para promedio mensual
    dias_periodo = max((fecha_hasta_obj - fecha_desde_obj).days, 1)
    ventas_promedio_mes = ingresos_brutos / dias_periodo * 30

    # ── Top 10 productos por utilidad ─────────────────────────────────────
    productos_dict = defaultdict(lambda: {
        'nombre': '', 'total_ventas': 0, 'total_costo': 0, 'unidades': 0
    })

    for mov in ventas_qs:
        pk = mov.producto_id
        productos_dict[pk]['nombre']       = mov.producto.nombre
        productos_dict[pk]['total_ventas'] += float(mov.cantidad) * float(mov.producto.precio_venta)
        productos_dict[pk]['total_costo']  += float(mov.cantidad) * float(mov.producto.precio_compra)
        productos_dict[pk]['unidades']     += float(mov.cantidad)

    top_productos_raw = []
    for datos in productos_dict.values():
        utilidad = datos['total_ventas'] - datos['total_costo']
        margen   = (utilidad / datos['total_ventas'] * 100) if datos['total_ventas'] else 0
        top_productos_raw.append({**datos, 'utilidad': utilidad, 'margen': margen})

    top_productos = sorted(top_productos_raw, key=lambda x: x['utilidad'], reverse=True)[:10]

    # ── Utilidad mensual histórica (últimos 12 meses) ─────────────────────
    MESES_ES = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    hace_12_meses = hoy - timedelta(days=365)

    ventas_hist = MovimientoInventario.objects.filter(
        producto__negocio=negocio,
        tipo='S',
        fecha__date__gte=hace_12_meses,
    ).select_related('producto')

    compras_hist = MovimientoInventario.objects.filter(
        producto__negocio=negocio,
        tipo='E',
        fecha__date__gte=hace_12_meses,
    ).select_related('producto')

    meses_hist = defaultdict(lambda: {'ingresos': 0, 'costo': 0})
    for m in ventas_hist:
        clave = (m.fecha.year, m.fecha.month)
        meses_hist[clave]['ingresos'] += float(m.cantidad) * float(m.producto.precio_venta)
    for m in compras_hist:
        clave = (m.fecha.year, m.fecha.month)
        meses_hist[clave]['costo'] += float(m.cantidad) * float(m.costo_unitario)

    utilidad_mensual = []
    for clave, datos in sorted(meses_hist.items(), reverse=True):
        u = datos['ingresos'] - datos['costo']
        mg = (u / datos['ingresos'] * 100) if datos['ingresos'] else 0
        utilidad_mensual.append({
            'nombre_mes': f"{MESES_ES[clave[1]]} {clave[0]}",
            'ingresos':   datos['ingresos'],
            'costo':      datos['costo'],
            'utilidad':   u,
            'margen':     mg,
        })

    utilidades = {
        'ingresos_brutos':      ingresos_brutos,
        'costo_ventas':         costo_ventas,
        'utilidad_bruta':       utilidad_bruta,
        'margen_bruto':         margen_bruto,
        'ventas_promedio_mes':  ventas_promedio_mes,
    }

    return render(request, 'app/gerente/utilidades.html', {
        'utilidades':       utilidades,
        'top_productos':    top_productos,
        'utilidad_mensual': utilidad_mensual,
        'fecha_desde':      fecha_desde_obj.strftime('%Y-%m-%d'),
        'fecha_hasta':      fecha_hasta_obj.strftime('%Y-%m-%d'),
        'periodo':          periodo,
    })

# ─────────────────────────────────────────────────────────────────────────────
# VISTAS DE CÓDIGOS DE BARRAS
# Agregar en views.py (sin borrar nada existente)
#
# Dependencia: pip install python-barcode pillow
#
# En urls.py agregar:
#   path('codigos-barras/',                views.codigos_barras,          name='codigos-barras'),
#   path('codigos-barras/svg/<int:pk>/',   views.barcode_svg,             name='barcode-svg'),
#   path('codigos-barras/buscar/',         views.buscar_por_codigo,       name='buscar-por-codigo'),
#   path('codigos-barras/hoja/<str:ids>/', views.hoja_impresion_barras,   name='hoja-impresion-barras'),
# ─────────────────────────────────────────────────────────────────────────────

import io
import re
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required

# python-barcode (pip install python-barcode pillow)
from barcode import Code128
from barcode.writer import SVGWriter


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _get_negocio(request):
    """Devuelve el negocio del usuario o None."""
    perfil = getattr(request.user, 'perfil', None)
    return perfil.negocio if perfil else None


def _generar_svg_barcode(codigo: str) -> str:
    """
    Genera el SVG de un código Code-128 y devuelve el string SVG limpio
    (sin la cabecera XML <?xml ...?> para poder incrustarlo en HTML).
    """
    buf = io.BytesIO()
    options = {
        'write_text': True,
        'font_size':  10,
        'text_distance': 4,
        'quiet_zone': 4,
        'module_height': 14,
        'module_width': 0.9,
    }
    Code128(codigo, writer=SVGWriter()).write(buf, options=options)
    svg_bytes = buf.getvalue().decode('utf-8')

    # Quitar cabecera XML, DOCTYPE y comentarios ANTES del <svg>
    # para poder incrustar el SVG inline en el HTML sin que Django
    # lo muestre como texto plano. Usar |safe en el template.
    svg_bytes = re.sub(r'<\?xml[^?]*\?>', '', svg_bytes, flags=re.DOTALL)
    svg_bytes = re.sub(r'<!DOCTYPE[^>]*>', '', svg_bytes, flags=re.DOTALL | re.IGNORECASE)
    svg_bytes = re.sub(r'<!--.*?-->', '', svg_bytes, flags=re.DOTALL)

    # Empezar exactamente en el tag <svg
    idx = svg_bytes.find('<svg')
    if idx > 0:
        svg_bytes = svg_bytes[idx:]

    return svg_bytes.strip()


# ── VISTA 1: Panel de Códigos de Barras ──────────────────────────────────────

@login_required
def codigos_barras(request):
    """
    Panel principal:
    - Muestra todos los productos con sus códigos de barras (SVG inline).
    - Permite buscar/filtrar productos.
    - Botón para abrir el escáner de cámara (JS puro).
    - Selección múltiple para imprimir hoja de etiquetas.
    Acceso: Bodeguero, Gerente, Administrador.
    Template: app/barras/codigos_barras.html
    """
    negocio = _get_negocio(request)
    if not negocio:
        return HttpResponse("Su usuario no posee un Perfil de Negocio asignado.")

    search = request.GET.get('q', '').strip()
    sin_codigo = request.GET.get('sin_codigo', '')

    from .models import Producto
    from django.db.models import Q

    productos_qs = (
        Producto.objects
        .filter(activo=True, negocio=negocio)
        .order_by('nombre')
    )

    if search:
        productos_qs = productos_qs.filter(
            Q(nombre__icontains=search) | Q(codigo_barras__icontains=search)
        )

    if sin_codigo:
        productos_qs = productos_qs.filter(
            Q(codigo_barras='') | Q(codigo_barras__isnull=True)
        )

    # Pre-generar SVG para cada producto que tenga código de barras
    productos_data = []
    for p in productos_qs:
        svg = None
        if p.codigo_barras and p.codigo_barras.strip():
            try:
                svg = _generar_svg_barcode(p.codigo_barras.strip())
            except Exception:
                svg = None
        productos_data.append({
            'producto': p,
            'svg': svg,
        })

    total = len(productos_data)
    con_codigo = sum(1 for d in productos_data if d['svg'])
    sin_codigo_count = total - con_codigo

    return render(request, 'app/barras/codigos_barras.html', {
        'productos_data':    productos_data,
        'search':            search,
        'sin_codigo':        sin_codigo,
        'total':             total,
        'con_codigo':        con_codigo,
        'sin_codigo_count':  sin_codigo_count,
    })


# ── VISTA 2: SVG individual de un producto (respuesta HTTP directa) ───────────

@login_required
def barcode_svg(request, pk):
    """
    Devuelve el SVG del código de barras de un producto como respuesta HTTP.
    Útil para <img src="{% url 'barcode-svg' producto.pk %}">
    o para descarga directa.
    """
    negocio = _get_negocio(request)
    if not negocio:
        return HttpResponse(status=403)

    from .models import Producto
    producto = get_object_or_404(Producto, pk=pk, negocio=negocio)

    if not producto.codigo_barras:
        return HttpResponse("Este producto no tiene código de barras asignado.", status=404)

    try:
        buf = io.BytesIO()
        options = {
            'write_text': True,
            'font_size':  12,
            'text_distance': 5,
            'quiet_zone': 6,
            'module_height': 15,
        }
        Code128(producto.codigo_barras, writer=SVGWriter()).write(buf, options=options)
        svg_content = buf.getvalue()

        descargar = request.GET.get('download', '')
        if descargar:
            response = HttpResponse(svg_content, content_type='image/svg+xml')
            nombre_archivo = re.sub(r'[^\w\-]', '_', producto.nombre)
            response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}_{producto.codigo_barras}.svg"'
            return response

        return HttpResponse(svg_content, content_type='image/svg+xml')
    except Exception as e:
        return HttpResponse(f"Error generando código: {e}", status=500)


# ── VISTA 3: API JSON – buscar producto por código escaneado ──────────────────

@login_required
def buscar_por_codigo(request):
    """
    Endpoint AJAX que recibe un código de barras (GET ?codigo=XXX)
    y devuelve el JSON del producto si existe en el negocio.
    Lo usa el escáner de cámara en el frontend.
    """
    negocio = _get_negocio(request)
    if not negocio:
        return JsonResponse({'found': False, 'error': 'Sin negocio asignado'}, status=403)

    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'found': False, 'error': 'Código vacío'})

    from .models import Producto
    try:
        producto = Producto.objects.get(
            codigo_barras=codigo,
            negocio=negocio,
            activo=True,
        )
        return JsonResponse({
            'found': True,
            'id':           producto.pk,
            'nombre':       producto.nombre,
            'codigo':       producto.codigo_barras,
            'stock_actual': float(producto.stock_actual),
            'precio_venta': float(producto.precio_venta),
            'stock_bajo':   producto.stock_bajo,
        })
    except Producto.DoesNotExist:
        return JsonResponse({'found': False, 'error': f'Código "{codigo}" no encontrado'})
    except Producto.MultipleObjectsReturned:
        return JsonResponse({'found': False, 'error': 'Código duplicado en el sistema'})


# ── VISTA 4: Hoja de impresión de etiquetas (múltiple) ───────────────────────

@login_required
def hoja_impresion_barras(request, ids):
    """
    Genera una página lista para imprimir con los códigos de barras
    de los productos seleccionados (IDs separados por guión: /hoja/1-3-7/).
    Template: app/barras/hoja_impresion.html
    """
    negocio = _get_negocio(request)
    if not negocio:
        return HttpResponse(status=403)

    from .models import Producto
    try:
        pk_list = [int(x) for x in ids.split('-') if x.isdigit()]
    except ValueError:
        return HttpResponse("IDs inválidos", status=400)

    productos_qs = Producto.objects.filter(
        pk__in=pk_list,
        negocio=negocio,
        activo=True,
    )

    etiquetas = []
    for p in productos_qs:
        if p.codigo_barras and p.codigo_barras.strip():
            try:
                svg = _generar_svg_barcode(p.codigo_barras.strip())
                etiquetas.append({'producto': p, 'svg': svg})
            except Exception:
                pass

    copias = int(request.GET.get('copias', 1))
    etiquetas_final = etiquetas * copias

    return render(request, 'app/barras/hoja_impresion.html', {
        'etiquetas': etiquetas_final,
        'copias':    copias,
    })


    import json
from django.http import JsonResponse
# Asegúrate de importar tus modelos Categoria y Proveedor
# from .models import Categoria, Proveedor 

def api_crear_categoria(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre')
            if nombre:
                perfil = getattr(request.user, 'perfil', None)
                negocio = perfil.negocio if perfil else None
                categoria = Categoria.objects.create(nombre=nombre, negocio=negocio)
                return JsonResponse({'success': True, 'id': categoria.id, 'nombre': categoria.nombre})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

def api_crear_proveedor(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre')
            if nombre:
                perfil = getattr(request.user, 'perfil', None)
                negocio = perfil.negocio if perfil else None
                proveedor = Proveedor.objects.create(nombre=nombre, negocio=negocio)
                return JsonResponse({'success': True, 'id': proveedor.id, 'nombre': proveedor.nombre})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})