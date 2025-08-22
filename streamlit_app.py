# Visor de Información Geoespacial de Precipitación y el Fenómeno ENSO
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
import numpy as np
from datetime import datetime

# --- Configuración de la página ---
st.set_page_config(layout="wide", page_title="Visor de Precipitación y ENSO", page_icon="☔")

# --- Funciones de carga de datos ---
def load_data(file_path, sep=';'):
    """
    Carga datos desde un archivo local, asumiendo un formato de archivo CSV.
    """
    try:
        df = pd.read_csv(io.StringIO(file_path.getvalue().decode('utf-8')), sep=sep)
        df.columns = df.columns.str.strip()  # Elimina espacios en blanco en los nombres de las columnas
        return df
    except Exception as e:
        st.error(f"Ocurrió un error al cargar los datos: {e}")
        return None

def load_shapefile(file_path):
    """
    Carga un shapefile desde un archivo .zip local,
    asigna el CRS correcto y lo convierte a WGS84.
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            shp_path = [f for f in os.listdir(temp_dir) if f.endswith('.shp')][0]
            
            gdf = gpd.read_file(os.path.join(temp_dir, shp_path))
            
            gdf.set_crs("EPSG:9377", inplace=True)
            gdf = gdf.to_crs("EPSG:4326")
            return gdf
    except Exception as e:
        st.error(f"Error al procesar el shapefile: {e}")
        return None

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
df_precip_anual, df_enso, df_precip_mensual, gdf = None, None, None, None

if uploaded_file_mapa and uploaded_file_enso and uploaded_file_precip and uploaded_zip_shapefile:
    df_precip_anual = load_data(uploaded_file_mapa)
    df_enso = load_data(uploaded_file_enso)
    df_precip_mensual = load_data(uploaded_file_precip)
    gdf = load_shapefile(uploaded_zip_shapefile)
else:
    st.info("Por favor, suba los 4 archivos para habilitar la aplicación.")
    st.stop()

# Si todos los DataFrames se cargaron correctamente, se procede con el resto de la aplicación
if df_precip_anual is not None and df_enso is not None and df_precip_mensual is not None and gdf is not None:
    
    # --- Preprocesamiento de datos de precipitación mensual ---
    try:
        df_precip_mensual.columns = df_precip_mensual.columns.str.strip()
        # Se renombra la columna para consistencia, usando el nombre correcto del archivo
        df_precip_mensual = df_precip_mensual.rename(columns={'Id_Fecha': 'Fecha'})
        df_precip_mensual['Fecha'] = pd.to_datetime(df_precip_mensual['Fecha'], format='%d/%m/%Y')
        df_precip_mensual['Year'] = df_precip_mensual['Fecha'].dt.year
        df_precip_mensual['Mes'] = df_precip_mensual['Fecha'].dt.month
        
        df_long = df_precip_mensual.melt(id_vars=['Fecha', 'Year', 'Mes'], var_name='Id_estacion', value_name='Precipitation')
        df_long['Precipitation'] = df_long['Precipitation'].replace('n.d', np.nan).astype(float)
        df_long = df_long.dropna(subset=['Precipitation'])

    except Exception as e:
        st.error(f"Error en el preprocesamiento del archivo de precipitación mensual: {e}")
        st.stop()

    # --- Preprocesamiento de datos ENSO ---
    try:
        df_enso['Year'] = df_enso['Year'].astype(int)
        df_enso['fecha_merge'] = pd.to_datetime(df_enso['Year'].astype(str) + '-' + df_enso['mes'], format='%Y-%b').dt.strftime('%Y-%m')

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
    year_range = st.sidebar.slider(
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
        var_name='Año', 
        value_name='Precipitación'
    )
    df_precip_anual_filtered_melted['Año'] = df_precip_anual_filtered_melted['Año'].astype(int)

    df_precip_anual_filtered_melted = df_precip_anual_filtered_melted[
        (df_precip_anual_filtered_melted['Año'] >= year_range[0]) &
        (df_precip_anual_filtered_melted['Año'] <= year_range[1])
    ]

    if not df_precip_anual_filtered_melted.empty:
        chart_anual = alt.Chart(df_precip_anual_filtered_melted).mark_line().encode(
            x=alt.X('Año:O', title='Año'),
            y=alt.Y('Precipitación:Q', title='Precipitación Total (mm)'),
            color='Nom_Est:N',
            tooltip=['Nom_Est', 'Año', 'Precipitación']
        ).properties(
            title='Precipitación Anual Total por Estación'
        ).interactive()
        st.altair_chart(chart_anual, use_container_width=True)
    else:
        st.warning("No hay datos para las estaciones y el rango de años seleccionados.")

    # Gráfico de Serie de Tiempo Mensual
    st.subheader("Precipitación Mensual Total (mm)")
    df_monthly_total = df_long.groupby(['Nom_Est', 'Year', 'Mes'])['Precipitation'].sum().reset_index()
    df_monthly_total['Fecha'] = pd.to_datetime(df_monthly_total['Year'].astype(str) + '-' + df_monthly_total['Mes'].astype(str), format='%Y-%m')

    df_monthly_filtered = df_monthly_total[
        (df_monthly_total['Nom_Est'].isin(filtered_stations)) &
        (df_monthly_total['Year'] >= year_range[0]) &
        (df_monthly_total['Year'] <= year_range[1])
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
            animation_frame='Año',
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

    df_analisis = df_long.copy()

    try:
        df_analisis['fecha_merge'] = df_analisis['Fecha'].dt.strftime('%Y-%m')
        df_analisis = pd.merge(df_analisis, df_enso[['fecha_merge', 'Anomalia_ONI', 'ENSO']], on='fecha_merge', how='left')
        df_analisis = df_analisis.dropna(subset=['ENSO'])

        df_enso_group = df_analisis.groupby('ENSO')['Precipitation'].mean().reset_index()
        df_enso_group = df_enso_group.rename(columns={'Precipitation': 'Precipitación'})

        fig_enso = px.bar(
            df_enso_group,
            x='ENSO',
            y='Precipitación',
            title='Precipitación Media por Evento ENSO',
            labels={'ENSO': 'Evento ENSO', 'Precipitación': 'Precipitación Media (mm)'},
            color='ENSO'
        )
        st.plotly_chart(fig_enso, use_container_width=True)

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
