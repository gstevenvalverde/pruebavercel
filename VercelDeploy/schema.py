import graphene
from graphene_django import DjangoObjectType
import pandas as pd
from graphene import ObjectType, Field, List, String, Float, Int
from inmueblesapp.models import Propiedad
from django.db import connection

class PropiedadType(DjangoObjectType):
    class Meta:
        model = Propiedad
        fields = (
            "id",
            "tipo",
            "localidad",
            "zona",
            "superficie",
            "metros_cuadrados_construidos",
            "valor",
            "visitas",
            "created_at",
            "fecha_de_venta",
        )

class PrecioPromedioPorlocalidadType(ObjectType):
    localidad = String()
    precio_promedio_por_m2 = Float()

class TasaConversionPorlocalidadType(ObjectType):
    localidad = String()
    tasa_conversion = Float()

class PromedioTiempoMercadoPorlocalidadType(ObjectType):
    localidad = String()
    promedio_dias_en_venta = Int()

class PropiedadesVendidasPorzonaType(ObjectType):
    zona = String()
    vendidos = Int()
    no_vendidos = Int()

class PrecioPromedioPorZonaType(ObjectType):
    zona = String()
    precio_promedio_por_m2 = Float()

class PromedioTiempoMercadoPorZonaType(ObjectType):
    zona = String()
    promedio_dias_en_venta = Float()

class zonaType(ObjectType):
    zona = String()

class TimeSeriesDataType(graphene.ObjectType):
    fecha = graphene.Date()
    valor = graphene.Float()

class SalesSummaryType(graphene.ObjectType):
    monthly_data = List(TimeSeriesDataType)
    yearly_data = List(TimeSeriesDataType)

