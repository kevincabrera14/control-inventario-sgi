from django.shortcuts import render, redirect, get_object_or_404
from django.db import models, IntegrityError
from django.urls import reverse_lazy, reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db import transaction
from django.db.models import F, Sum, Count
from decimal import Decimal
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import date, timedelta
import json
from .models import Producto, MovimientoInventario, Categoria, Proveedor, Negocio, PerfilUsuario, DispositivoRecordado, Venta
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
DEVICE_COOKIE_NAME = 'sgi_device_token'
DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 año
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
                request.session.set_expiry(60 * 60 * 24 * 30)  # sesión normal: 30 días
                response = redirect('dashboard')
                # Generar y guardar el token de "dispositivo recordado"
                dispositivo = DispositivoRecordado.generar_para(
                    user, user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                response.set_cookie(
                    DEVICE_COOKIE_NAME,
                    dispositivo.token,
                    max_age=DEVICE_COOKIE_MAX_AGE,
                    httponly=True,
                    samesite='Lax',
                )
                return response
        return render(request, 'app/login.html', {'form': form, 'error': 'Credenciales inválidas'})
def logout_view(request):
    # Logout normal: cierra la sesión actual de Django.
    # NO se borra la cookie 'sgi_device_token' a propósito: el dispositivo
    # sigue recordado y el middleware volverá a loguear automáticamente
    # en la próxima visita, sin pedir credenciales.
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
    success_url = reverse_lazy('producto-list')
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
    # ------------------------------------------------------------------
    # Totales por método de pago (corte de caja)
    # ------------------------------------------------------------------
    # 1️⃣ Ingresos (entradas) – se calculan usando `costo_unitario`
    ingresos_qs = MovimientoInventario.objects.filter(
            producto__negocio=negocio,
        tipo='E',
            fecha__date__gte=fecha_desde_obj,
            fecha__date__lte=fecha_hasta_obj,
    ).values('payment_method').annotate(total=Sum(F('cantidad') * F('costo_unitario')))
    # 2️⃣ Egresos (salidas) – se calculan usando `precio_unitario_venta`
    egresos_qs = MovimientoInventario.objects.filter(
            producto__negocio=negocio,
            tipo='S',
            fecha__date__gte=fecha_desde_obj,
            fecha__date__lte=fecha_hasta_obj,
    ).values('payment_method').annotate(total=Sum(F('cantidad') * F('precio_unitario_venta')))
    # Inicializar dicts con ceros para asegurar todas las claves
    ingresos_dict = {'E': 0, 'N': 0, 'B': 0, 'O': 0}
    egresos_dict = {'E': 0, 'N': 0, 'B': 0, 'O': 0}
    for entry in ingresos_qs:
        ingresos_dict[entry['payment_method']] = entry['total'] or 0
    for entry in egresos_qs:
        egresos_dict[entry['payment_method']] = entry['total'] or 0
    # Net total por método (ingreso - egreso)
    corte_dict = {k: ingresos_dict.get(k, 0) - egresos_dict.get(k, 0) for k in ingresos_dict}
    # Guardar también los subtotales por separado para la plantilla
    corte_ingreso = ingresos_dict
    corte_egreso = egresos_dict
    # Agrupar movimientos por día usando Python para incluir detalle completo
    from collections import defaultdict
    dias = defaultdict(lambda: {'movimientos': [], 'total_items': 0, 'total_unidades': 0})
    for mov in movimientos_ventas:
        dia_key = mov.fecha.date()
        dias[dia_key]['movimientos'].append(mov)
        dias[dia_key]['total_items'] += 1
        dias[dia_key]['total_unidades'] += float(mov.cantidad)
        # Acumular ingresos por método de pago (ventas)
        ingresos_diario = dias[dia_key].setdefault('ingresos_por_metodo', {'E': 0, 'N': 0, 'B': 0, 'O': 0})
        precio_unitario = mov.precio_unitario_venta if mov.precio_unitario_venta is not None else mov.producto.precio_venta
        monto = float(mov.cantidad) * float(precio_unitario)
        ingresos_diario[mov.payment_method] = ingresos_diario.get(mov.payment_method, 0) + monto
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
    # Totales por método de pago (corte de caja)
        'corte_efectivo': corte_dict.get('E', 0),
        'corte_nequi': corte_dict.get('N', 0),
        'corte_bancolombia': corte_dict.get('B', 0),
        'corte_otros': corte_dict.get('O', 0),
        # Subtotales ingresos y egresos por método
        'corte_ingreso_efectivo': corte_ingreso.get('E', 0),
        'corte_egreso_efectivo': corte_egreso.get('E', 0),
        'corte_ingreso_nequi': corte_ingreso.get('N', 0),
        'corte_egreso_nequi': corte_egreso.get('N', 0),
        'corte_ingreso_bancolombia': corte_ingreso.get('B', 0),
        'corte_egreso_bancolombia': corte_egreso.get('B', 0),
        'corte_ingreso_otros': corte_ingreso.get('O', 0),
        'corte_egreso_otros': corte_egreso.get('O', 0),
        'corte_total': sum(corte_dict.values()),
    }
    return render(request, 'app/bodeguero/reportes_ventas.html', context)
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
# ── ALIASES DE COMPATIBILIDAD CON URLs.PY antiguas ───────────────────
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
# NUEVAS VISTAS: Checkout y Ticket
@login_required
@require_POST
def preparar_checkout(request):
    """
    Recibe el carrito vía JSON, lo guarda en la sesión y devuelve la URL del checkout.
    """
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        request.session['pending_cart'] = items
        request.session.modified = True
        return JsonResponse({'success': True, 'checkout_url': reverse('checkout-venta')})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
