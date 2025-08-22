# Visor de Información Geoespacial de Precipitación
# Creado para el análisis de datos climáticos y su correlación con eventos ENSO.
import streamlit as st
import pandas as pd
import altair as alt
import folium
from streamlit_folium import folium_static
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
import zipfile
import tempfile
import os
import io
import requests
import numpy as np
from datetime import datetime

# --- Configuración de la página ---
st.set_page_config(layout="wide", page_title="Visor de Precipitación y ENSO", page_icon=" ☔ ")

# --- URLs de GitHub para carga automática de datos (solo como fallback) ---
GITHUB_BASE_URL = "https://raw.githubusercontent.com/juancami94/Visor_Lluvia_ENSO/main/"
SHAPEFILE_URL = "https://github.com/juancami94/Visor_Lluvia_ENSO/raw/main/mapaCV.zip"

# --- Funciones de carga de datos ---
def load_data(file_type, file_path, sep=';'):
    """
    Carga datos desde un archivo local o una URL de GitHub.
    Soporta archivos CSV con diferentes delimitadores.
    """
    try:
        if file_type == 'local':
            if file_path.name.endswith('.csv'):
                return pd.read_csv(file_path, sep=sep, encoding='latin1')
            else:
                st.error("Formato de archivo no soportado. Por favor, suba un archivo CSV.")
                return None
        elif file_type == 'github':
            url = GITHUB_BASE_URL + file_path
            response = requests.get(url)
            if response.status_code == 200:
                return pd.read_csv(io.StringIO(response.content.decode('utf-8')), sep=sep, encoding='utf-8')
            else:
                st.error(f"Error al descargar el archivo desde GitHub: {url}")
                return None
        else:
            return None
    except Exception as e:
        st.error(f"Ocurrió un error al cargar los datos: {e}")
        return None

def load_shapefile(file_type, file_path):
    """
    Carga un shapefile desde un archivo .zip local o una URL de GitHub,
    asigna el CRS correcto y lo convierte a WGS84.
    """
    try:
        if file_type == 'local':
            zip_file_obj = file_path
        elif file_type == 'github':
            st.info("Descargando shapefile desde GitHub...")
            response = requests.get(SHAPEFILE_URL)
            if response.status_code != 200:
                st.error("Error al descargar el shapefile de GitHub.")
                return None
            zip_file_obj = io.BytesIO(response.content)
        else:
            return None

        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_file_obj, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            shp_path = [f for f in os.listdir(temp_dir) if f.endswith('.shp')][0]
            
            # Cargar el shapefile sin CRS asignado
            gdf = gpd.read_file(os.path.join(temp_dir, shp_path))
            
            # Asignar el CRS correcto (MAGNA-SIRGAS, EPSG:9377)
            gdf.set_crs("EPSG:9377", inplace=True)
            
            # Convertir a WGS84 (EPSG:4326) para Folium
            gdf = gdf.to_crs("EPSG:4326")
            return gdf

    except Exception as e:
        st.error(f"Error al procesar el shapefile: {e}")
        return None

# --- Función para cargar los datos ---
@st.cache_data
def load_all_data(df_precip_anual, df_enso, df_precip_mensual, gdf):
    """Retorna los datos cargados."""
    return df_precip_anual, df_enso, df_precip_mensual, gdf

# --- Interfaz de usuario ---
st.title('☔ Visor de Precipitación y Fenómeno ENSO')
st.markdown("""
Esta aplicación interactiva permite visualizar y analizar datos de precipitación
y su correlación con los eventos climáticos de El Niño-Oscilación del Sur (ENSO).
""")

# --- Panel de control (sidebar) ---
st.sidebar.header("Panel de Control")
st.sidebar.markdown("Por favor, suba los archivos requeridos para comenzar.")

