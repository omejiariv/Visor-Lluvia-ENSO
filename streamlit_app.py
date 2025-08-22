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
from shapely.geometry import Point
import base64

# --- Configuración de la página ---
st.set_page_config(layout="wide", page_title="Visor de Precipitación y ENSO", page_icon="☔")

# Aplicar CSS personalizado para reducir el tamaño del texto y optimizar el espacio
st.markdown("""
<style>
    .sidebar .sidebar-content {
        font-size: 13px; /* Reducir el tamaño de la fuente en el sidebar */
    }
    .stSelectbox label, .stMultiSelect label, .stSlider label {
        font-size: 13px !important; /* Asegurar que los labels también sean más pequeños */
    }
    .stMultiSelect div[data-baseweb="select"] {
        font-size: 13px !important; /* Reducir el tamaño del texto dentro de la selección múltiple */
    }
    .stSlider label {
        font-size: 13px !important; /* Reducir el tamaño de la fuente del label del slider */
    }
    .css-1d391kg {
        font-size: 13px; /* Afecta a los títulos de los widgets */
    }
    .css-1cpx93x {
        font-size: 13px;
    }
    h1 {
        margin-top: 0px; /* Elimina el espacio superior del título principal */
        padding-top: 0px;
    }
</style>
""", unsafe_allow_html=True)

# --- Funciones de carga de datos ---
def load_data(file_path, sep=';'):
    """
    Carga datos desde un archivo local, asumiendo un formato de archivo CSV.
    Intenta decodificar con varias codificaciones comunes y maneja errores de archivos vacíos.
    """
    if file_path is None:
        return None
        
    try:
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
            df = pd.read_csv(io.BytesIO(content), sep=sep, encoding=encoding)
            df.columns = df.columns.str.strip()
            return df
        except pd.errors.EmptyDataError:
            st.error("Ocurrió un error al cargar los datos: No columns to parse from file. El archivo podría estar vacío o dañado.")
            return None
        except UnicodeDecodeError:
            continue
        except Exception as e:
            st.error(f"Ocurrió un error al cargar los datos: {e}")
            return None
    
    st.error("No se pudo decodificar el archivo con ninguna de las codificaciones probadas. Por favor, verifique la codificación.")
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
            gdf.columns = gdf.columns.str.strip()
            
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

with st.sidebar.expander("📂 **Cargar Archivos**"):
    uploaded_file_mapa = st.file_uploader("1. Cargar archivo de estaciones (mapaCVENSO.csv)", type="csv")
    uploaded_file_enso = st.file_uploader("2. Cargar archivo de ENSO (ENSO_1950_2023.csv)", type="csv")
    uploaded_file_precip = st.file_uploader("3. Cargar archivo de precipitación mensual (DatosPptnmes_ENSO.csv)", type="csv")
    uploaded_zip_shapefile = st.file_uploader("4. Cargar shapefile (.zip)", type="zip")

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

