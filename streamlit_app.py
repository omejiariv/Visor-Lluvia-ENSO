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
import statsmodels.api as sm
import numpy as np
import requests

# Título de la aplicación
st.set_page_config(layout="wide")
st.title(' ☔ Visor de Información Geoespacial de Precipitación 🌧️ ')
st.markdown("---")

# URL de los archivos en GitHub (reemplaza con tu propio repositorio si lo tienes)
GITHUB_BASE_URL = "https://raw.githubusercontent.com/TuUsuario/TuRepositorio/main/"
SHAPEFILE_URL = "https://github.com/TuUsuario/TuRepositorio/raw/main/shapefile.zip"

df = None
df_pptn = None
df_enso = None
gdf_colombia = None

def load_data_from_github():
    """Carga todos los archivos automáticamente desde un repositorio de GitHub."""
    global df, df_pptn, df_enso, gdf_colombia
    
    st.info("Cargando archivos desde GitHub...")
    
    try:
        # Cargar mapaCV.csv
        df = pd.read_csv(f"{GITHUB_BASE_URL}mapaCV.csv", sep=';')
        df.columns = df.columns.str.strip()
        df = df.rename(columns={'Mpio': 'municipio', 'NOMBRE_VER': 'vereda'})
        
        # Cargar DatosPptn_Om.csv
        df_pptn = pd.read_csv(f"{GITHUB_BASE_URL}DatosPptn_Om.csv", sep=';')
        df_pptn.columns = df_pptn.columns.str.strip()
        
        # Cargar ENSO_1950-2023.csv (con la codificación corregida)
        df_enso = pd.read_csv(f"{GITHUB_BASE_URL}ENSO_1950-2023.csv", sep='\t', encoding='latin-1')
        df_enso.columns = df_enso.columns.str.strip()
        df_enso['Año_ENOS'] = df_enso['Año_ENOS'].str.strip()
        
        # Cargar shapefile desde el zip
        response = requests.get(SHAPEFILE_URL)
        if response.status_code == 200:
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, "shapefile.zip")
                with open(zip_path, "wb") as f:
                    f.write(response.content)
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdir)
                
                shp_file = [f for f in os.listdir(tmpdir) if f.endswith('.shp')][0]
                shp_path = os.path.join(tmpdir, shp_file)
                
                gdf_colombia = gpd.read_file(shp_path)
        else:
            st.error(f"Error al descargar el shapefile. Código de estado: {response.status_code}")
            return False

        st.success("¡Archivos cargados automáticamente exitosamente!")
        return True
    
    except Exception as e:
        st.error(f"Ocurrió un error al cargar los datos desde GitHub: {e}")
        return False

# --- Sección para la carga de datos ---
with st.expander(" 📂 Cargar Datos"):
    st.subheader("Carga Automática desde GitHub")
    if st.button("Cargar datos por defecto"):
        load_data_from_github()
    
    st.markdown("---")
    st.subheader("Carga Manual de Archivos")
    st.write("Carga tu archivo `mapaCV.csv` y los archivos del shapefile (`.shp`, `.shx`, `.dbf`) comprimidos en un único archivo `.zip`.")
    
    # Carga de archivos CSV
    uploaded_file_csv = st.file_uploader("Cargar archivo .csv (mapaCV.csv)", type="csv")
    csv_sep = st.text_input("Separador de CSV", value=';')
    if uploaded_file_csv:
        try:
            df = pd.read_csv(uploaded_file_csv, sep=csv_sep)
            df.columns = df.columns.str.strip()
            df = df.rename(columns={'Mpio': 'municipio', 'NOMBRE_VER': 'vereda'})
            st.success("Archivo CSV cargado exitosamente.")
        except Exception as e:
            st.error(f"Error al leer el archivo CSV: {e}")
            df = None
    
    # Carga de archivos del shapefile
    uploaded_zip = st.file_uploader("Cargar archivos shapefile (.zip)", type="zip")
    if uploaded_zip:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, "uploaded.zip")
                with open(zip_path, "wb") as f:
                    f.write(uploaded_zip.getbuffer())
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdir)
                shp_file = [f for f in os.listdir(tmpdir) if f.endswith('.shp')][0]
                shp_path = os.path.join(tmpdir, shp_file)
                gdf_colombia = gpd.read_file(shp_path)
                st.success("Archivos del shapefile cargados exitosamente.")
        except Exception as e:
            st.error(f"Error al leer los archivos del shapefile: {e}")
            gdf_colombia = None
    
    st.markdown("---")
    st.subheader("Cargar Datos de Precipitación y ENSO")
    st.write("Cargar archivo de datos diarios de precipitación (DatosPptn_Om.csv) y el archivo ENSO (ENSO_1950-2023.csv).")

    # Carga de datos de precipitación
    uploaded_pptn = st.file_uploader("Cargar archivo de datos diarios de precipitación", type="csv", key="pptn_uploader")
    if uploaded_pptn:
        try:
            df_pptn = pd.read_csv(uploaded_pptn, sep=csv_sep)
            df_pptn.columns = df_pptn.columns.str.strip()
            st.success("Datos de precipitación cargados exitosamente.")
        except Exception as e:
            st.error(f"Error al leer el archivo de precipitación: {e}")
            df_pptn = None
    
    # Carga de datos ENSO
    uploaded_enso = st.file_uploader("Cargar archivo de datos ENSO", type="csv", key="enso_uploader")
    if uploaded_enso:
        try:
            df_enso = pd.read_csv(uploaded_enso, sep='\t', encoding='latin-1')
            df_enso.columns = df_enso.columns.str.strip()
            df_enso['Año_ENOS'] = df_enso['Año_ENOS'].str.strip()
            st.success("Datos de ENSO cargados exitosamente.")
        except Exception as e:
            st.error(f"Error al leer el archivo ENSO: {e}")
            df_enso = None
    
# --- Sección de visualización de datos ---
if df is not None and gdf_colombia is not None and df_pptn is not None and df_enso is not None:
    st.markdown("---")
    st.header('📊 Visualización y Análisis de Datos')
    
    # Filtro de estaciones
    estaciones = sorted(df['Nombre_Estacion'].unique())
    selected_estaciones = st.multiselect("Selecciona Estaciones:", estaciones, default=estaciones[:5])
    
    # Si se seleccionan estaciones, filtrar el DataFrame
    df_filtered = df[df['Nombre_Estacion'].isin(selected_estaciones)]
    
    # Convertir las columnas de precipitación a numéricas
    for col in df_pptn.columns:
        if col not in ['Id_Fecha', 'Dia', 'mes-año', 'mes', 'año']:
            df_pptn[col] = pd.to_numeric(df_pptn[col].astype(str).str.replace(',', '.'), errors='coerce')
    
    # Crear un control para el rango de años
    min_year = int(df_pptn['año'].min()) if not df_pptn['año'].isnull().all() else 2000
    max_year = int(df_pptn['año'].max()) if not df_pptn['año'].isnull().all() else 2023
    year_range = st.slider(
        "Selecciona el Rango de Años para el Análisis:",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year)
    )

    # --- Gráfico de serie de tiempo de precipitación anual ---
    st.subheader("Precipitación Anual por Estación")
    
    if not selected_estaciones:
        st.info("Por favor, selecciona al menos una estación para visualizar los datos.")
    else:
        df_pptn_filtered = df_pptn[(df_pptn['año'] >= year_range[0]) & (df_pptn['año'] <= year_range[1])]
        
        # Melt el DataFrame para Altair
        df_melted = df_pptn_filtered.melt(id_vars=['Id_Fecha', 'Dia', 'mes-año', 'mes', 'año'],
                                           var_name='Codigo_Estacion',
                                           value_name='Precipitación')
        
        # Unir con el DataFrame de estaciones para obtener el nombre
        df_melted = pd.merge(df_melted, df[['Codigo_Estacion', 'Nombre_Estacion']],
                             on='Codigo_Estacion', how='left')
        
        df_melted = df_melted[df_melted['Nombre_Estacion'].isin(selected_estaciones)]
        
        if not df_melted.empty:
            # Agrupar por año y nombre de estación para obtener la precipitación anual
            df_anual = df_melted.groupby(['año', 'Nombre_Estacion'])['Precipitación'].sum().reset_index()
            
            # Crear el gráfico de líneas con Altair
            chart = alt.Chart(df_anual).mark_line().encode(
                x=alt.X('año', title='Año', axis=alt.Axis(format='d')),
                y=alt.Y('Precipitación', title='Precipitación Anual (mm)'),
                color=alt.Color('Nombre_Estacion', title='Estación'),
                tooltip=['año', 'Precipitación', 'Nombre_Estacion']
            ).properties(
                title='Precipitación Anual por Estación'
            ).interactive()
            
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("El rango de años seleccionado no contiene datos de precipitación para las estaciones seleccionadas. Por favor, ajusta el rango de años.")

    st.markdown("---")

    # --- Mapa interactivo con Folium ---
    st.subheader('Mapa de Estaciones')
    
    # Crear mapa base
    m = folium.Map(location=[df['Latitud'].mean(), df['Longitud'].mean()], zoom_start=7, tiles="OpenStreetMap")
    
    # Añadir marcadores para las estaciones seleccionadas
    for index, row in df_filtered.iterrows():
        folium.Marker(
            location=[row['Latitud'], row['Longitud']],
            tooltip=f"Estación: {row['Nombre_Estacion']}",
            popup=f"Estación: {row['Nombre_Estacion']}<br>Lat: {row['Latitud']}<br>Lon: {row['Longitud']}"
        ).add_to(m)
        
    # Mostrar el mapa
    folium_static(m)

    st.markdown("---")

    # --- Relación entre precipitación y ENSO ---
    st.subheader("Análisis de la Relación entre Precipitación y ENSO")
    
    if not selected_estaciones:
        st.info("Por favor, selecciona al menos una estación para el análisis ENSO.")
    else:
        # Calcular la precipitación mensual por estación
        df_pptn_filtered = df_pptn[(df_pptn['año'] >= df_enso['Año'].min()) & (df_pptn['año'] <= df_enso['Año'].max())].copy()
        
        df_melted_pptn_mensual = df_pptn_filtered.melt(id_vars=['año', 'mes'],
                                                     var_name='Codigo_Estacion',
                                                     value_name='Precipitación')
        
        df_melted_pptn_mensual = pd.merge(df_melted_pptn_mensual, df[['Codigo_Estacion', 'Nombre_Estacion']],
                                         on='Codigo_Estacion', how='left')
        df_melted_pptn_mensual['Precipitación'] = pd.to_numeric(df_melted_pptn_mensual['Precipitación'], errors='coerce')
        
        pptn_mensual_promedio_estacion = df_melted_pptn_mensual.groupby(['año', 'mes', 'Nombre_Estacion'])['Precipitación'].sum().reset_index()
        
        # Merge de datos ENSO y precipitación
        df_enso['mes'] = df_enso['mes'].astype(int)
        df_enso['Año'] = df_enso['Año'].astype(int)
        
        df_enso_precip = pd.merge(pptn_mensual_promedio_estacion, df_enso, on=['año', 'mes'], how='left')
        
        df_enso_precip_filtered = df_enso_precip[df_enso_precip['Nombre_Estacion'].isin(selected_estaciones)]
        
        if not df_enso_precip_filtered.empty:
            
            # Gráfico de barras de Precipitación vs ENSO
            fig_enso = px.bar(df_enso_precip_filtered,
                              x='Año',
                              y='Precipitación',
                              color='Año_ENOS',
                              facet_col='Nombre_Estacion',
                              facet_col_wrap=2,
                              title='Precipitación Mensual y Tipo de Evento ENSO por Estación',
                              labels={'Precipitación': 'Precipitación Mensual (mm)', 'Año_ENOS': 'Evento ENSO'})
            
            st.plotly_chart(fig_enso, use_container_width=True)

            # Análisis de Correlación
            st.subheader("Correlación entre Precipitación y ENSO")
            
            # Convertir 'Precipitación' a numérica, reemplazando comas con puntos si es necesario
            df_enso_precip_filtered['Precipitación'] = pd.to_numeric(df_enso_precip_filtered['Precipitación'], errors='coerce')
            
            # Calcular la precipitación promedio para todas las estaciones seleccionadas
            pptn_promedio_total = df_enso_precip_filtered.groupby(['año', 'mes'])['Precipitación'].mean().reset_index()
            df_merged_corr = pd.merge(pptn_promedio_total, df_enso, on=['año', 'mes'], how='left')
            
            # Eliminar filas con valores NaN
            df_merged_corr.dropna(subset=['Precipitación', 'ONI_IndOceanico'], inplace=True)
            
            # Asegurar que las columnas sean numéricas antes de la correlación
            df_merged_corr['Precipitación'] = pd.to_numeric(df_merged_corr['Precipitación'], errors='coerce')
            df_merged_corr['ONI_IndOceanico'] = pd.to_numeric(df_merged_corr['ONI_IndOceanico'], errors='coerce')

            # Calcular la correlación
            if len(df_merged_corr) > 1:
                correlation = df_merged_corr['Precipitación'].corr(df_merged_corr['ONI_IndOceanico'])
                st.write(f"Coeficiente de correlación entre la precipitación promedio de las estaciones y el Índice Oceánico ONI: **{correlation:.2f}**")

                if correlation > 0.3:
                    st.success("Existe una correlación positiva, lo que sugiere que los eventos El Niño están asociados con una mayor precipitación.")
                elif correlation < -0.3:
                    st.success("Existe una correlación negativa, lo que sugiere que los eventos La Niña están asociados con una mayor precipitación.")
                else:
                    st.info("La correlación es débil o inexistente.")
            else:
                st.warning("No hay suficientes datos para calcular la correlación. Por favor, ajusta los filtros de año o carga más datos.")
        else:
            st.info("No hay datos de precipitación para el rango de años de ENSO en las estaciones seleccionadas.")

    st.markdown("---")

    # --- Mapa animado de Precipitación Anual ---
    st.subheader("Mapa Animado de Precipitación Anual")
    
    if not selected_estaciones:
        st.info("Por favor, selecciona estaciones para la animación.")
    else:
        df_anual_map = df_melted.groupby(['año', 'Nombre_Estacion', 'Latitud', 'Longitud'])['Precipitación'].sum().reset_index()
        df_melted_map = pd.merge(df_anual_map, df[['Codigo_Estacion', 'Nombre_Estacion', 'Latitud', 'Longitud']],
                                  on='Nombre_Estacion', how='left')
        
        df_melted_map.drop_duplicates(subset=['año', 'Nombre_Estacion'], inplace=True)
        
        if not df_melted_map.empty:
            y_range = [df_melted_map['Precipitación'].min(), df_melted_map['Precipitación'].max()]
            fig = px.scatter_mapbox(
                df_melted_map,
                lat="Latitud",
                lon="Longitud",
                hover_name="Nombre_Estacion",
                hover_data={"Precipitación": True, "año": True, "Latitud": False, "Longitud": False},
                color="Precipitación",
                size="Precipitación",
                color_continuous_scale=px.colors.sequential.Bluyl,
                animation_frame="año",
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

else:
    st.warning("Por favor, carga todos los archivos necesarios para ver las visualizaciones.")
