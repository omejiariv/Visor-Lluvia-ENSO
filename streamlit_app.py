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
import re
from datetime import datetime

# --- Configuración de la página ---
st.set_page_config(layout="wide", page_title="Visor de Precipitación y ENSO", page_icon="☔")

# --- Funciones de carga de datos ---
def load_data(file_path, sep=';'):
    """
    Carga datos desde un archivo local, asumiendo un formato de archivo CSV.
    Intenta decodificar con varias codificaciones comunes y maneja errores de archivos vacíos.
    """
    if file_path is None:
        return None
        
    try:
        # Lee el contenido del archivo en memoria para verificar si está vacío
        content = file_path.getvalue()
        if not content.strip():
            st.error("Ocurrió un error al cargar los datos: El archivo parece estar vacío.")
            return None
    except Exception as e:
        st.error(f"Error al leer el contenido del archivo: {e}")
        return None

    encodings_to_try = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
    for encoding in encodings_to_try:
        try:
            # Intenta leer el archivo con la codificación actual
            df = pd.read_csv(io.BytesIO(content), sep=sep, encoding=encoding)
            df.columns = df.columns.str.strip()  # Elimina espacios en blanco en los nombres de las columnas
            return df
        except pd.errors.EmptyDataError:
            st.error("Ocurrió un error al cargar los datos: No columns to parse from file. El archivo podría estar vacío o dañado.")
            return None
        except UnicodeDecodeError:
            continue  # Si falla, intenta con la siguiente codificación
        except Exception as e:
        st.error(f"Ocurrió un error al cargar los datos: {e}")
            return None
    
    st.error("No se pudo decodificar el archivo con ninguna de las codificaciones probadas (utf-8, latin1, cp1252, iso-8859-1). Por favor, verifique la codificación del archivo.")
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
            
            # Limpiar nombres de columnas para evitar KeyError
            gdf.columns = gdf.columns.str.strip()
            
            # Se asume el CRS del archivo y se convierte a WGS84
            # Si el shapefile no tiene un CRS, se le asigna 9377 y se transforma
            if gdf.crs is None:
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
    
    # --- Preprocesamiento de datos de ENSO ---
    try:
        # Reemplazar comas por puntos para convertir a float
        for col in ['Anomalia_ONI', 'Temp_SST', 'Temp_media']:
            if col in df_enso.columns and pd.api.types.is_object_dtype(df_enso[col]):
                df_enso[col] = df_enso[col].str.replace(',', '.', regex=True).astype(float)

        # Mapeo manual de meses de español a inglés
        meses_es_en = {
            'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr',
            'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Aug',
            'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
        }
        
        df_enso['Year'] = df_enso['Year'].astype(int)
        df_enso['mes_en'] = df_enso['mes'].str.lower().map(meses_es_en)
        df_enso['fecha_merge'] = pd.to_datetime(df_enso['Year'].astype(str) + '-' + df_enso['mes_en'], format='%Y-%b').dt.strftime('%Y-%m')

    except Exception as e:
        st.error(f"Error en el preprocesamiento del archivo ENSO: {e}")
        st.stop()
    
    # --- Preprocesamiento de datos de precipitación anual (mapa) ---
    try:
        df_precip_anual.columns = df_precip_anual.columns.str.strip()

        # Convertir Longitud y Latitud a tipo numérico
        for col in ['Longitud', 'Latitud']:
            if col in df_precip_anual.columns and pd.api.types.is_object_dtype(df_precip_anual[col]):
                df_precip_anual[col] = df_precip_anual[col].str.replace(',', '.', regex=True).astype(float)
        
    except Exception as e:
        st.error(f"Error en el preprocesamiento del archivo de estaciones (mapaCVENSO.csv): {e}")
        st.stop()
        
    # --- Preprocesamiento de datos de precipitación mensual ---
    try:
        df_precip_mensual.columns = df_precip_mensual.columns.str.strip()
        
        # Identificar columnas de estaciones para melt
        station_cols = [col for col in df_precip_mensual.columns if col.isdigit() and len(col) == 8]
        
        if not station_cols:
            st.error("No se encontraron columnas de estación válidas en el archivo de precipitación mensual. Verifique el formato de los IDs.")
            st.stop()
            
        df_long = df_precip_mensual.melt(
            id_vars=['Id_Fecha', 'año', 'mes'], 
            value_vars=station_cols,
            var_name='Id_estacion', 
            value_name='Precipitation'
        )
        
        # Renombrar columnas para consistencia y convertir tipos
        df_long = df_long.rename(columns={'año': 'Year', 'mes': 'Mes'})
        df_long['Precipitation'] = df_long['Precipitation'].replace('n.d', np.nan).astype(float)
        df_long = df_long.dropna(subset=['Precipitation'])
        
        # Convertir a fecha y crear la columna de fecha para la fusión
        df_long['Fecha'] = pd.to_datetime(df_long['Year'].astype(str) + '-' + df_long['Mes'].astype(str), format='%Y-%m')
        
    except Exception as e:
        st.error(f"Error en el preprocesamiento del archivo de precipitación mensual: {e}")
        st.stop()

    # --- Mapeo y Fusión de Estaciones ---
    # Limpiar y estandarizar la columna de nombre de estación para la unión con el mapa
    # Uso de regex para eliminar el ID entre corchetes
    df_precip_anual['Nom_Est_clean'] = df_precip_anual['Nom_Est'].astype(str).str.strip()
    df_precip_anual['Nom_Est_clean'] = df_precip_anual['Nom_Est_clean'].apply(lambda x: re.sub(r'\[\d+\]', '', x)).str.strip().str.upper()

    gdf['Nom_Est_clean'] = gdf['Nom_Est'].astype(str).str.strip().str.upper()

    # Fusionar el GeoDataFrame con los datos de las estaciones del CSV
    gdf = gdf.merge(df_precip_anual[['Nom_Est_clean', 'Porc_datos', 'municipio', 'Latitud', 'Longitud']], on='Nom_Est_clean', how='inner')

    if gdf.empty:
        st.warning("La fusión de datos de estaciones y coordenadas fracasó. Los nombres de las estaciones en el archivo .csv y el .zip podrían no coincidir.")
        st.stop()
    
    # Unir la información de las estaciones a los datos mensuales usando los IDs correctos
    # Limpiar los IDs para asegurar la coincidencia
    df_precip_anual['Id_estacio'] = df_precip_anual['Id_estacio'].astype(str).str.strip()
    df_long['Id_estacion'] = df_long['Id_estacion'].astype(str).str.strip()
    
    station_mapping = df_precip_anual.set_index('Id_estacio')['Nom_Est_clean'].to_dict()
    df_long['Nom_Est_clean'] = df_long['Id_estacion'].map(station_mapping)
    df_long = df_long.dropna(subset=['Nom_Est_clean'])

    if df_long.empty:
        st.warning("La fusión de datos mensuales y de estaciones fracasó. Los IDs de las estaciones no coinciden entre los archivos.")
        st.stop()

    # --- Controles en la barra lateral ---
    staciones_list = sorted(df_precip_anual['Nom_Est_clean'].unique())
    selected_stations = st.sidebar.multiselect(
        'Seleccione una o varias estaciones', 
        options=staciones_list,
        default=staciones_list[:5]
    )

    # Filtro de años
    años_disponibles = sorted([int(col) for col in df_precip_anual.columns if str(col).isdigit() and len(str(col)) == 4])
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
        filtered_stations_by_municipio = df_precip_anual[df_precip_anual['municipio'].isin(selected_municipios)]['Nom_Est_clean'].tolist()
        filtered_stations = [s for s in selected_stations if s in filtered_stations_by_municipio]
    else:
        filtered_stations = selected_stations

    # --- Sección de Visualizaciones ---
    st.header("Visualizaciones de Precipitación 💧")
    
    # Gráfico de Serie de Tiempo Anual
    st.subheader("Precipitación Anual Total (mm)")
    df_precip_anual_filtered = df_precip_anual[df_precip_anual['Nom_Est_clean'].isin(filtered_stations)].copy()
    
    year_cols = [col for col in df_precip_anual_filtered.columns if str(col).isdigit() and len(str(col)) == 4]
    
    df_precip_anual_filtered_melted = df_precip_anual_filtered.melt(
        id_vars=['Nom_Est_clean'], 
        value_vars=year_cols,
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
            color='Nom_Est_clean:N',
            tooltip=['Nom_Est_clean', 'Año', 'Precipitación']
        ).properties(
            title='Precipitación Anual Total por Estación'
        ).interactive()
        st.altair_chart(chart_anual, use_container_width=True)
    else:
        st.warning("No hay datos para las estaciones y el rango de años seleccionados.")

    # Gráfico de Serie de Tiempo Mensual
    st.subheader("Precipitación Mensual Total (mm)")
    df_monthly_total = df_long.groupby(['Nom_Est_clean', 'Year', 'Mes'])['Precipitation'].sum().reset_index()
    df_monthly_total['Fecha'] = pd.to_datetime(df_monthly_total['Year'].astype(str) + '-' + df_monthly_total['Mes'].astype(str), format='%Y-%m')

    df_monthly_filtered = df_monthly_total[
        (df_monthly_total['Nom_Est_clean'].isin(filtered_stations)) &
        (df_monthly_total['Year'] >= year_range[0]) &
        (df_monthly_total['Year'] <= year_range[1])
    ]

    if not df_monthly_filtered.empty:
        chart_mensual = alt.Chart(df_monthly_filtered).mark_line().encode(
            x=alt.X('Fecha:T', title='Fecha'),
            y=alt.Y('Precipitation:Q', title='Precipitación Total (mm)'),
            color='Nom_Est_clean:N',
            tooltip=[alt.Tooltip('Fecha', format='%Y-%m'), 'Precipitation', 'Nom_Est_clean']
        ).properties(
            title='Precipitación Mensual Total por Estación'
        ).interactive()
        st.altair_chart(chart_mensual, use_container_width=True)
    else:
        st.warning("No hay datos mensuales para las estaciones y el rango de años seleccionados.")

    # Mapa Interactivo (Folium)
    st.subheader("Mapa de Estaciones de Lluvia en Colombia")
    st.markdown("Ubicación de las estaciones seleccionadas.")

    gdf_filtered = gdf[gdf['Nom_Est_clean'].isin(filtered_stations)].copy()

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
    if not df_precip_anual_filtered_melted.empty and not gdf_filtered.empty:
        # Usamos df_precip_anual_filtered para la unión ya que tiene las coordenadas
        df_plot = df_precip_anual_filtered_melted.merge(gdf_filtered[['Nom_Est_clean', 'Latitud', 'Longitud']], on='Nom_Est_clean', how='inner')
        fig_mapa_animado = px.scatter_geo(
            df_plot,
            lat='Latitud',
            lon='Longitud',
            color='Precipitación',
            size='Precipitación',
            hover_name='Nom_Est_clean',
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