# Carga de archivos manual
uploaded_file_mapa = st.sidebar.file_uploader("1. Cargar archivo de estaciones (mapaCVENSO.csv)", type="csv")
uploaded_file_enso = st.sidebar.file_uploader("2. Cargar archivo de ENSO (ENSO_1950_2023.csv)", type="csv")
uploaded_file_precip = st.sidebar.file_uploader("3. Cargar archivo de precipitación mensual (DatosPptnmes_ENSO.csv)", type="csv")
uploaded_zip_shapefile = st.sidebar.file_uploader("4. Cargar shapefile (.zip)", type="zip")

# Proceso de carga de datos
df_precip_anual = None
df_enso = None
df_precip_mensual = None
gdf = None

if uploaded_file_mapa and uploaded_file_enso and uploaded_file_precip and uploaded_zip_shapefile:
    df_precip_anual = load_data('local', uploaded_file_mapa)
    df_enso = load_data('local', uploaded_file_enso)
    df_precip_mensual = load_data('local', uploaded_file_precip)
    gdf = load_shapefile('local', uploaded_zip_shapefile)
else:
    st.info("Por favor, suba los 4 archivos para habilitar la aplicación.")
    st.stop()

# Verificación de carga de datos
if df_precip_anual is None or df_enso is None or df_precip_mensual is None or gdf is None:
    st.error("No se pudieron cargar los datos. Por favor, revise si los archivos son correctos.")
    st.stop()

# --- Preprocesamiento de datos de precipitación mensual ---
try:
    df_precip_mensual.columns = df_precip_mensual.columns.str.strip()
    df_precip_mensual = df_precip_mensual.rename(columns={'Id_Fecha': 'Fecha'})
    
    df_precip_mensual['Id_Fecha'] = pd.to_datetime(df_precip_mensual['Id_Fecha'], format='%d/%m/%Y')
    df_precip_mensual['año'] = df_precip_mensual['Id_Fecha'].dt.año
    df_precip_mensual['Mes'] = df_precip_mensual['Id_Fecha'].dt.month
    
    # Derretir el dataframe para tener un formato largo
    df_long = df_precip_mensual.melt(id_vars=['Id_Fecha', 'año', 'Mes'], var_name='Id_estacion', value_name='Precipitation')
    
    # Eliminar filas con valores 'n.d' y convertir la columna de precipitación a float
    df_long['Precipitation'] = df_long['Precipitation'].replace('n.d', np.nan).astype(float)
    df_long = df_long.dropna(subset=['Precipitation'])

except Exception as e:
    st.error(f"Error en el preprocesamiento del archivo de precipitación mensual: {e}")
    st.stop()

# --- Preprocesamiento de datos ENSO ---
try:
    df_enso['año'] = df_enso['año'].astype(int)
    # Crear una columna de Fecha para la fusión
    df_enso['Fecha_merge'] = pd.to_datetime(df_enso['año'].astype(str) + '-' + df_enso['mes'], format='%Y-%b')

except Exception as e:
    st.error(f"Error en el preprocesamiento del archivo ENSO: {e}")
    st.stop()
    
# --- Mapeo de estaciones ---
station_mapping = df_precip_anual[['Id_estacion', 'Nom_Est']].set_index('Id_estacion').to_dict()['Nom_Est']
df_long['Nom_Est'] = df_long['Id_estacion'].map(station_mapping)

# --- Controles en la barra lateral ---
staciones_list = sorted(df_precip_anual['Nom_Est'].unique())
selected_stations = st.sidebar.multiselect(
    'Seleccione una o varias estaciones', 
    options=staciones_list,
    default=staciones_list[:5]
)

# Filtro de años
años_disponibles = sorted(df_precip_anual.columns[2:54].astype(int).tolist())
año_range = st.sidebar.slider(
    "Seleccione el rango de años",
    min_value=min(años_disponibles),
    max_value=max(años_disponibles),
    value=(min(años_disponibles), max(años_disponibles))
)

# Filtro por municipio
municipios_list = sorted(df_precip_anual['municipio'].unique())
selected_municipios = st.sidebar.multiselect(
    'Filtrar por municipio',
    options=municipios_list,
    default=[]
)