if df_precip_anual is not None and df_enso is not None and df_precip_mensual is not None and gdf is not None:
    
    # --- Preprocesamiento de datos de ENSO ---
    try:
        for col in ['Anomalia_ONI', 'Temp_SST', 'Temp_media']:
            if col in df_enso.columns and pd.api.types.is_object_dtype(df_enso[col]):
                df_enso[col] = df_enso[col].str.replace(',', '.', regex=True).astype(float)
        meses_es_en = {'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr', 'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Aug', 'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'}
        df_enso['Year'] = df_enso['Year'].astype(int)
        df_enso['mes_en'] = df_enso['mes'].str.lower().map(meses_es_en)
        df_enso['fecha_merge'] = pd.to_datetime(df_enso['Year'].astype(str) + '-' + df_enso['mes_en'], format='%Y-%b').dt.strftime('%Y-%m')
    except Exception as e:
        st.error(f"Error en el preprocesamiento del archivo ENSO: {e}")
        st.stop()
    
    # --- Preprocesamiento de datos de precipitación anual (mapa) ---
    try:
        df_precip_anual.columns = df_precip_anual.columns.str.strip()
        for col in ['Longitud', 'Latitud']:
            if col in df_precip_anual.columns and pd.api.types.is_object_dtype(df_precip_anual[col]):
                df_precip_anual[col] = df_precip_anual[col].str.replace(',', '.', regex=True).astype(float)
        gdf_stations = gpd.GeoDataFrame(
            df_precip_anual,
            geometry=gpd.points_from_xy(df_precip_anual['Longitud'], df_precip_anual['Latitud']),
            crs="EPSG:9377"
        )
        gdf_stations = gdf_stations.to_crs("EPSG:4326")
        gdf_stations['Longitud_geo'] = gdf_stations.geometry.x
        gdf_stations['Latitud_geo'] = gdf_stations.geometry.y
    except Exception as e:
        st.error(f"Error en el preprocesamiento del archivo de estaciones (mapaCVENSO.csv): {e}")
        st.stop()
        
    # --- Preprocesamiento de datos de precipitación mensual ---
    try:
        df_precip_mensual.columns = df_precip_mensual.columns.str.strip().str.lower().str.replace('á', 'a').str.replace('é', 'e').str.replace('í', 'i').str.replace('ó', 'o').str.replace('ú', 'u').str.replace('ñ', 'n')
        df_precip_mensual.rename(columns={'ano': 'Year', 'mes': 'Mes'}, inplace=True)
        station_cols = [col for col in df_precip_mensual.columns if col.isdigit() and len(col) == 8]
        if not station_cols:
            st.error("No se encontraron columnas de estación válidas en el archivo de precipitación mensual.")
            st.stop()
        df_long = df_precip_mensual.melt(
            id_vars=['id_fecha', 'Year', 'Mes'], 
            value_vars=station_cols,
            var_name='Id_estacion', 
            value_name='Precipitation'
        )
        df_long['Precipitation'] = df_long['Precipitation'].replace('n.d', np.nan).astype(float)
        df_long = df_long.dropna(subset=['Precipitation'])
        df_long['Fecha'] = pd.to_datetime(df_long['Year'].astype(str) + '-' + df_long['Mes'].astype(str), format='%Y-%m')
    except Exception as e:
        st.error(f"Error en el preprocesamiento del archivo de precipitación mensual: {e}")
        st.stop()

    # --- Mapeo y Fusión de Estaciones ---
    gdf_stations['Nom_Est_clean'] = gdf_stations['Nom_Est'].astype(str).str.upper().str.strip()
    gdf_stations['Nom_Est_clean'] = gdf_stations['Nom_Est_clean'].apply(lambda x: re.sub(r'[^A-Z0-9]', '', x))
    gdf['Nom_Est_clean'] = gdf['Nom_Est'].astype(str).str.upper().str.strip()
    gdf['Nom_Est_clean'] = gdf['Nom_Est_clean'].apply(lambda x: re.sub(r'[^A-Z0-9]', '', x))
    gdf_stations['Id_estacio'] = gdf_stations['Id_estacio'].astype(str).str.strip()
    df_long['Id_estacion'] = df_long['Id_estacion'].astype(str).str.strip()
    station_mapping = gdf_stations.set_index('Id_estacio')[['Nom_Est_clean', 'Nom_Est']].to_dict('index')
    df_long['Nom_Est_clean'] = df_long['Id_estacion'].map(lambda x: station_mapping.get(x, {}).get('Nom_Est_clean'))
    df_long['Nom_Est'] = df_long['Id_estacion'].map(lambda x: station_mapping.get(x, {}).get('Nom_Est'))
    df_long = df_long.dropna(subset=['Nom_Est_clean'])
    if df_long.empty:
        st.warning("La fusión de datos mensuales y de estaciones fracasó. Los IDs de las estaciones no coinciden.")
        st.stop()

    # --- Controles en la barra lateral ---
    staciones_list = sorted(gdf_stations['Nom_Est'].unique())
    selected_stations = st.sidebar.multiselect(
        'Seleccione una o varias estaciones', 
        options=staciones_list,
        default=staciones_list[:5]
    )
    selected_stations_clean = [gdf_stations[gdf_stations['Nom_Est'] == s]['Nom_Est_clean'].iloc[0] for s in selected_stations if s in gdf_stations['Nom_Est'].values]
    años_disponibles = sorted([int(col) for col in gdf_stations.columns if str(col).isdigit() and len(str(col)) == 4])
    year_range = st.sidebar.slider(
        "Seleccione el rango de años",
        min_value=min(años_disponibles),
        max_value=max(años_disponibles),
        value=(min(años_disponibles), max(años_disponibles))
    )
    municipios_list = sorted(gdf_stations['municipio'].unique())
    selected_municipios = st.sidebar.multiselect(
        'Filtrar por municipio',
        options=municipios_list,
        default=[]
    )
    if selected_municipios:
        filtered_stations_by_municipio = gdf_stations[gdf_stations['municipio'].isin(selected_municipios)]['Nom_Est'].tolist()
        filtered_stations = [s for s in selected_stations if s in filtered_stations_by_municipio]
    else:
        filtered_stations = selected_stations
    filtered_stations_clean = [gdf_stations[gdf_stations['Nom_Est'] == s]['Nom_Est_clean'].iloc[0] for s in filtered_stations if s in gdf_stations['Nom_Est'].values]

    # --- Sección de Visualizaciones ---
    st.header("Visualizaciones de Precipitación 💧")
    
    # Gráfico de Serie de Tiempo Anual
    st.subheader("Precipitación Anual Total (mm)")
    df_precip_anual_filtered = gdf_stations[gdf_stations['Nom_Est'].isin(filtered_stations)].copy()
    year_cols = [col for col in df_precip_anual_filtered.columns if str(col).isdigit() and len(str(col)) == 4]
    df_precip_anual_filtered_melted = df_precip_anual_filtered.melt(
        id_vars=['Nom_Est', 'Nom_Est_clean', 'Latitud_geo', 'Longitud_geo', 'municipio'], 
        value_vars=year_cols,
        var_name='Año', 
        value_name='Precipitación'
    )
    df_precip_anual_filtered_melted['Año'] = df_precip_anual_filtered_melted['Año'].astype(int)
    df_precip_anual_filtered_melted = df_precip_anual_filtered_melted[
        (df_precip_anual_filtered_melted['Año'] >= year_range[0]) &
        (df_precip_anual_filtered_melted['Año'] <= year_range[1])
    ].copy() # Usar .copy() para evitar SettingWithCopyWarning y problemas de renderizado en Altair

    if not df_precip_anual_filtered_melted.empty:
        # Habilitar selección interactiva de la leyenda con Altair
        selection_anual = alt.selection_point(fields=['Nom_Est'], bind='legend')
        chart_anual = alt.Chart(df_precip_anual_filtered_melted).mark_line().encode(
            x=alt.X('Año:O', title='Año'),
            y=alt.Y('Precipitación:Q', title='Precipitación Total (mm)'),
            color='Nom_Est:N',
            opacity=alt.condition(selection_anual, alt.value(1.0), alt.value(0.2)),
            tooltip=['Nom_Est', 'Año', 'Precipitación']
        ).properties(
            title='Precipitación Anual Total por Estación'
        ).add_params(selection_anual).interactive()
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
    ].copy() # Usar .copy() para evitar SettingWithCopyWarning y problemas de renderizado en Altair

    if not df_monthly_filtered.empty:
        # Habilitar selección interactiva de la leyenda con Altair
        selection_mensual = alt.selection_point(fields=['Nom_Est'], bind='legend')
        chart_mensual = alt.Chart(df_monthly_filtered).mark_line().encode(
            x=alt.X('Fecha:T', title='Fecha'),
            y=alt.Y('Precipitation:Q', title='Precipitación Total (mm)'),
            color='Nom_Est:N',
            opacity=alt.condition(selection_mensual, alt.value(1.0), alt.value(0.2)),
            tooltip=[alt.Tooltip('Fecha', format='%Y-%m'), 'Precipitation', 'Nom_Est']
        ).properties(
            title='Precipitación Mensual Total por Estación'
        ).add_params(selection_mensual).interactive()
        st.altair_chart(chart_mensual, use_container_width=True)
    else:
        st.warning("No hay datos mensuales para las estaciones y el rango de años seleccionados.")

    # Mapa Interactivo (Folium)
    st.subheader("Mapa de Estaciones de Lluvia en Colombia")
    st.markdown("Ubicación de las estaciones seleccionadas.")

    gdf_filtered = gdf_stations[gdf_stations['Nom_Est_clean'].isin(filtered_stations_clean)].copy()

    if not gdf_filtered.empty:
        m = folium.Map(location=[gdf_filtered['Latitud_geo'].mean(), gdf_filtered['Longitud_geo'].mean()], zoom_start=6)
        for _, row in gdf_filtered.iterrows():
            folium.Marker(
                location=[row['Latitud_geo'], row['Longitud_geo']],
                tooltip=f"Estación: {row['Nom_Est']}<br>Municipio: {row['municipio']}<br>Porc. Datos: {row['Porc_datos']}",
                icon=folium.Icon(color="blue", icon="cloud-rain", prefix='fa')
            ).add_to(m)
        folium_static(m, width=900, height=600)
        st.info("""
        **Nota sobre la interactividad:** Para los mapas de Folium, la selección por leyenda no es una funcionalidad nativa. Para filtrar las estaciones, por favor use las opciones de selección en el panel lateral.
        """)
    else:
        st.warning("No hay estaciones seleccionadas o datos de coordenadas para mostrar en el mapa.")

    # Mapa Animado (Plotly)
    st.subheader("Mapa Animado de Precipitación Anual")
    st.markdown("Visualice la precipitación anual a lo largo del tiempo.")
    if not df_precip_anual_filtered_melted.empty:
        fig_mapa_animado = px.scatter_geo(
            df_precip_anual_filtered_melted,
            lat='Latitud_geo',
            lon='Longitud_geo',
            color='Precipitación',
            size='Precipitación',
            hover_name='Nom_Est',
            animation_frame='Año',
            projection='natural earth',
            title='Precipitación Anual de las Estaciones',
            color_continuous_scale=px.colors.sequential.RdBu
        )
        fig_mapa_animado.update_geos(fitbounds="locations", showcountries=True, countrycolor="black")
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
        df_analisis = df_analisis.dropna(subset=['ENSO']).copy()

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
            - Un valor cercano a 1 indica una correlación positiva fuerte.
            - Un valor cercano a -1 indica una correlación negativa fuerte.
            - Un valor cercano a 0 indica una correlación débil o nula.
            """)
        else:
            st.warning("No hay suficientes datos para calcular la correlación.")
    except Exception as e:
        st.error(f"Error en el análisis ENSO: {e}")

    # --- Opciones de Descarga ---
    st.markdown("---")
    st.header("Opciones de Descarga 📥")
    st.markdown("""
    **Exportar a CSV:**
    Para obtener los datos filtrados en formato CSV, haga clic en los botones de descarga a continuación.
    """)
    
    st.markdown("**Datos de Precipitación Anual**")
    csv_anual = df_precip_anual_filtered_melted.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar datos anuales (CSV)",
        data=csv_anual,
        file_name='precipitacion_anual.csv',
        mime='text/csv',
    )
    
    st.markdown("**Datos de Precipitación Mensual**")
    csv_mensual = df_monthly_filtered.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar datos mensuales (CSV)",
        data=csv_mensual,
        file_name='precipitacion_mensual.csv',
        mime='text/csv',
    )
    
    st.markdown("---")
    st.markdown("""
    **Exportar a Imagen (PNG/SVG):**
    Para descargar los **gráficos de Plotly** como imagen, simplemente pase el cursor sobre el gráfico y haga clic en el ícono de la cámara 📷 que aparece en la parte superior derecha. Para los **mapas de Folium**, use una captura de pantalla.

    **Exportar a PDF:**
    Para guardar una copia de toda la página (incluyendo todos los gráficos y tablas visibles) como un archivo PDF, utilice la función de su navegador:
    1. Vaya al menú del navegador (usualmente en la esquina superior derecha).
    2. Seleccione **"Imprimir..."**.
    3. En el destino, elija **"Guardar como PDF"**.
    """)

---

### **Requisitos del Proyecto**

Por favor, reemplace su archivo `requirements.txt` actual con el siguiente para asegurarse de que solo se instalen las librerías necesarias y evitar futuros errores de instalación:
