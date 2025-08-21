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

# --- Configuración de la página ---
st.set_page_config(layout="wide", page_title="Visor de Precipitación y ENSO", page_icon=" ☔ ")

# --- URLs de GitHub para carga automática de datos ---
GITHUB_BASE_URL = "https://raw.githubusercontent.com/TuUsuario/TuRepositorio/main/"
SHAPEFILE_URL = "https://github.com/TuUsuario/TuRepositorio/raw/main/mapaCV.zip"

# --- Funciones de carga de datos ---
def load_data(file_type, file_path, sep=';'):
    """
    Carga datos desde un archivo local o una URL de GitHub.
    Soporta archivos CSV con diferentes delimitadores.
    """
    try:
        if file_type == 'github':
            url = GITHUB_BASE_URL + file_path
            df = pd.read_csv(url, sep=sep)
        elif file_type == 'local':
            df = pd.read_csv(file_path, sep=sep)
        return df
    except Exception as e:
        st.error(f"Error al cargar el archivo {file_path}. Error: {e}")
        return None

def load_enso_data():
    """
    Carga datos de ENSO. Se utiliza una plantilla si el archivo no está disponible.
    """
    st.warning("El archivo 'ENSO_1950-2023.csv' no se encontró. Se usará un DataFrame de ejemplo. Por favor, reemplace esta sección con su archivo real para un análisis completo.")
    enso_data = {
        'Id_Fecha': pd.to_datetime(pd.date_range(start='1970-01-01', end='2021-12-01', freq='MS').strftime('%Y-%m-%d')),
        'Anomalia_ONI': np.random.uniform(-2.5, 2.5, size=624)
    }
    df_enso = pd.DataFrame(enso_data)
    return df_enso

def load_geospatial_data(file_type, file_url):
    """
    Carga archivos geoespaciales comprimidos (.zip).
    """
    try:
        if file_type == 'github':
            response = requests.get(file_url)
            zip_file = zipfile.ZipFile(io.BytesIO(response.content))
        elif file_type == 'local':
            zip_file = zipfile.ZipFile(file_url)
        
        # Extraer archivos .shp, .dbf, .shx a una carpeta temporal
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_file.extractall(temp_dir)
            
            # Buscar el shapefile
            shp_file = [f for f in os.listdir(temp_dir) if f.endswith('.shp')][0]
            shp_path = os.path.join(temp_dir, shp_file)
            
            # Leer el shapefile con geopandas
            gdf = gpd.read_file(shp_path)
            
            # Asegurar que las coordenadas estén en WGS84 (EPSG:4326)
            if gdf.crs and gdf.crs.name != 'WGS 84':
                st.info(f"Convirtiendo CRS de {gdf.crs.name} a WGS84...")
                gdf = gdf.to_crs(epsg=4326)
            
            # Crear las columnas de latitud y longitud
            gdf['Longitud'] = gdf.geometry.x
            gdf['Latitud'] = gdf.geometry.y
            
            return gdf

    except Exception as e:
        st.error(f"Error al cargar el shapefile: {e}")
        return None

# --- Función para preprocesar los datos de precipitación (wide to long format) ---
@st.cache_data
def preprocess_precipitation_data(df_ppt):
    """
    Transforma el DataFrame de precipitación del formato 'ancho' al 'largo'
    y realiza la limpieza de datos.
    """
    if 'Id_Fecha' not in df_ppt.columns:
        st.error("Error: La columna 'Id_Fecha' no se encuentra en el archivo de precipitación.")
        return pd.DataFrame()

    # Identificar columnas de estación
    station_columns = [col for col in df_ppt.columns if col != 'Id_Fecha']
    
    # Derretir el DataFrame (wide to long format)
    df_long = pd.melt(df_ppt, id_vars=['Id_Fecha'], value_vars=station_columns, var_name='Id_estacion', value_name='Precipitacion_mm')
    
    # Limpieza de datos
    df_long['Precipitacion_mm'] = pd.to_numeric(df_long['Precipitacion_mm'], errors='coerce')
    df_long['Precipitacion_mm'] = df_long['Precipitacion_mm'].fillna(0)
    
    # Conversión de fechas
    df_long['Id_Fecha'] = pd.to_datetime(df_long['Id_Fecha'], format='%d/%m/%Y', errors='coerce')
    df_long = df_long.dropna(subset=['Id_Fecha'])
    
    # Convertir 'Id_estacion' a string para asegurar la compatibilidad con el otro DataFrame
    df_long['Id_estacion'] = df_long['Id_estacion'].astype(str)

    # Extraer año y mes
    df_long['Año'] = df_long['Id_Fecha'].dt.year
    df_long['Mes'] = df_long['Id_Fecha'].dt.month
    
    return df_long