# Aplicar filtros
if selected_municipios:
    filtered_stations_by_municipio = df_precip_anual[df_precip_anual['municipio'].isin(selected_municipios)]['Nom_Est'].tolist()
    filtered_stations = [s for s in selected_stations if s in filtered_stations_by_municipio]
else:
    filtered_stations = selected_stations

# --- Sección de Visualizaciones ---
st.header("Visualizaciones de Precipitación 💧")

# Gráfico de Serie de Tiempo Anual
st.subheader("Precipitación Anual Total (mm)")
df_precip_anual_filtered = df_precip_anual[df_precip_anual['Nom_Est'].isin(filtered_stations)].copy()
df_precip_anual_filtered = df_precip_anual_filtered.loc[:, df_precip_anual_filtered.columns.astype(str).str.contains('^Id_estacion|Nom_Est|\\d{4}$')]
df_precip_anual_filtered_melted = df_precip_anual_filtered.melt(
    id_vars=['Nom_Est'], 
    var_name='año', 
    value_name='Precipitación'
)
df_precip_anual_filtered_melted['año'] = df_precip_anual_filtered_melted['año'].astype(int)

# Filtrar por el rango de años
df_precip_anual_filtered_melted = df_precip_anual_filtered_melted[
    (df_precip_anual_filtered_melted['año'] >= año_range[0]) &
    (df_precip_anual_filtered_melted['año'] <= año_range[1])
]

if not df_precip_anual_filtered_melted.empty:
    chart_anual = alt.Chart(df_precip_anual_filtered_melted).mark_line().encode(
        x=alt.X('año:O', title='año'),
        y=alt.Y('Precipitación:Q', title='Precipitación Total (mm)'),
        color='Nom_Est:N',
        tooltip=['Nom_Est', 'año', 'Precipitación']
    ).properties(
        title='Precipitación Anual Total por Estación'
    ).interactive()
    st.altair_chart(chart_anual, use_container_width=True)
else:
    st.warning("No hay datos para las estaciones y el rango de años seleccionados.")

# Gráfico de Serie de Tiempo Mensual
st.subheader("Precipitación Mensual Total (mm)")
# Agrupar los datos mensuales por año, mes y estación
df_monthly_total = df_long.groupby(['Nom_Est', 'año', 'mes'])['Precipitation'].sum().reset_index()
df_monthly_total['Fecha'] = pd.to_datetime(df_monthly_total['año'].astype(str) + '-' + df_monthly_total['mes'].astype(str), format='%Y-%m')

# Filtrar por estaciones y años
df_monthly_filtered = df_monthly_total[
    (df_monthly_total['Nom_Est'].isin(filtered_stations)) &
    (df_monthly_total['año'] >= año_range[0]) &
    (df_monthly_total['año'] <= año_range[1])
]

if not df_monthly_filtered.empty:
    chart_mensual = alt.Chart(df_monthly_filtered).mark_line().encode(
        x=alt.X('Fecha:T', title='Fecha'),
        y=alt.Y('Precipitation:Q', title='Precipitación Total (mm)'),
        color='Nom_Est:N',
        tooltip=[alt.Tooltip('Fecha', format='%Y-%m'), 'Precipitation', 'Nom_Est']
    ).properties(
        title='Precipitación Mensual Total por Estación'
    ).interactive()
    st.altair_chart(chart_mensual, use_container_width=True)
else:
    st.warning("No hay datos mensuales para las estaciones y el rango de años seleccionados.")

# Mapa Interactivo (Folium)
st.subheader("Mapa de Estaciones de Lluvia en Colombia")
st.markdown("Ubicación de las estaciones seleccionadas.")

# Filtrar el GeoDataFrame
gdf_filtered = gdf[gdf['Nom_Est'].isin(filtered_stations)].copy()

