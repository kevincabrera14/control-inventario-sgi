import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import MovimientoInventario

logger = logging.getLogger(__name__)

@receiver(post_save, sender=MovimientoInventario)
def alert_stock_bajo(sender, instance, **kwargs):
    if instance.producto.stock_actual <= instance.producto.stock_minimo:
        logger.warning(f'Stock bajo para producto {instance.producto.nombre} (ID {instance.producto.id})')