class Query(graphene.ObjectType):
    propiedades = graphene.List(PropiedadType) # OK
    calcular_precio_promedio_por_localidad = List(PrecioPromedioPorlocalidadType)
    calcular_tasa_conversion_por_localidad = List(TasaConversionPorlocalidadType)
    calcular_promedio_tiempo_mercado_por_localidad = List(PromedioTiempoMercadoPorlocalidadType)

    propiedades_vendidas_por_zona = graphene.List(PropiedadesVendidasPorzonaType, zona=graphene.String(required=True))
    precio_m2_por_zona = graphene.List(PrecioPromedioPorZonaType, zona=graphene.String(required=True))
    calcular_promedio_tiempo_mercado_por_zona = graphene.List(PromedioTiempoMercadoPorZonaType, zona=graphene.String(required=True))
    obtener_zonas_unicas = graphene.List(zonaType)

    sales_summary = graphene.Field(SalesSummaryType)

    def resolve_propiedades(self, info):
        return Propiedad.objects.all()

    def resolve_calcular_precio_promedio_por_localidad(self, info):
        # Consulta SQL para cargar los datos desde PostgreSQL
        query = "SELECT valor, superficie, localidad FROM inmueblesapp_propiedad"
        data_frame = pd.read_sql_query(query, connection)

        # Evitar divisiones por cero
        data_frame = data_frame[data_frame['superficie'] > 0]

        # Calcular el precio por metro cuadrado para cada propiedad
        data_frame['precio_por_m2'] = (data_frame['valor'] / data_frame['superficie']).round(2)

        # Agrupar por localidad y calcular el precio por m2 promedio
        grouped_data = data_frame.groupby(['localidad'])['precio_por_m2'].mean().reset_index()

        # Convertir los resultados en una lista de objetos que GraphQL pueda devolver
        result = [
            {
                'localidad': row['localidad'],
                'precio_promedio_por_m2': row['precio_por_m2']
            }
            for _, row in grouped_data.iterrows()
        ]

        return result

    def resolve_calcular_tasa_conversion_por_localidad(self, info):
        # Consulta SQL para cargar los datos desde PostgreSQL
        query = "SELECT visitas, fecha_de_venta, localidad FROM inmueblesapp_propiedad"
        data_frame = pd.read_sql_query(query, connection)

        # Filtrar propiedades que han sido visitadas al menos una vez
        data_frame = data_frame[data_frame['visitas'] > 0]

        # Crear una columna que indique si la propiedad fue vendida (fecha_de_venta no es nulo)
        data_frame['vendido'] = data_frame['fecha_de_venta'].notnull()

        # Agrupar por localidad y calcular la tasa de conversión (porcentaje de vendidos respecto a visitados)
        grouped_data = data_frame.groupby('localidad').agg(
            total_visitados=('visitas', 'count'),
            total_vendidos=('vendido', 'sum')
        ).reset_index()

        # Calcular la tasa de conversión como porcentaje
        grouped_data['tasa_conversion'] = (grouped_data['total_vendidos'] / grouped_data['total_visitados']) * 100

        # Convertir los resultados en una lista de objetos que GraphQL pueda devolver
        result = [
            TasaConversionPorlocalidadType(
                localidad=row['localidad'],
                tasa_conversion=row['tasa_conversion']
            )
            for _, row in grouped_data.iterrows()
        ]

        return result

    def resolve_calcular_promedio_tiempo_mercado_por_localidad(self, info):
        # Consulta SQL para cargar los datos desde PostgreSQL
        query = "SELECT created_at, fecha_de_venta, localidad FROM inmueblesapp_propiedad WHERE fecha_de_venta IS NOT NULL"
        data_frame = pd.read_sql_query(query, connection)

        # Convertir las columnas de fecha a tipo datetime
        data_frame['created_at'] = pd.to_datetime(data_frame['created_at'])
        data_frame['fecha_de_venta'] = pd.to_datetime(data_frame['fecha_de_venta'])

        # Calcular la diferencia en días entre la fecha de venta y la fecha de publicación
        data_frame['dias_en_venta'] = (data_frame['fecha_de_venta'] - data_frame['created_at']).dt.days

        # Agrupar por localidad y calcular el promedio de días en venta
        grouped_data = data_frame.groupby(['localidad'])['dias_en_venta'].mean().reset_index()

        # Entero del promedio de días en venta
        grouped_data['dias_en_venta'] = grouped_data['dias_en_venta'].astype(int)

        # Convertir los resultados en una lista de objetos que GraphQL pueda devolver
        result = [
            PromedioTiempoMercadoPorlocalidadType(
                localidad=row['localidad'],
                promedio_dias_en_venta=row['dias_en_venta']
            )
            for _, row in grouped_data.iterrows()
        ]

        return result

    def resolve_propiedades_vendidas_por_zona(self, info, zona):
        # Obtén la cantidad de propiedades vendidas y no vendidas para la zona solicitada
        total_vendidos = Propiedad.objects.filter(zona=zona, fecha_de_venta__isnull=False).count()
        total_no_vendidos = Propiedad.objects.filter(zona=zona, fecha_de_venta__isnull=True).count()

        # Estructura los datos en el formato solicitado
        result = [PropiedadesVendidasPorzonaType(
                zona = zona,
                vendidos = total_vendidos,
                no_vendidos= total_no_vendidos,
            )]

        return result

    def resolve_precio_m2_por_zona(self, info, zona):
        # Extrae las propiedades en la zona específica
        propiedades = Propiedad.objects.filter(zona=zona).values('zona', 'valor', 'superficie')

        # Convierte los resultados a un DataFrame de Pandas
        df = pd.DataFrame(list(propiedades))

        # Verifica que el DataFrame no esté vacío
        if df.empty:
            return PrecioPromedioPorZonaType(zona=zona, precio_promedio_por_m2=None)

        # Filtra filas sin valores de `superficie` o `valor`
        df = df[(df['superficie'] > 0) & (df['valor'] > 0)]

        # Calcula el precio promedio por metro cuadrado
        df['precio_por_m2'] = df['valor'] / df['superficie']
        precio_promedio_por_m2 = round(df['precio_por_m2'].mean(), 2)

        # Estructura los datos en el formato solicitado
        result = [PrecioPromedioPorZonaType(
            zona=zona,
            precio_promedio_por_m2=precio_promedio_por_m2
        )]
        return result

    def resolve_calcular_promedio_tiempo_mercado_por_zona(self, info, zona):
        # Consulta SQL para cargar los datos de propiedades vendidas de la zona especificada
        query = f"""
        SELECT created_at, fecha_de_venta, zona 
        FROM inmueblesapp_propiedad 
        WHERE fecha_de_venta IS NOT NULL AND zona = %s
        """
        data_frame = pd.read_sql_query(query, connection, params=[zona])

        # Verifica que haya datos en la zona especificada
        if data_frame.empty:
            return []

        # Convertir las columnas de fecha a tipo datetime
        data_frame['created_at'] = pd.to_datetime(data_frame['created_at'])
        data_frame['fecha_de_venta'] = pd.to_datetime(data_frame['fecha_de_venta'])

        # Calcular la diferencia en días entre la fecha de venta y la fecha de publicación
        data_frame['dias_en_venta'] = (data_frame['fecha_de_venta'] - data_frame['created_at']).dt.days

        # Calcular el promedio de días en venta para la zona
        promedio_dias_en_venta = round(data_frame['dias_en_venta'].mean(), 2)

        # Convertir los resultados en una lista de objetos que GraphQL pueda devolver
        result = [
            PromedioTiempoMercadoPorZonaType(
                zona=zona,
                promedio_dias_en_venta=promedio_dias_en_venta  # Redondear a dos decimales
            )
        ]

        return result

    def resolve_obtener_zonas_unicas(self, info):
        # Realiza la consulta para obtener zonas únicas desde la base de datos
        zonas_unicas = Propiedad.objects.values('zona').distinct()

        # Convertir el resultado a una lista de objetos de tipo zonaType
        result = [zonaType(zona=z['zona']) for z in zonas_unicas]

        return result

    def resolve_sales_summary(self, info):
        # Extraer los datos de la base de datos
        ventas = Propiedad.objects.filter(fecha_de_venta__isnull=False).values('fecha_de_venta', 'valor')

        # Crear un DataFrame a partir de los datos de la base de datos
        df = pd.DataFrame(list(ventas))
        df['fecha_de_venta'] = pd.to_datetime(df['fecha_de_venta'])

        # Agrupación por mes (Año y Mes) y sumatoria de ventas
        df['month'] = df['fecha_de_venta'].dt.to_period('M')  # Agrupar por Año-Mes
        monthly_summary = (
            df.groupby('month')['valor'].sum()
            .reset_index()
            .sort_values('month')
        )

        # Convertir los datos de mes a un formato compatible con GraphQL
        monthly_data = [
            TimeSeriesDataType(
                fecha=period.to_timestamp().date(),
                valor=precio
            )
            for period, precio in zip(monthly_summary['month'], monthly_summary['valor'])
        ]

        # Agrupación por año y sumatoria de ventas
        df['year'] = df['fecha_de_venta'].dt.to_period('Y')  # Agrupar solo por Año
        yearly_summary = (
            df.groupby('year')['valor'].sum()
            .reset_index()
            .sort_values('year')
        )

        # Convertir los datos de año a un formato compatible con GraphQL
        yearly_data = [
            TimeSeriesDataType(
                fecha=period.to_timestamp().date(),
                valor=precio
            )
            for period, precio in zip(yearly_summary['year'], yearly_summary['valor'])
        ]

        # Retornar los datos como objeto SalesSummaryType
        return SalesSummaryType(monthly_data=monthly_data, yearly_data=yearly_data)

