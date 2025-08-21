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
from scipy.stats import pearsonr

# --- Configuración de la página ---
st.set_page_config(layout="wide")
st.title('☔ Visor de Información Geoespacial de Precipitación 🌧️')
st.markdown("---")

# --- URLs de archivos de datos en GitHub para carga automática ---
GITHUB_BASE_URL = 'https://raw.githubusercontent.com/TuUsuario/TuRepositorio/main/'
SHAPEFILE_URL = 'https://github.com/TuUsuario/TuRepositorio/raw/main/mapaCV.zip'

# --- Sección para la carga de datos ---
def load_data_from_github():
    """Carga los archivos CSV desde GitHub."""
    try:
        @st.cache_data(show_spinner=False)
        def load_csv_from_url(url, sep=';'):
            response = requests.get(url)
            response.raise_for_status()
            return pd.read_csv(io.StringIO(response.text), sep=sep)

        st.info("Cargando datos automáticamente desde GitHub...")
        df_mapa = load_csv_from_url(GITHUB_BASE_URL + 'mapaCV.csv')
        df_pptn = load_csv_from_url(GITHUB_BASE_URL + 'DatosPptn_Om.csv')
        df_enso = load_csv_from_url(GITHUB_BASE_URL + 'ENSO_1950_2023.csv')

        # Carga del shapefile
        @st.cache_data(show_spinner=False)
        def load_shapefile_from_url(url):
            with tempfile.TemporaryDirectory() as tempdir:
                response = requests.get(url)
                response.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    z.extractall(tempdir)
                    shp_path = [os.path.join(tempdir, f) for f in z.namelist() if f.endswith('.shp')][0]
                    return gpd.read_file(shp_path)

        gdf = load_shapefile_from_url(SHAPEFILE_URL)
        st.success("Archivos cargados exitosamente desde GitHub.")
        return df_mapa, df_pptn, df_enso, gdf
    except Exception as e:
        st.error(f"Error al cargar archivos desde GitHub. Por favor, cárguelos manualmente. {e}")
        return None, None, None, None

def load_data_manually():
    """Permite al usuario cargar los archivos manualmente."""
    uploaded_file_csv = st.file_uploader("Cargar archivo de estaciones .csv (mapaCV.csv)", type="csv")
    uploaded_file_pptn = st.file_uploader("Cargar archivo de precipitación .csv (DatosPptn_Om.csv)", type="csv")
    uploaded_file_enso = st.file_uploader("Cargar archivo ENSO .csv (ENSO_1950_2023.csv)", type="csv")
    uploaded_file_shp = st.file_uploader("Cargar shapefile .zip (mapaCV.zip)", type="zip")

    df_mapa, df_pptn, df_enso, gdf = None, None, None, None
    try:
        if uploaded_file_csv and uploaded_file_pptn and uploaded_file_enso and uploaded_file_shp:
            df_mapa = pd.read_csv(uploaded_file_csv, sep=';', encoding='utf-8')
            df_pptn = pd.read_csv(uploaded_file_pptn, sep=';', encoding='utf-8')
            df_enso = pd.read_csv(uploaded_file_enso, sep=';', encoding='utf-8')
            
            with tempfile.TemporaryDirectory() as tempdir:
                with zipfile.ZipFile(uploaded_file_shp, 'r') as zip_ref:
                    zip_ref.extractall(tempdir)
                shp_path = [os.path.join(tempdir, f) for f in zip_ref.namelist() if f.endswith('.shp')][0]
                gdf = gpd.read_file(shp_path)

            st.success("Archivos cargados exitosamente de forma manual.")
    except Exception as e:
        st.error(f"Error al leer los archivos cargados: {e}")

    return df_mapa, df_pptn, df_enso, gdf

# --- Panel de control (Sidebar) ---
st.sidebar.header('⚙️ Panel de Control')

with st.sidebar.expander("📂 Cargar Datos"):
    st.write("Carga tus archivos `mapaCV.csv`, `DatosPptn_Om.csv`, `ENSO_1950_2023.csv` y los archivos del shapefile (`.shp`, `.shx`, `.dbf`, etc.) comprimidos en un único archivo `.zip`.")
    load_option = st.radio("Selecciona una opción de carga:", ("Carga Automática (GitHub)", "Carga Manual"))

    if load_option == "Carga Automática (GitHub)":
        df_mapa, df_pptn, df_enso, gdf = load_data_from_github()
    else:
        df_mapa, df_pptn, df_enso, gdf = load_data_manually()