# --- Carga de datos principales ---
try:
    precip_file_content = open("DatosPptnmes_ENSO.csv", "rb").read()
    
    df_precip_wide = pd.read_csv(io.StringIO(precip_file_content.decode('utf-8')), sep=';', header=0)
    df_precip = preprocess_precipitation_data(df_precip_wide)
    
    # Cargar los datos de las estaciones directamente del shapefile
    gdf_estaciones = load_geospatial_data('local', 'mapaCV.zip')
    
    # Renombrar columnas para la unión
    if gdf_estaciones is not None:
        gdf_estaciones.rename(columns={'Id_estacion': 'Id_estacion_shp', 'Nom_Est': 'Nom_Est_shp'}, inplace=True)
        # Tomar los datos relevantes de las estaciones del shapefile
        df_estaciones_shp = gdf_estaciones[['Id_estacion_shp', 'Nom_Est_shp', 'municipio', 'Latitud', 'Longitud']]
        # Convertir 'Id_estacion' a string
        df_estaciones_shp['Id_estacion_shp'] = df_estaciones_shp['Id_estacion_shp'].astype(str)
    
    # ENSO data is missing, so we load the dummy data
    df_enso = load_enso_data()

except FileNotFoundError as e:
    st.error(f"Error: No se encontró el archivo necesario. Asegúrese de que todos los archivos CSV y el archivo .zip están en la misma carpeta que el script. Error: {e}")
    st.stop()
except Exception as e:
    st.error(f"Error inesperado al cargar los archivos. Por favor, verifique los nombres de las columnas y los delimitadores. Error: {e}")
    st.stop()