class CreatePropiedad(graphene.Mutation):
    class Arguments:
        id = graphene.ID()
        tipo = graphene.String()
        localidad = graphene.String()
        zona = graphene.String()
        superficie = graphene.String()
        metros_cuadrados_construidos = graphene.Float()
        valor = graphene.Float()
        visitas = graphene.Int()
        created_at = graphene.DateTime()
        fecha_de_venta = graphene.DateTime()

    propiedad = graphene.Field(PropiedadType)

    def mutate(self, info, **kwargs):
        propiedad = Propiedad.objects.create(**kwargs)
        return CreatePropiedad(propiedad=propiedad)

# Mutación para actualizar solo el campo fecha_de_venta
class UpdateDateSold(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        fecha_de_venta = graphene.Date(required=True)

    propiedad = graphene.Field(PropiedadType)

    def mutate(self, info, id, fecha_de_venta):
        propiedad = Propiedad.objects.get(id=id)
        propiedad.fecha_de_venta = fecha_de_venta
        propiedad.save()
        return UpdateDateSold(propiedad=propiedad)

# Mutación para incrementar el campo visitas en 1
class Incrementvisitas(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    propiedad = graphene.Field(PropiedadType)

    def mutate(self, info, id):
        propiedad = Propiedad.objects.get(id=id)
        propiedad.visitas += 1
        propiedad.save()
        return Incrementvisitas(propiedad=propiedad)

# Clase Mutation que agrupa todas las mutaciones
class Mutation(graphene.ObjectType):
    create_propiedad = CreatePropiedad.Field()
    update_fecha_de_venta = UpdateDateSold.Field()
    increment_visitas = Incrementvisitas.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)