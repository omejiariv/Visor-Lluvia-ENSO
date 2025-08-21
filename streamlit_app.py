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
st.set_page_config(layout="wide", page_title="Visor de Precipitación y ENSO", page_icon="☔")

# --- URLs de GitHub para carga automática de datos ---
GITHUB_BASE_URL = "https://raw.githubusercontent.com/TuUsuario/TuRepositorio/main/"
# Asegúrate de reemplazar 'TuUsuario' y 'TuRepositorio' con los datos de tu repositorio
# Por ejemplo:
# GITHUB_BASE_URL = "https://raw.githubusercontent.com/juancami94/Visor_Lluvia_ENSO/main/"
# SHAPEFILE_URL = "https://github.com/juancami94/Visor_Lluvia_ENSO/raw/main/mapaCV.zip"
SHAPEFILE_URL = "https://github.com/TuUsuario/TuRepositorio/raw/main/mapaCV.zip"

# --- Funciones de carga de datos ---

def load_data(file_type, file_path, sep=';'):
    """
    Carga datos desde un archivo local o una URL de GitHub.
    Soporta archivos CSV con diferentes delimitadores.
    """
    try:
        if file_type == 'local':
            if file_path.endswith('.csv'):
                return pd.read_csv(file_path, sep=sep)
            else:
                st.error(f"Tipo de archivo no soportado: {file_path}")
                return None
        elif file_type == 'github':
            response = requests.get(file_path)
            if response.status_code == 200:
                content = io.StringIO(response.text)
                return pd.read_csv(content, sep=sep)
            else:
                st.error(f"Error al descargar el archivo de GitHub: {response.status_code}")
                return None
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        return None

def load_geospatial_data(file_type, file_path, file_name, file_extension):
    """
    Carga un shapefile desde un archivo .zip.
    """
    try:
        if file_type == 'local':
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                with tempfile.TemporaryDirectory() as tempdir:
                    zip_ref.extractall(tempdir)
                    shp_path = os.path.join(tempdir, file_name)
                    return gpd.read_file(shp_path)
        elif file_type == 'github':
            response = requests.get(file_path)
            if response.status_code == 200:
                with tempfile.TemporaryDirectory() as tempdir:
                    zip_file_path = os.path.join(tempdir, "mapa.zip")
                    with open(zip_file_path, 'wb') as f:
                        f.write(response.content)
                    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                        zip_ref.extractall(tempdir)
                        shp_name = file_path.split('/')[-1].replace('.zip', '')
                        shp_path = os.path.join(tempdir, f"{shp_name}.shp")
                        return gpd.read_file(shp_path)
            else:
                st.error(f"Error al descargar el shapefile de GitHub: {response.status_code}")
                return None
    except Exception as e:
        st.error(f"Error al cargar el archivo geoespacial: {e}")
        return None

def find_delimiter(file):
    """Intenta detectar el delimitador de un archivo CSV."""
    sample = file.getvalue().decode('utf-8').splitlines()[0]
    if ',' in sample and ';' not in sample:
        return ','
    return ';'

# --- Título y descripción de la aplicación ---
st.title('☔ Visor de Información Geoespacial de Precipitación 🌧️')
st.markdown("---")

# --- Sección para la carga de datos ---
with st.expander("📂 Cargar Datos"):
    st.write("""
    Carga tus archivos o usa los datos de ejemplo desde GitHub.
    Se requieren tres archivos CSV (estaciones, precipitación y ENSO) y un archivo .zip con el shapefile.
    """)
    
    source = st.radio("Seleccione la fuente de datos:", ('Carga Manual', 'Usar Datos de GitHub'))

    df_estaciones = None
    df_pptn = None
    df_enso = None
    gdf_estaciones = None
    
    if source == 'Carga Manual':
        uploaded_file_estaciones = st.file_uploader("Cargar archivo de estaciones (.csv)", type="csv")
        uploaded_file_pptn = st.file_uploader("Cargar archivo de precipitación (.csv)", type="csv")
        uploaded_file_enso = st.file_uploader("Cargar archivo ENSO (.csv)", type="csv")
        uploaded_zip = st.file_uploader("Cargar shapefile (.zip)", type="zip")

        if uploaded_file_estaciones:
            delimiter = find_delimiter(uploaded_file_estaciones)
            df_estaciones = load_data('local', uploaded_file_estaciones, sep=delimiter)
        if uploaded_file_pptn:
            delimiter = find_delimiter(uploaded_file_pptn)
            df_pptn = load_data('local', uploaded_file_pptn, sep=delimiter)
        if uploaded_file_enso:
            delimiter = find_delimiter(uploaded_file_enso)
            df_enso = load_data('local', uploaded_file_enso, sep=delimiter)
        if uploaded_zip:
            gdf_estaciones = load_geospatial_data('local', uploaded_zip, uploaded_zip.name.replace('.zip', '.shp'), '.zip')
    
    else:  # Usar Datos de GitHub
        st.info("Cargando archivos de ejemplo de GitHub...")
        try:
            df_estaciones = load_data('github', GITHUB_BASE_URL + 'mapaCV.csv', sep=';')
            df_pptn = load_data('github', GITHUB_BASE_URL + 'DatosPptn_Om.csv', sep=';')
            df_enso = load_data('github', GITHUB_BASE_URL + 'ENSO_1950_2023.csv', sep=';')
            gdf_estaciones = load_geospatial_data('github', SHAPEFILE_URL, 'mapaCV.shp', '.zip')
            if all([df_estaciones is not None, df_pptn is not None, df_enso is not None, gdf_estaciones is not None]):
                st.success("Archivos cargados exitosamente desde GitHub.")
            else:
                st.error("Uno o más archivos no pudieron ser cargados desde GitHub. Por favor, revise las URLs.")
        except Exception as e:
            st.error(f"Error al cargar los datos de GitHub: {e}")