if df_precip is not None and not df_precip.empty and gdf_estaciones is not None and not gdf_estaciones.empty:
    # --- Unión de los datos de precipitación y estaciones ---
    df_completo = pd.merge(df_precip, df_estaciones_shp, left_on='Id_estacion', right_on='Id_estacion_shp', how='left')
    df_completo = df_completo.dropna(subset=['Latitud', 'Longitud'])
    
    # Preparación de datos para el análisis ENSO
    df_precip_mensual_promedio = df_completo.groupby('Id_Fecha')['Precipitacion_mm'].mean().reset_index()
    df_precip_mensual_promedio['Año_Mes'] = df_precip_mensual_promedio['Id_Fecha'].dt.to_period('M')
    
    df_enso['Id_Fecha'] = pd.to_datetime(df_enso['Id_Fecha'])
    df_enso['Año_Mes'] = df_enso['Id_Fecha'].dt.to_period('M')
    
    df_analisis = pd.merge(df_precip_mensual_promedio, df_enso, on='Año_Mes', how='inner')
    df_analisis.rename(columns={'Precipitacion_mm': 'Precipitación', 'Anomalia_ONI': 'Anomalia_ONI'}, inplace=True)
    df_analisis['ENSO'] = np.where(df_analisis['Anomalia_ONI'] > 0.5, 'Niño',
                                 np.where(df_analisis['Anomalia_ONI'] < -0.5, 'Niña', 'Neutral'))
    
    # --- Panel de Control (Sidebar) ---
    with st.sidebar:
        st.title("Panel de Control")
        
        # Filtros de año y mes
        all_years = sorted(df_completo['Año'].unique())
        selected_years = st.multiselect("Seleccionar Años", all_years, default=all_years)
        
        all_months = sorted(df_completo['Mes'].unique())
        selected_months = st.multiselect("Seleccionar Meses", all_months, default=all_months)
        
        # Filtro por municipio
        municipios = sorted(df_completo['municipio'].dropna().unique())
        selected_municipios = st.multiselect("Seleccionar Municipios", municipios, default=municipios)
        
        # Filtro de estaciones
        all_stations = sorted(df_completo['Nom_Est_shp'].dropna().unique())
        selected_stations = st.multiselect("Seleccionar Estaciones", all_stations, default=[])
    
    # --- Lógica de filtrado de datos ---
    df_filtered = df_completo[
        (df_completo['Año'].isin(selected_years)) &
        (df_completo['Mes'].isin(selected_months)) &
        (df_completo['municipio'].isin(selected_municipios))
    ]
    
    if selected_stations:
        df_filtered = df_filtered[df_filtered['Nom_Est_shp'].isin(selected_stations)]
    
    if not df_filtered.empty:
        st.success(f"Datos cargados y filtrados. Mostrando {len(df_filtered['Id_estacion'].unique())} estaciones.")
        st.dataframe(df_filtered.head())
        
        # --- Visualizaciones de Datos ---
        st.title("Visualizaciones de Datos de Precipitación")
        
        # Gráfico de Serie de Tiempo Anual
        st.header("1. Serie de Tiempo Anual de Precipitación")
        # Corrección: Agrupar por 'Id_estacion' para mantener la clave de unión
        df_anual = df_filtered.groupby(['Año', 'Id_estacion', 'Nom_Est_shp'])['Precipitacion_mm'].sum().reset_index()
        df_anual['Fecha_Anual'] = pd.to_datetime(df_anual['Año'], format='%Y')
        
        chart_anual = alt.Chart(df_anual).mark_line(point=True).encode(
            x=alt.X('Fecha_Anual:T', axis=alt.Axis(title='Año')),
            y=alt.Y('Precipitacion_mm', title='Precipitación Anual (mm)'),
            color='Nom_Est_shp',
            tooltip=['Fecha_Anual:T', 'Nom_Est_shp', 'Precipitacion_mm']
        ).interactive()
        st.altair_chart(chart_anual, use_container_width=True)
        
        # Gráfico de Serie de Tiempo Mensual
        st.header("2. Serie de Tiempo Mensual de Precipitación")
        df_mensual = df_filtered.groupby(['Id_Fecha', 'Nom_Est_shp'])['Precipitacion_mm'].sum().reset_index()
        
        chart_mensual = alt.Chart(df_mensual).mark_line(point=True).encode(
            x=alt.X('Id_Fecha:T', axis=alt.Axis(title='Fecha')),
            y=alt.Y('Precipitacion_mm', title='Precipitación Mensual (mm)'),
            color='Nom_Est_shp',
            tooltip=['Id_Fecha:T', 'Nom_Est_shp', 'Precipitacion_mm']
        ).interactive()
        st.altair_chart(chart_mensual, use_container_width=True)
        
        # Mapa Interactivo (Folium)
        st.header("3. Mapa Interactivo de Estaciones")
        if not df_filtered.empty:
            map_data = df_filtered.drop_duplicates(subset=['Id_estacion'])
            
            # Calcular el centro del mapa
            center_lat = map_data['Latitud'].mean()
            center_lon = map_data['Longitud'].mean()
            m = folium.Map(location=[center_lat, center_lon], zoom_start=6)
            
            for _, row in map_data.iterrows():
                folium.Marker(
                    location=[row['Latitud'], row['Longitud']],
                    popup=f"Estación: {row['Nom_Est_shp']}<br>Municipio: {row['municipio']}<br>Precipitación: {row['Precipitacion_mm']:.2f} mm"
                ).add_to(m)
            
            folium_static(m)
        else:
            st.warning("No hay estaciones para mostrar con los filtros seleccionados.")
            
        # Mapa Animado (Plotly)
        st.header("4. Mapa Animado de Precipitación Anual")
        # El DataFrame df_anual ya tiene 'Id_estacion'
        df_anual_plot = pd.merge(df_anual, df_estaciones_shp[['Id_estacion_shp', 'Longitud', 'Latitud']], left_on='Id_estacion', right_on='Id_estacion_shp', how='left')
        
        fig_mapa_anual = px.scatter_mapbox(
            df_anual_plot,
            lat='Latitud',
            lon='Longitud',
            color='Precipitacion_mm',
            size='Precipitacion_mm',
            animation_frame='Año',
            hover_name='Nom_Est_shp',
            hover_data={'Precipitacion_mm': ':.2f'},
            color_continuous_scale=px.colors.sequential.Viridis,
            mapbox_style="carto-positron",
            zoom=5,
            title="Precipitación Anual por Estación a lo Largo de los Años"
        )
        st.plotly_chart(fig_mapa_anual, use_container_width=True)
        
        # --- Análisis ENSO ---
        st.header("5. Análisis ENSO")
        st.info("Esta sección presenta la correlación de la precipitación con los datos del fenómeno ENSO.")
        
        if not df_analisis.empty:
            df_enso_group = df_analisis.groupby('ENSO')['Precipitación'].mean().reset_index()
            
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
            df_corr = df_analisis[['Anomalia_ONI', 'Precipitación']].dropna()
            if not df_corr.empty:
                correlation = df_corr['Anomalia_ONI'].corr(df_corr['Precipitación'])
                st.write(f"### Coeficiente de Correlación entre Anomalía ONI y Precipitación: **{correlation:.2f}**")
                st.info("""
                **Interpretación:**
                - Un valor cercano a 1 indica una correlación positiva fuerte (a mayor ONI, mayor precipitación).
                - Un valor cercano a -1 indica una correlación negativa fuerte (a mayor ONI, menor precipitación).
                - Un valor cercano a 0 indica una correlación débil o nula.
                """)
            else:
                st.warning("No hay suficientes datos para calcular la correlación.")
            
        else:
            st.error("No se pudo generar el tablero. Por favor, asegúrese de que todos los archivos necesarios se hayan cargado correctamente y revise los filtros.")
    else:
        st.warning("No hay datos que coincidan con los filtros seleccionados. Por favor, ajuste sus selecciones en el panel lateral.")