if not gdf_filtered.empty:
    m = folium.Map(location=[gdf_filtered['Latitud'].mean(), gdf_filtered['Longitud'].mean()], zoom_start=6)

    for _, row in gdf_filtered.iterrows():
        folium.Marker(
            location=[row['Latitud'], row['Longitud']],
            tooltip=f"Estación: {row['Nom_Est']}<br>Municipio: {row['municipio']}<br>Porc. Datos: {row['Porc_datos']}",
            icon=folium.Icon(color="blue", icon="cloud-rain", prefix='fa')
        ).add_to(m)
    
    folium_static(m, width=900, height=600)
else:
    st.warning("No hay estaciones seleccionadas o datos de coordenadas para mostrar en el mapa.")

# Mapa Animado (Plotly)
st.subheader("Mapa Animado de Precipitación Anual")
st.markdown("Visualice la precipitación anual a lo largo del tiempo.")
if not df_precip_anual_filtered_melted.empty:
    fig_mapa_animado = px.scatter_geo(
        df_precip_anual_filtered_melted.merge(gdf_filtered, on='Nom_Est', how='inner'),
        lat='Latitud',
        lon='Longitud',
        color='Precipitación',
        size='Precipitación',
        hover_name='Nom_Est',
        animation_frame='año',
        projection='natural earth',
        title='Precipitación Anual de las Estaciones',
        color_continuous_scale=px.colors.sequential.RdBu
    )
    fig_mapa_animado.update_geos(
        fitbounds="locations",
        showcountries=True,
        countrycolor="black"
    )
    st.plotly_chart(fig_mapa_animado, use_container_width=True)
else:
    st.warning("No hay datos suficientes para generar el mapa animado.")

# --- Análisis ENSO ---
st.header("Análisis de Precipitación y el Fenómeno ENSO")
st.markdown("Esta sección explora la relación entre la precipitación y los eventos de El Niño-Oscilación del Sur.")

# Preparar los datos para el análisis
df_analisis = df_long.copy()

# Fusión con los datos ENSO
try:
    df_analisis['Fecha_merge'] = pd.to_datetime(df_analisis['Fecha'].dt.strftime('%Y-%b'))
    df_analisis = pd.merge(df_analisis, df_enso[['Fecha_merge', 'Anomalia_ONI', 'ENSO']], on='Fecha_merge', how='left')
    df_analisis = df_analisis.dropna(subset=['ENSO'])

    # Agrupar datos por evento ENSO
    df_enso_group = df_analisis.groupby('ENSO')['Precipitation'].mean().reset_index()
    df_enso_group = df_enso_group.rename(columns={'Precipitation': 'Precipitación'})

    # Gráfico de barras de Precipitación vs ENSO
    fig_enso = px.bar(
        df_enso_group,
        x='ENSO',
        y='Precipitación',
        title='Precipitación Media por Evento ENSO',
        labels={'ENSO': 'Evento ENSO', 'Precipitación': 'Precipitación Media (mm)'},
        color='ENSO'
    )
    st.plotly_chart(fig_enso, use_container_width=True)

    # Correlación entre Anomalía ONI y precipitación
    df_corr = df_analisis[['Anomalia_ONI', 'Precipitation']].dropna()
    if not df_corr.empty:
        correlation = df_corr['Anomalia_ONI'].corr(df_corr['Precipitation'])
        st.write(f"### Coeficiente de Correlación entre Anomalía ONI y Precipitación: **{correlation:.2f}**")
        st.info("""
        **Interpretación:**
        - Un valor cercano a 1 indica una correlación positiva fuerte (a mayor ONI, mayor precipitación).
        - Un valor cercano a -1 indica una correlación negativa fuerte (a mayor ONI, menor precipitación).
        - Un valor cercano a 0 indica una correlación débil o nula.
        """)
    else:
        st.warning("No hay suficientes datos para calcular la correlación.")

except Exception as e:
    st.error(f"Error en el análisis ENSO: {e}")
