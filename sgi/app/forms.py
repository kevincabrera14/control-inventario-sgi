from django import forms
from django.contrib.auth import authenticate
from .models import Producto, Proveedor, MovimientoInventario
from django.core.exceptions import ValidationError


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get('username')
        password = cleaned.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise forms.ValidationError('Credenciales inválidas')

        return cleaned


class ProductoForm(forms.ModelForm):
    """Form for creating / editing Producto.
    Adds validation to guarantee that, within the same Negocio, the
    ``codigo_barras`` is unique.  The view passes the current Negocio
    via ``get_form_kwargs`` so the form can perform the check.
    """
    def __init__(self, *args, **kwargs):
        # ``negocio`` is supplied by the view; if not provided we keep ``None``
        self.negocio = kwargs.pop('negocio', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = Producto
        fields = '__all__'
        widgets = {
            'descripcion': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3}
            ),
        }

    def clean_codigo_barras(self):
        """Ensure the barcode is unique for the given negocio.
        An empty ``codigo_barras`` is considered invalid because multiple
        products with an empty string would violate the unique constraint.
        """
        codigo = self.cleaned_data.get('codigo_barras', '').strip()
        if not codigo:
            raise ValidationError('Debe ingresar un código de barras.')
        if self.negocio is None:
            return codigo
        qs = Producto.objects.filter(negocio=self.negocio, codigo_barras=codigo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Ya existe un producto con este código de barras en su negocio.')
        return codigo


class EntradaForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    cantidad = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    costo_unitario = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    referencia = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    observacion = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={'class': 'form-control', 'rows': 3}
        )
    )


class SalidaForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    cantidad = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    referencia = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    observacion = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={'class': 'form-control', 'rows': 3}
        )
    )


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = '__all__'
        widgets = {
            'descripcion': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3}
            ),
        }


class FiltroHistorialForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    tipo = forms.ChoiceField(
        choices=[('', '---')] + list(MovimientoInventario.TIPO_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )

    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )