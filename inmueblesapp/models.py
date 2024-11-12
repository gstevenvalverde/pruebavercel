from django.db import models

# Create your models here.
class Propiedad(models.Model):
    id = models.AutoField(primary_key=True)  # AutoField para el ID
    created_at = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=50)  # Ej: 'Casa', 'Departamento', 'Terreno'
    localidad = models.CharField(max_length=100)  # Ejemplo: ciudad o región
    zona = models.CharField(max_length=100)  # Ejemplo: barrio o sector específico
    superficie = models.DecimalField(max_digits=10, decimal_places=2)  # En metros cuadrados
    metros_cuadrados_construidos = models.DecimalField(max_digits=10, decimal_places=2)  # En metros cuadrados
    valor = models.DecimalField(max_digits=15, decimal_places=2)  # Valor estimado en moneda local
    visitas = models.IntegerField(null=True, blank=True)  # Permitir que sea nulo
    fecha_de_venta = models.DateTimeField(null=True, blank=True)  # Permitir que sea nulo