if df_mapa is not None and df_pptn is not None and df_enso is not None and gdf is not None:
    # --- Pre-procesamiento de datos y mapeo de columnas ---
    
    # Mapeo de nombres de columnas comunes
    col_map_mapa = {
        'Id_estacion': 'Id_estacion',
        'Nom_Est': 'Nom_Est',
        'Longitud': 'Longitud',
        'Latitud': 'Latitud',
        'municipio': 'municipio',
        'departamento': 'departamento',
        'SUBREGION': 'SUBREGION',
        'Celda_XY': 'Celda_XY'
    }
    col_map_pptn = {'Id_Fecha': 'Id_Fecha'}
    col_map_enso = {'Anomalia_ONI': 'Anomalia_ONI', 'Year': 'Year', 'mes': 'mes'}

    # Renombrar columnas para estandarizar
    df_mapa = df_mapa.rename(columns={old: new for old, new in col_map_mapa.items() if old in df_mapa.columns})
    df_pptn = df_pptn.rename(columns={old: new for old, new in col_map_pptn.items() if old in df_pptn.columns})
    df_enso = df_enso.rename(columns={old: new for old, new in col_map_enso.items() if old in df_enso.columns})
    
    # Limpieza de datos
    df_mapa = df_mapa.dropna(subset=['Latitud', 'Longitud'])
    df_mapa['Latitud'] = pd.to_numeric(df_mapa['Latitud'], errors='coerce')
    df_mapa['Longitud'] = pd.to_numeric(df_mapa['Longitud'], errors='coerce')

    # Convertir las columnas de precipitación a numérico
    pptn_cols = [col for col in df_pptn.columns if col not in ['Id_Fecha']]
    for col in pptn_cols:
        df_pptn[col] = pd.to_numeric(df_pptn[col], errors='coerce').fillna(0)

    # Convertir Id_Fecha a formato de fecha
    try:
        df_pptn['Id_Fecha'] = pd.to_datetime(df_pptn['Id_Fecha'], format='%d/%m/%Y')
    except:
        df_pptn['Id_Fecha'] = pd.to_datetime(df_pptn['Id_Fecha'])

    # Extraer año y mes
    df_pptn['Year'] = df_pptn['Id_Fecha'].dt.year
    df_pptn['mes'] = df_pptn['Id_Fecha'].dt.month

    # Fusión de los datos para el análisis
    df_full = pd.merge(df_mapa, df_pptn.T, left_on='Id_estacion', right_index=True)
    df_full = df_full.T.reset_index().rename(columns={'index': 'Id_estacion'})
    df_full.columns = df_full.iloc[0]
    df_full = df_full[1:].rename(columns={'Id_estacion': 'Id_Fecha', 'Year': 'Year_Pptn', 'mes': 'mes_Pptn'})
    df_full['Id_Fecha'] = pd.to_datetime(df_full['Id_Fecha'])
    df_full['Year'] = df_full['Id_Fecha'].dt.year
    df_full['mes'] = df_full['Id_Fecha'].dt.month
    
    # Fusión con los datos ENSO
    df_analisis = pd.merge(df_full, df_enso, on=['Year', 'mes'], how='left')

    # --- Filtros en el panel lateral ---
    
    # Filtro por rango de años
    all_years = sorted(df_analisis['Year'].unique())
    year_range = st.sidebar.slider(
        "Selecciona el rango de años:",
        min_value=all_years[0],
        max_value=all_years[-1],
        value=(all_years[0], all_years[-1])
    )
    df_filtered_years = df_analisis[(df_analisis['Year'] >= year_range[0]) & (df_analisis['Year'] <= year_range[1])]

    # Filtro por estaciones
    available_stations = df_mapa['Nom_Est'].unique()
    selected_stations = st.sidebar.multiselect(
        "Selecciona las estaciones de lluvia:",
        options=available_stations,
        default=available_stations[:10]
    )
    
    # Filtro por celda XY y municipio
    celdas_unicas = sorted(df_mapa['Celda_XY'].dropna().unique())
    celda_seleccionada = st.sidebar.selectbox("Filtrar por Celda XY:", ["Todas"] + celdas_unicas)
    
    municipios_unicos = sorted(df_mapa['municipio'].dropna().unique())
    municipio_seleccionado = st.sidebar.selectbox("Filtrar por Municipio:", ["Todos"] + municipios_unicos)

    if celda_seleccionada != "Todas":
        df_mapa = df_mapa[df_mapa['Celda_XY'] == celda_seleccionada]
    if municipio_seleccionado != "Todos":
        df_mapa = df_mapa[df_mapa['municipio'] == municipio_seleccionado]
        
    df_mapa_filtered = df_mapa[df_mapa['Nom_Est'].isin(selected_stations)]

    # --- Visualizaciones y análisis ---
    
    st.markdown("## 📊 Visualizaciones de Datos de Precipitación")
    st.markdown("---")
    
    # --- Gráfico de Serie de Tiempo (Precipitación Anual) ---
    st.markdown("### Precipitación Anual por Estación")
    
    # Agrupar los datos por año y estación para el gráfico
    df_pptn_years = df_pptn.drop(columns=['Id_Fecha', 'mes']).groupby('Year').sum().reset_index()
    df_pptn_melted = df_pptn_years.melt('Year', var_name='Id_estacion', value_name='Precipitación')
    df_pptn_melted['Id_estacion'] = df_pptn_melted['Id_estacion'].astype(str)
    
    # Unir con los nombres de las estaciones
    df_pptn_melted = df_pptn_melted.merge(df_mapa_filtered[['Id_estacion', 'Nom_Est']], on='Id_estacion', how='left')
    df_pptn_melted = df_pptn_melted.dropna(subset=['Nom_Est'])
    
    if not df_pptn_melted.empty:
        chart_line = alt.Chart(df_pptn_melted).mark_line().encode(
            x=alt.X('Year:O', title='Año'),
            y=alt.Y('Precipitación:Q', title='Precipitación Anual (mm)'),
            color=alt.Color('Nom_Est:N', title='Estación'),
            tooltip=['Year', 'Nom_Est', 'Precipitación']
        ).properties(
            title='Precipitación Anual Total para Estaciones Seleccionadas'
        ).interactive()
        st.altair_chart(chart_line, use_container_width=True)
    else:
        st.info("Por favor, selecciona al menos una estación para visualizar la precipitación.")

    # --- Mapa Interactivo (Folium) ---
    st.markdown("---")
    st.markdown("### Mapa Interactivo de Estaciones")
    
    if not df_mapa_filtered.empty:
        # Calcular el centro del mapa
        center_lat = df_mapa_filtered['Latitud'].mean()
        center_lon = df_mapa_filtered['Longitud'].mean()
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="cartodbpositron")
        
        for index, row in df_mapa_filtered.iterrows():
            folium.Marker(
                location=[row['Latitud'], row['Longitud']],
                popup=f"**Estación:** {row['Nom_Est']}<br>**Municipio:** {row['municipio']}<br>**Departamento:** {row['departamento']}",
                icon=folium.Icon(color='blue', icon='cloud-rain', prefix='fa')
            ).add_to(m)
        
        folium_static(m, width=900, height=500)
    else:
        st.info("No hay estaciones seleccionadas o datos de coordenadas para mostrar en el mapa.")

    # --- Mapa Animado (Plotly) ---
    st.markdown("---")
    st.markdown("### Mapa Animado de Precipitación Anual")

    df_melted_map = df_pptn_melted.merge(df_mapa[['Id_estacion', 'Latitud', 'Longitud', 'Nom_Est']], on='Id_estacion', how='inner')
    df_melted_map = df_melted_map.dropna(subset=['Latitud', 'Longitud'])
    
    if not df_melted_map.empty:
        y_range = [df_melted_map['Precipitación'].min(), df_melted_map['Precipitación'].max()]
        fig = px.scatter_mapbox(
            df_melted_map,
            lat="Latitud",
            lon="Longitud",
            hover_name="Nom_Est",
            hover_data={"Precipitación": True, "Year": True, "Latitud": False, "Longitud": False},
            color="Precipitación",
            size="Precipitación",
            color_continuous_scale=px.colors.sequential.Bluyl,
            animation_frame="Year",
            mapbox_style="open-street-map",
            zoom=7,
            title="Precipitación Anual Animada en el Mapa",
            range_color=y_range
        )
        fig.update_layout(
            mapbox_style="open-street-map",
            mapbox_zoom=7,
            mapbox_center={"lat": df_melted_map['Latitud'].mean(), "lon": df_melted_map['Longitud'].mean()},
        )
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("El rango de años seleccionado no contiene datos de precipitación para las estaciones seleccionadas. Por favor, ajusta el rango de años.")

    # --- Análisis ENSO ---
    st.markdown("---")
    st.markdown("## ☀️ Análisis de la relación con el Fenómeno ENSO")
    
    # Calcular la precipitación promedio anual por año
    df_promedio_anual = df_analisis.groupby(['Year', 'Anomalia_ONI']).sum(numeric_only=True).reset_index()

    # Clasificar el ENSO
    def classify_enso(oni):
        if oni >= 0.5:
            return 'Niño'
        elif oni <= -0.5:
            return 'Niña'
        else:
            return 'Neutral'

    df_promedio_anual['ENSO'] = df_promedio_anual['Anomalia_ONI'].apply(classify_enso)
    
    # Renombrar columnas para el gráfico
    df_promedio_anual.rename(columns={'Anomalia_ONI': 'Anomalía ONI', 'ENSO': 'Evento ENSO'}, inplace=True)

    # Gráfico de barras de Precipitación vs Evento ENSO
    st.markdown("### Precipitación vs Evento ENSO")
    fig_enso_bar = px.bar(
        df_promedio_anual,
        x='Year',
        y=pptn_cols,
        color='Evento ENSO',
        title="Precipitación total anual por tipo de evento ENSO",
        labels={'value': 'Precipitación (mm)', 'variable': 'Estación', 'Year': 'Año'},
        color_discrete_map={'Niño': 'red', 'Niña': 'blue', 'Neutral': 'green'}
    )
    fig_enso_bar.update_layout(barmode='stack')
    st.plotly_chart(fig_enso_bar, use_container_width=True)
    
    # --- Cálculo y visualización de Correlación ---
    st.markdown("---")
    st.markdown("### Correlación entre la Precipitación y la Anomalía ONI")
    
    # Prepara los datos para la correlación
    df_corr = df_analisis[['Year', 'Anomalia_ONI'] + pptn_cols].dropna()

    if not df_corr.empty and len(df_corr) > 1:
        st.write("Calculando el coeficiente de correlación de Pearson para cada estación:")
        correlations = {}
        for col in pptn_cols:
            if df_corr[col].std() > 0 and df_corr['Anomalia_ONI'].std() > 0:
                corr, _ = pearsonr(df_corr[col], df_corr['Anomalia_ONI'])
                correlations[df_mapa.loc[df_mapa['Id_estacion'] == col, 'Nom_Est'].iloc[0]] = corr

        if correlations:
            df_correlations = pd.DataFrame(list(correlations.items()), columns=['Estación', 'Coeficiente de Correlación (r)'])
            st.dataframe(df_correlations, use_container_width=True)
            
            st.info(f"**Interpretación del Coeficiente de Correlación:**")
            st.write("""
- **r = 1**: Correlación positiva perfecta.
- **r > 0**: Correlación positiva. A medida que una variable aumenta, la otra también tiende a aumentar.
- **r = 0**: No hay correlación lineal.
- **r < 0**: Correlación negativa. A medida que una variable aumenta, la otra tiende a disminuir.
- **r = -1**: Correlación negativa perfecta.
""")
        else:
            st.warning("No se pudieron calcular las correlaciones. Asegúrate de que los datos no son constantes.")
    else:
        st.warning("No hay suficientes datos para realizar el análisis de correlación.")

    # --- Visor de Código en el Panel Lateral ---
    with st.sidebar.expander("📖 Ver Código Fuente"):
        st.markdown("Este es el código de la aplicación. ¡Siéntete libre de copiarlo y modificarlo!")
        try:
            with open(__file__, 'r') as f:
                code = f.read()
            st.code(code, language='python')
        except Exception as e:
            st.error(f"Error al leer el código: {e}")