@login_required
def checkout_venta(request):
    """
    GET  → muestra formulario de pago (template checkout_venta.html)
    POST → crea Venta, MovimientoInventario y redirige al ticket.
    """
    # Obtener carrito guardado en sesión
    cart = request.session.get('pending_cart', [])
    if not cart:
        # Si el carrito está vacío, volver al POS
        return redirect('dashboard_bodeguero')
    # Preparar datos para el template
    cart_items = []
    total_bruto = Decimal('0')
    for it in cart:
        try:
            producto = Producto.objects.get(pk=it['producto_id'])
        except Producto.DoesNotExist:
            continue
        cantidad = Decimal(str(it.get('cantidad', 1)))
        subtotal = producto.precio_venta * cantidad
        total_bruto += subtotal
        cart_items.append({
            'nombre': producto.nombre,
            'precio_venta': producto.precio_venta,
            'cantidad': cantidad,
            'subtotal': subtotal,
            'producto_id': producto.pk,
        })
    if request.method == 'GET':
        return render(request, 'app/bodeguero/checkout_venta.html', {
            'cart_items': cart_items,
            'total_bruto': total_bruto,
        })
    # ---- POST: procesar pago y crear registros ----
    cliente = request.POST.get('cliente_nombre', '').strip() or None
    payment_method = request.POST.get('payment_method', 'E')
    desconto = Decimal(request.POST.get('desconto') or 0)
    # Calcular total neto (bruto - descuento)
    total_neto = total_bruto - desconto
    # Tomar IVA del primer producto (asume mismo IVA para todos)
    iva_percent = 0
    if cart_items:
        first_prod = Producto.objects.get(pk=cart_items[0]['producto_id'])
        iva_percent = first_prod.iva
    perfil = getattr(request.user, 'perfil', None)
    negocio = perfil.negocio if perfil else None
    with transaction.atomic():
        # Bloquea la fila del negocio para asignar el siguiente número de
        # factura sin colisiones si dos bodegueros hacen checkout al mismo tiempo.
        negocio_lock = Negocio.objects.select_for_update().get(pk=negocio.pk)
        numero_factura = negocio_lock.siguiente_numero_factura
        negocio_lock.siguiente_numero_factura = numero_factura + 1
        negocio_lock.save(update_fields=['siguiente_numero_factura'])
        # Crear registro de venta
        venta = Venta.objects.create(
            negocio=negocio,
            numero_factura=numero_factura,
            usuario=request.user,
            cliente_nombre=cliente,
            descuento=desconto,
            iva=iva_percent,
            total_bruto=total_bruto,
            total_neto=total_neto,
            payment_method=payment_method,
        )
        # Registrar cada movimiento y actualizar stock
        for item in cart_items:
            prod = Producto.objects.select_for_update().get(pk=item['producto_id'])
            qty = Decimal(str(item['cantidad']))
            stock_antes = prod.stock_actual
            prod.stock_actual = prod.stock_actual - qty
            prod.save()
            MovimientoInventario.objects.create(
                producto=prod,
                    tipo='S',
                cantidad=qty,
                costo_unitario=Decimal('0'),
                precio_unitario_venta=prod.precio_venta,
                stock_antes=stock_antes,
                stock_despues=prod.stock_actual,
                referencia='Venta POS',
                usuario=request.user,
                payment_method=payment_method,
                venta=venta,
            )
    # Limpiar carrito de la sesión
    request.session.pop('pending_cart', None)
    return redirect('ticket-venta', venta_id=venta.id)
@login_required
def ticket_venta(request, venta_id):
    """
    Muestra el ticket listo para imprimir en impresoras POS (80mm / 58mm).
    """
    perfil = getattr(request.user, 'perfil', None)
    negocio = perfil.negocio if perfil else None
    venta = get_object_or_404(Venta, pk=venta_id, negocio=negocio)
    movimientos = venta.movimientos.select_related('producto')
    # Se arma la lista de líneas con el precio vigente EN EL MOMENTO DE LA VENTA.
    # Fallback a precio_venta actual solo para ventas antiguas creadas antes de
    # que existiera el campo precio_unitario_venta.
    items = []
    for mov in movimientos:
        precio_unitario = mov.precio_unitario_venta
        if precio_unitario is None:
            precio_unitario = mov.producto.precio_venta
        items.append({
            'nombre': mov.producto.nombre,
            'cantidad': mov.cantidad,
            'precio_unitario': precio_unitario,
            'subtotal': mov.cantidad * precio_unitario,
        })
    return render(request, 'app/bodeguero/ticket_pos.html', {
        'venta': venta,
        'items': items,
    })
# ─────────────────────────────────────────────────────────────────────────────
# NUEVAS VISTAS: Checkout y Ticket




