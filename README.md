# 📦 SGI — Sistema de Gestión de Inventario

Aplicación web multi-negocio para control de inventario, ventas y reportes, construida con Django. Permite administrar productos, proveedores, movimientos de stock y usuarios con distintos roles, todo desde el navegador (incluye instalación como PWA en Android, iPhone y escritorio).

**🔗 Demo en vivo:** [web-production-6eae7.up.railway.app](https://web-production-6eae7.up.railway.app/)

> La demo corre en el plan gratuito de Railway: la primera carga puede tardar unos segundos mientras el servidor "despierta".


## ✨ Características principales

- **Control de stock en tiempo real**: el inventario se actualiza automáticamente con cada entrada o salida de mercancía.
- **Alertas de stock bajo**: cada producto tiene un mínimo configurable; el sistema avisa cuando está por agotarse.
- **Escáner de código de barras**: registro de productos usando la cámara del celular/tablet o un lector físico USB, además de generación e impresión de códigos.
- **Punto de venta simplificado**: búsqueda de producto, carrito con cantidades y confirmación de salida en un flujo de pocos clics.
- **Reversión de movimientos**: cualquier entrada o salida puede revertirse, restaurando el stock y conservando el historial.
- **Reportes exportables**: inventario, stock bajo y movimientos en Excel y PDF.
- **Multi-negocio**: un mismo sistema puede administrar varias tiendas o bodegas, cada una con sus propios productos, usuarios y reportes aislados entre sí.
- **Acceso por roles** (Administrador / Gerente / Bodeguero), cada uno con una vista y permisos distintos.
- **Progressive Web App**: instalable en Android, iPhone y PC/Mac, con ícono propio y funcionamiento en pantalla completa.
- **Sesión recordada por dispositivo**: inicio de sesión persistente y seguro basado en tokens, sin depender solo de la cookie de sesión estándar de Django.

## 👥 Roles del sistema

| Rol | Puede hacer |
|---|---|
| **Bodeguero** | Vender con escáner, registrar entradas de mercancía, crear/editar productos, ver reporte de ventas del día, revertir ventas recientes |
| **Gerente** | Todo lo del Bodeguero + dashboard con indicadores, historial financiero, proyecciones de utilidades, exportación de reportes |
| **Administrador** | Todo lo anterior + gestión de negocios/sucursales, creación de usuarios y asignación de roles |

## 🛠️ Stack tecnológico

| Área | Tecnología |
|---|---|
| Backend | Python 3, Django 4.2 |
| Base de datos | PostgreSQL en producción (Railway) · SQLite en desarrollo |
| Servidor de aplicación | Gunicorn |
| Archivos estáticos | WhiteNoise |
| Reportes | openpyxl (Excel), ReportLab (PDF) |
| Códigos de barra | python-barcode + Pillow |
| Frontend | Templates de Django, CSS, JavaScript |
| PWA | Web App Manifest + Service Worker |
| Despliegue | Railway |

## 🏗️ Estructura del proyecto

```
sgi/
├── app/                        # Aplicación principal
│   ├── models.py               # Negocio, Producto, Categoria, Proveedor, MovimientoInventario...
│   ├── views.py                # Dashboard, productos, movimientos, reportes, códigos de barra
│   ├── forms.py
│   ├── urls.py
│   ├── middleware.py           # Dispositivo recordado (login persistente)
│   ├── admin.py
│   ├── signals.py
│   ├── utils.py
│   ├── fixtures/
│   │   └── fixtures.json       # Datos de ejemplo (categorías, productos...)
│   ├── management/commands/
│   │   ├── create_test_users.py    # Crea usuarios de prueba con roles asignados
│   │   └── seed.py                 # Carga las fixtures de ejemplo
│   ├── migrations/
│   ├── static/
│   │   ├── css/                # login.css, style.css
│   │   ├── img/                # logo.png
│   │   └── js/                 # js.js
│   └── templates/app/
│       ├── base.html, dashboard.html, login.html, informacion.html
│       ├── dashboard_admin.html, dashboard_gerente.html, dashboard_bodeguero.html
│       ├── productos/          # lista, form, detalle
│       ├── proveedores/        # lista, form, detalle
│       ├── movimientos/        # entrada, salida, historial
│       ├── barras/             # códigos de barra, hoja de impresión
│       ├── bodeguero/          # lista de productos, reportes de ventas, revertir venta
│       ├── gerente/            # historial financiero, stock, utilidades
│       ├── reportes/           # index de reportes
│       └── pwa/                # offline.html
├── config/                     # Configuración del proyecto (settings, urls, wsgi/asgi)
├── static/                     # Manifest e íconos de la PWA
│   ├── manifest.json
│   ├── sw.js
│   └── icons/
├── manage.py
├── Procfile                    # Comando de arranque para Railway
└── requirements.txt
```

## ⚙️ Instalación local

```bash
# 1. Clonar el repositorio
git clone https://github.com/kevincabrera14/control-inventario-sgi.git
cd control-inventario-sgi/sgi

# 2. Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate      # En Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp ../.env.example .env
# Edita .env con tus propios valores (SECRET_KEY, DEBUG, etc.)

# 5. Aplicar migraciones
python manage.py migrate

# 6. (Opcional) Crear usuarios de prueba con roles ya asignados
python manage.py create_test_users

# 7. Iniciar el servidor de desarrollo
python manage.py runserver
```

La aplicación quedará disponible en `http://127.0.0.1:8000/`.

## 🔑 Variables de entorno

Estas variables se definen en `.env` (ver `.env.example` como referencia):

| Variable | Descripción |
|---|---|
| `SECRET_KEY` | Clave secreta de Django. Genera una propia, nunca uses la de ejemplo en producción |
| `DEBUG` | `True` en desarrollo, `False` en producción |
| `ALLOWED_HOSTS` | Dominios permitidos, separados por coma |
| `DATABASE_URL` | Cadena de conexión a PostgreSQL (Railway la provee automáticamente) |
| `PORT` | Puerto en el que corre la aplicación (Railway lo asigna en runtime) |

## 🧪 Datos de prueba

El comando `create_test_users` crea los tres roles del sistema con usuarios de ejemplo, útil para probar el proyecto localmente sin capturar datos manualmente:

```bash
python manage.py create_test_users
```

> ⚠️ Estos usuarios usan contraseñas simples pensadas solo para desarrollo local. No ejecutes este comando en un entorno de producción con datos reales.

## 🚀 Despliegue

El proyecto está desplegado en [Railway](https://railway.app/), con PostgreSQL como base de datos y el siguiente flujo de arranque (`Procfile`):

```
web: python manage.py collectstatic --noinput && python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

## ✍️ Autor

**Kevin Cabrera**
https://github.com/kevincabrera14 · ka5849698@gmail.com  