# --- Mapeo de columnas y pre-procesamiento ---

if all([df_estaciones is not None, df_pptn is not None, df_enso is not None]):
    # Mapeo y limpieza del DataFrame de estaciones
    df_estaciones.rename(columns={
        'Nom_Est': 'Nom_Est', 'departamento': 'departamento', 'municipio': 'municipio',
        'vereda': 'vereda', 'Longitud': 'Longitud', 'Latitud': 'Latitud',
        'Celda_XY': 'Celda_XY', 'Id_estacion': 'Id_estacion'
    }, inplace=True)
    
    # Mapeo y limpieza del DataFrame de precipitación
    df_pptn.rename(columns={
        'Id_Fecha': 'Id_Fecha'
    }, inplace=True)

    # Mapeo y limpieza del DataFrame ENSO
    df_enso.rename(columns={
        'Year': 'Year', 'mes': 'mes', 'Anomalia_ONI': 'Anomalia_ONI',
        'ENSO': 'ENSO'
    }, inplace=True)

    df_pptn = df_pptn.melt(id_vars=['Id_Fecha'], var_name='Id_estacion', value_name='Precipitación')
    df_pptn['Id_estacion'] = df_pptn['Id_estacion'].astype(str)
    
    # Manejar los valores "Sin dato" o "0"
    df_pptn['Precipitación'] = pd.to_numeric(df_pptn['Precipitación'], errors='coerce').fillna(0)
    
    # Combinar datos de estaciones y precipitación
    df_merged = pd.merge(df_pptn, df_estaciones, on='Id_estacion', how='left')
    df_merged.dropna(subset=['Latitud', 'Longitud'], inplace=True)
    df_merged['Id_Fecha'] = pd.to_datetime(df_merged['Id_Fecha'], format='%d/%m/%Y', errors='coerce')
    df_merged.dropna(subset=['Id_Fecha'], inplace=True)
    df_merged['Year'] = df_merged['Id_Fecha'].dt.year
    df_merged['Month'] = df_merged['Id_Fecha'].dt.month

    st.sidebar.title("Controles de Filtro")
    
    # Selección de municipios y celdas
    municipios_unicos = df_merged['municipio'].unique().tolist()
    celdas_unicas = df_merged['Celda_XY'].unique().tolist()
    
    selected_municipios = st.sidebar.multiselect("Seleccione Municipios", municipios_unicos, default=municipios_unicos)
    selected_celdas = st.sidebar.multiselect("Seleccione Celdas", celdas_unicas, default=celdas_unicas)

    # Filtrar estaciones por municipio y celda
    df_filtered_stations = df_merged[df_merged['municipio'].isin(selected_municipios) & df_merged['Celda_XY'].isin(selected_celdas)]
    
    estaciones_unicas = df_filtered_stations['Nom_Est'].unique().tolist()
    selected_stations = st.sidebar.multiselect("Seleccione Estaciones", estaciones_unicas, default=estaciones_unicas)
    
    # Filtrar los datos por las estaciones seleccionadas
    df_filtered_data = df_filtered_stations[df_filtered_stations['Nom_Est'].isin(selected_stations)]
    
    # Rango de años y meses
    if not df_filtered_data.empty:
        min_year = int(df_filtered_data['Year'].min())
        max_year = int(df_filtered_data['Year'].max())
        start_year, end_year = st.sidebar.slider("Seleccione Rango de Años", min_year, max_year, (min_year, max_year))
        
        min_month = int(df_filtered_data['Month'].min())
        max_month = int(df_filtered_data['Month'].max())
        start_month, end_month = st.sidebar.slider("Seleccione Rango de Meses", min_month, max_month, (min_month, max_month))
        
        df_final = df_filtered_data[(df_filtered_data['Year'] >= start_year) & (df_filtered_data['Year'] <= end_year) &
                                    (df_filtered_data['Month'] >= start_month) & (df_filtered_data['Month'] <= end_month)]
    
    else:
        st.warning("No hay datos disponibles para la combinación de filtros seleccionada.")
        df_final = pd.DataFrame()

    # --- Sección de Visualizaciones ---
    if not df_final.empty:
        st.markdown("## 📊 Visualizaciones y Análisis")
        st.markdown("---")

        # --- 1. Gráfico de Serie de Tiempo de Precipitación Anual ---
        st.subheader("Gráfico de Serie de Tiempo de Precipitación Anual por Estación")
        df_anual = df_final.groupby(['Year', 'Nom_Est'])['Precipitación'].sum().reset_index()
        
        chart = alt.Chart(df_anual).mark_line().encode(
            x=alt.X('Year:O', axis=alt.Axis(title='Año')),
            y=alt.Y('Precipitación:Q', title='Precipitación Anual Total (mm)'),
            color=alt.Color('Nom_Est', title='Estación')
        ).properties(
            title='Precipitación Anual Total por Estación'
        ).interactive()
        st.altair_chart(chart, use_container_width=True)
        st.markdown("---")
        
        # --- 2. Mapa Interactivo de Estaciones (Folium) ---
        st.subheader("🗺️ Mapa de Estaciones de Lluvia")
        
        if not df_estaciones.empty:
            mapa_estaciones = folium.Map(location=[df_estaciones['Latitud'].mean(), df_estaciones['Longitud'].mean()], zoom_start=6)
            
            for index, row in df_final[['Nom_Est', 'Latitud', 'Longitud']].drop_duplicates().iterrows():
                folium.Marker(
                    location=[row['Latitud'], row['Longitud']],
                    popup=row['Nom_Est'],
                    tooltip=row['Nom_Est']
                ).add_to(mapa_estaciones)
                
            folium_static(mapa_estaciones)
        else:
            st.warning("No se pudieron cargar los datos de las estaciones para el mapa.")
        st.markdown("---")
        
        # --- 3. Mapa Animado de Precipitación Anual (Plotly) ---
        st.subheader("🗺️ Mapa Animado de Precipitación Anual")
        
        df_animado = df_final.groupby(['Year', 'Nom_Est', 'Latitud', 'Longitud'])['Precipitación'].sum().reset_index()
        
        fig = px.scatter_mapbox(
            df_animado,
            lat="Latitud",
            lon="Longitud",
            hover_name="Nom_Est",
            hover_data={"Precipitación": True, "Year": True, "Latitud": False, "Longitud": False},
            color="Precipitación",
            size="Precipitación",
            color_continuous_scale=px.colors.sequential.Bluyl,
            animation_frame="Year",
            mapbox_style="open-street-map",
            zoom=5,
            title="Precipitación Anual Animada en el Mapa"
        )
        
        fig.update_layout(mapbox_style="open-street-map", mapbox_zoom=5, mapbox_center={"lat": df_animado['Latitud'].mean(), "lon": df_animado['Longitud'].mean()})
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
        
        # --- 4. Análisis ENSO ---
        st.subheader("🌊 Análisis de Correlación con Eventos ENSO")

        # Unir datos de precipitación y ENSO
        df_enso['Id_año_mes'] = df_enso['Year'].astype(str) + '-' + df_enso['mes']
        df_enso['Year'] = pd.to_numeric(df_enso['Year'])
        
        df_enso_filtrado = df_enso[(df_enso['Year'] >= start_year) & (df_enso['Year'] <= end_year)]
        
        # Agrupar por mes y año para la precipitación
        df_pptn_mensual = df_final.groupby(['Year', 'Month'])['Precipitación'].mean().reset_index()
        df_pptn_mensual['mes_str'] = df_pptn_mensual['Month'].apply(lambda x: pd.Timestamp(year=2000, month=x, day=1).strftime('%b'))
        
        df_analisis = pd.merge(df_pptn_mensual, df_enso_filtrado, on=['Year'])
        
        # Calcular precipitación media por evento ENSO
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
    st.warning("Por favor, cargue todos los archivos de datos para iniciar la aplicación.")
