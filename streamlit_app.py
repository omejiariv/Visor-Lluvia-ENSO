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

# Inicializar st.session_state para almacenar los DataFrames
if 'df' not in st.session_state:
    st.session_state.df = None
if 'df_pptn' not in st.session_state:
    st.session_state.df_pptn = None
if 'df_enso' not in st.session_state:
    st.session_state.df_enso = None
if 'gdf_colombia' not in st.session_state:
    st.session_state.gdf_colombia = None

def load_data_from_github():
    """Carga todos los archivos automáticamente desde un repositorio de GitHub."""
    st.info("Cargando archivos desde GitHub...")
    
    try:
        # Cargar mapaCV.csv
        st.session_state.df = pd.read_csv(f"{GITHUB_BASE_URL}mapaCV.csv", sep=';')
        st.session_state.df.columns = st.session_state.df.columns.str.strip()
        
        # Cargar DatosPptn_Om.csv
        st.session_state.df_pptn = pd.read_csv(f"{GITHUB_BASE_URL}DatosPptn_Om.csv", sep=';')
        st.session_state.df_pptn.columns = st.session_state.df_pptn.columns.str.strip()
        
        # Cargar ENSO_1950-2023.csv (con la codificación y separador corregidos)
        df_enso_raw = pd.read_csv(f"{GITHUB_BASE_URL}ENSO_1950-2023.csv", sep=';', encoding='latin-1')
        df_enso_raw.columns = df_enso_raw.columns.str.strip()
        
        # Lógica más robusta para encontrar y renombrar columnas
        column_mapping = {
            'año': ['Año', 'año', 'AÑO'],
            'mes': ['mes', 'MES'],
            'ENOS': ['ENOS', 'enos', 'Ano_ENOS', 'Año_ENOS']
        }
        
        found_columns = {}
        for required_col, possible_names in column_mapping.items():
            for name in possible_names:
                if name in df_enso_raw.columns:
                    found_columns[name] = required_col
                    break
        
        st.session_state.df_enso = df_enso_raw.rename(columns=found_columns)
        
        required_cols = list(column_mapping.keys())
        if all(col in st.session_state.df_enso.columns for col in required_cols):
            # Convertir las columnas a tipo int para su correcto manejo
            st.session_state.df_enso['año'] = st.session_state.df_enso['año'].astype(int)
            st.session_state.df_enso['mes'] = st.session_state.df_enso['mes'].astype(int)
            st.session_state.df_enso['ENOS'] = st.session_state.df_enso['ENOS'].str.strip()
            st.success("Datos de ENSO cargados exitosamente.")
        else:
            missing_cols = [col for col in required_cols if col not in st.session_state.df_enso.columns]
            st.error(f"Error al leer el archivo ENSO: Faltan las siguientes columnas: {', '.join(missing_cols)}. La carga automática falló.")
            st.session_state.df_enso = None
            
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
                
                st.session_state.gdf_colombia = gpd.read_file(shp_path)
        else:
            st.error(f"Error al descargar el shapefile. Código de estado: {response.status_code}")
            return False

        st.success("¡Archivos cargados automáticamente exitosamente!")
        return True
    
    except Exception as e:
        st.error(f"Ocurrió un error al cargar los datos desde GitHub: {e}")
        return False

# --- Configuración en el panel lateral (sidebar) ---
with st.sidebar:
    st.header('🔧 Controles y Configuración')

    # --- Sección para la carga de datos ---
    with st.expander(" 📂 Cargar Datos"):
        st.subheader("Carga Automática desde GitHub")
        if st.button("Cargar datos por defecto"):
            load_data_from_github()
        
        st.markdown("---")
        st.subheader("Carga Manual de Archivos")
        st.write("Carga tu archivo `mapaCV.csv` y los archivos del shapefile (`.shp`, `.shx`, `.dbf`) comprimidos en un único archivo `.zip`.")
        
        # Carga de archivos CSV
        uploaded_file_csv = st.file_uploader("Cargar archivo .csv (mapaCV.csv)", type="csv", key="csv_mapa")
        csv_sep_mapa = st.text_input("Separador del archivo mapaCV.csv", value=';')
        if uploaded_file_csv:
            try:
                st.session_state.df = pd.read_csv(uploaded_file_csv, sep=csv_sep_mapa)
                st.session_state.df.columns = st.session_state.df.columns.str.strip()
                st.success("Archivo mapaCV.csv cargado exitosamente.")
            except Exception as e:
                st.error(f"Error al leer el archivo CSV: {e}")
                st.session_state.df = None
        
        # Carga de archivos del shapefile
        uploaded_zip = st.file_uploader("Cargar archivos shapefile (.zip)", type="zip", key="shp_zip")
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
                    st.session_state.gdf_colombia = gpd.read_file(shp_path)
                    st.success("Archivos del shapefile cargados exitosamente.")
            except Exception as e:
                st.error(f"Error al leer los archivos del shapefile: {e}")
                st.session_state.gdf_colombia = None
        
        st.markdown("---")
        st.subheader("Cargar Datos de Precipitación y ENSO")
        
        # Carga de datos de precipitación
        uploaded_pptn = st.file_uploader("Cargar archivo de datos diarios de precipitación", type="csv", key="pptn_uploader")
        csv_sep_pptn = st.text_input("Separador de datos de precipitación", value=';')
        if uploaded_pptn:
            try:
                st.session_state.df_pptn = pd.read_csv(uploaded_pptn, sep=csv_sep_pptn)
                st.session_state.df_pptn.columns = st.session_state.df_pptn.columns.str.strip()
                st.success("Datos de precipitación cargados exitosamente.")
            except Exception as e:
                st.error(f"Error al leer el archivo de precipitación: {e}")
                st.session_state.df_pptn = None
        
        # Carga de datos ENSO
        uploaded_enso = st.file_uploader("Cargar archivo de datos ENSO", type="csv", key="enso_uploader")
        csv_sep_enso = st.text_input("Separador de datos ENSO", value=';')
        if uploaded_enso:
            try:
                df_enso_raw = pd.read_csv(uploaded_enso, sep=csv_sep_enso, encoding='latin-1')
                df_enso_raw.columns = df_enso_raw.columns.str.strip()
                
                # Definir un mapeo de posibles nombres de columnas a los nombres requeridos
                column_mapping = {
                    'año': ['Año', 'año', 'AÑO'],
                    'mes': ['mes', 'MES'],
                    'ENOS': ['ENOS', 'enos', 'Ano_ENOS', 'Año_ENOS']
                }
                
                found_columns = {}
                for required_col, possible_names in column_mapping.items():
                    for name in possible_names:
                        if name in df_enso_raw.columns:
                            found_columns[name] = required_col
                            break
                
                st.session_state.df_enso = df_enso_raw.rename(columns=found_columns)
                
                required_cols = list(column_mapping.keys())
                if all(col in st.session_state.df_enso.columns for col in required_cols):
                    # Convertir las columnas a tipo int para su correcto manejo
                    st.session_state.df_enso['año'] = st.session_state.df_enso['año'].astype(int)
                    st.session_state.df_enso['mes'] = st.session_state.df_enso['mes'].astype(int)
                    st.session_state.df_enso['ENOS'] = st.session_state.df_enso['ENOS'].str.strip()
                    st.success("Datos de ENSO cargados exitosamente.")
                else:
                    missing_cols = [col for col in required_cols if col not in st.session_state.df_enso.columns]
                    st.error(f"Error al leer el archivo ENSO: Faltan las siguientes columnas: {', '.join(missing_cols)}. Asegúrate de que el archivo contiene las columnas 'Año', 'mes' y 'ENOS'.")
                    st.session_state.df_enso = None
            except Exception as e:
                st.error(f"Error al leer el archivo ENSO: {e}")
                st.session_state.df_enso = None
    
# --- Sección de visualización de datos ---
if st.session_state.df is not None and st.session_state.gdf_colombia is not None and st.session_state.df_pptn is not None:
    st.markdown("---")
    st.header('📊 Visualización y Análisis de Datos')
    
    # Sección para seleccionar la columna de nombres de estación y los años
    st.sidebar.subheader("Configuración de Estaciones y Tiempo")
    
    # Asegurarse de que las columnas están disponibles antes de mostrar el selectbox
    columnas_df = list(st.session_state.df.columns)
    selected_name_col = st.sidebar.selectbox(
        "Selecciona la columna con los nombres de las estaciones:",
        columnas_df,
        index=columnas_df.index('Nom_Est') if 'Nom_Est' in columnas_df else 0,
        placeholder="Selecciona una columna..."
    )
    if selected_name_col:
        st.session_state.df = st.session_state.df.rename(columns={selected_name_col: 'Nombre_Estacion'})
        st.sidebar.success(f"La columna '{selected_name_col}' ha sido asignada como 'Nombre_Estacion'.")
    else:
        st.warning("Por favor, selecciona la columna de nombres de estación para continuar.")
        st.stop()
        
    columnas_pptn = list(st.session_state.df_pptn.columns)
    selected_year_col = st.sidebar.selectbox(
        "Selecciona la columna con el año (Precipitación):",
        columnas_pptn,
        index=columnas_pptn.index('año') if 'año' in columnas_pptn else 0,
        placeholder="Selecciona una columna..."
    )
    selected_month_col = st.sidebar.selectbox(
        "Selecciona la columna con el mes (Precipitación):",
        columnas_pptn,
        index=columnas_pptn.index('mes') if 'mes' in columnas_pptn else 0,
        placeholder="Selecciona una columna..."
    )

    if selected_year_col and selected_month_col:
        # Renombrar las columnas ANTES de usarlas
        st.session_state.df_pptn = st.session_state.df_pptn.rename(columns={selected_year_col: 'año', selected_month_col: 'mes'})
    else:
        st.warning("Por favor, selecciona las columnas de año y mes para continuar.")
        st.stop()

    # Filtro de estaciones
    estaciones = sorted(st.session_state.df['Nombre_Estacion'].unique())
    selected_estaciones = st.sidebar.multiselect("Selecciona Estaciones:", estaciones, default=estaciones[:5])
    
    # Si se seleccionan estaciones, filtrar el DataFrame
    df_filtered = st.session_state.df[st.session_state.df['Nombre_Estacion'].isin(selected_estaciones)]
    
    # Convertir las columnas de precipitación a numéricas
    for col in st.session_state.df_pptn.columns:
        if col not in ['Id_Fecha', 'Dia', 'mes-año', 'mes', 'año']:
            st.session_state.df_pptn[col] = pd.to_numeric(st.session_state.df_pptn[col].astype(str).str.replace(',', '.'), errors='coerce')
    
    # Crear un control para el rango de años
    min_year_pptn = int(st.session_state.df_pptn['año'].min()) if 'año' in st.session_state.df_pptn.columns and not st.session_state.df_pptn['año'].isnull().all() else 2000
    max_year_pptn = int(st.session_state.df_pptn['año'].max()) if 'año' in st.session_state.df_pptn.columns and not st.session_state.df_pptn['año'].isnull().all() else 2023
    
    min_year_enso = int(st.session_state.df_enso['año'].min()) if st.session_state.df_enso is not None and 'año' in st.session_state.df_enso.columns and not st.session_state.df_enso['año'].isnull().all() else min_year_pptn
    max_year_enso = int(st.session_state.df_enso['año'].max()) if st.session_state.df_enso is not None and 'año' in st.session_state.df_enso.columns and not st.session_state.df_enso['año'].isnull().all() else max_year_pptn
    
    min_combined_year = min(min_year_pptn, min_year_enso)
    max_combined_year = max(max_year_pptn, max_year_enso)
    
    year_range = st.sidebar.slider(
        "Selecciona el Rango de Años para el Análisis:",
        min_value=min_combined_year,
        max_value=max_combined_year,
        value=(min_combined_year, max_combined_year)
    )

    # --- Gráfico de serie de tiempo de precipitación anual ---
    st.subheader("Precipitación Anual por Estación")
    
    if not selected_estaciones:
        st.info("Por favor, selecciona al menos una estación para visualizar los datos.")
    else:
        df_pptn_filtered = st.session_state.df_pptn[(st.session_state.df_pptn['año'] >= year_range[0]) & (st.session_state.df_pptn['año'] <= year_range[1])]
        
        # Melt el DataFrame para Altair
        df_melted = df_pptn_filtered.melt(id_vars=['Id_Fecha', 'Dia', 'mes-año', 'mes', 'año'],
                                           var_name='Codigo_Estacion',
                                           value_name='Precipitación')
        
        # Unir con el DataFrame de estaciones para obtener el nombre
        df_melted = pd.merge(df_melted, st.session_state.df[['Codigo_Estacion', 'Nombre_Estacion']],
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
    m = folium.Map(location=[st.session_state.df['Latitud'].mean(), st.session_state.df['Longitud'].mean()], zoom_start=7, tiles="OpenStreetMap")
    
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

    # --- Sección de análisis ENSO (solo se muestra si el archivo se carga correctamente) ---
    if st.session_state.df_enso is not None:
        st.subheader("Análisis de la Relación entre Precipitación y ENSO")
        
        if not selected_estaciones:
            st.info("Por favor, selecciona al menos una estación para el análisis ENSO.")
        else:
            # Calcular la precipitación mensual por estación
            df_pptn_filtered = st.session_state.df_pptn[(st.session_state.df_pptn['año'] >= year_range[0]) & (st.session_state.df_pptn['año'] <= year_range[1])].copy()
            
            df_melted_pptn_mensual = df_pptn_filtered.melt(id_vars=['año', 'mes'],
                                                         var_name='Codigo_Estacion',
                                                         value_name='Precipitación')
            
            df_melted_pptn_mensual = pd.merge(df_melted_pptn_mensual, st.session_state.df[['Codigo_Estacion', 'Nombre_Estacion']],
                                             on='Codigo_Estacion', how='left')
            df_melted_pptn_mensual['Precipitación'] = pd.to_numeric(df_melted_pptn_mensual['Precipitación'], errors='coerce')
            
            pptn_mensual_promedio_estacion = df_melted_pptn_mensual.groupby(['año', 'mes', 'Nombre_Estacion'])['Precipitación'].sum().reset_index()
            
            # Merge de datos ENSO y precipitación
            df_enso_precip = pd.merge(pptn_mensual_promedio_estacion, st.session_state.df_enso, on=['año', 'mes'], how='left')
            
            df_enso_precip_filtered = df_enso_precip[df_enso_precip['Nombre_Estacion'].isin(selected_estaciones)]
            
            if not df_enso_precip_filtered.empty:
                
                # Gráfico de barras de Precipitación vs ENSO
                fig_enso = px.bar(df_enso_precip_filtered,
                                  x='año',
                                  y='Precipitación',
                                  color='ENOS',
                                  facet_col='Nombre_Estacion',
                                  facet_col_wrap=2,
                                  title='Precipitación Mensual y Tipo de Evento ENSO por Estación',
                                  labels={'Precipitación': 'Precipitación Mensual (mm)', 'ENOS': 'Evento ENSO'})
                
                st.plotly_chart(fig_enso, use_container_width=True)

                # Análisis de Correlación
                st.subheader("Correlación entre Precipitación y ENSO")
                
                df_enso_precip_filtered['Precipitación'] = pd.to_numeric(df_enso_precip_filtered['Precipitación'], errors='coerce')
                
                pptn_promedio_total = df_enso_precip_filtered.groupby(['año', 'mes'])['Precipitación'].mean().reset_index()
                
                # Asegurar que la columna 'ONI_IndOceanico' exista antes de intentar usarla
                if 'ONI_IndOceanico' in st.session_state.df_enso.columns:
                    df_merged_corr = pd.merge(pptn_promedio_total, st.session_state.df_enso, on=['año', 'mes'], how='left')
                else:
                    st.warning("No se encontró la columna 'ONI_IndOceanico' en el archivo ENSO para el análisis de correlación.")
                    df_merged_corr = pd.DataFrame() # Crear un DataFrame vacío para evitar errores
                
                if not df_merged_corr.empty:
                    df_merged_corr.dropna(subset=['Precipitación', 'ONI_IndOceanico'], inplace=True)
                    
                    df_merged_corr['Precipitación'] = pd.to_numeric(df_merged_corr['Precipitación'], errors='coerce')
                    df_merged_corr['ONI_IndOceanico'] = pd.to_numeric(df_merged_corr['ONI_IndOceanico'], errors='coerce')

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
                    st.info("No se puede realizar el análisis de correlación. Por favor, verifica que los datos ENSO se cargaron correctamente.")
            else:
                st.info("No hay datos de precipitación para el rango de años de ENSO en las estaciones seleccionadas.")
    else:
        st.info("No se puede realizar el análisis de ENSO porque el archivo no ha sido cargado exitosamente. Por favor, carga el archivo ENSO para habilitar esta funcionalidad.")

    st.markdown("---")

    # --- Mapa animado de Precipitación Anual ---
    st.subheader("Mapa Animado de Precipitación Anual")
    
    if not selected_estaciones:
        st.info("Por favor, selecciona estaciones para la animación.")
    else:
        df_pptn_filtered = st.session_state.df_pptn[(st.session_state.df_pptn['año'] >= year_range[0]) & (st.session_state.df_pptn['año'] <= year_range[1])]
        df_melted = df_pptn_filtered.melt(id_vars=['Id_Fecha', 'Dia', 'mes-año', 'mes', 'año'],
                                           var_name='Codigo_Estacion',
                                           value_name='Precipitación')
        df_melted = pd.merge(df_melted, st.session_state.df[['Codigo_Estacion', 'Nombre_Estacion', 'Latitud', 'Longitud']],
                             on='Codigo_Estacion', how='left')
        
        df_anual_map = df_melted.groupby(['año', 'Nombre_Estacion', 'Latitud', 'Longitud'])['Precipitación'].sum().reset_index()
        
        if not df_anual_map.empty:
            y_range = [df_anual_map['Precipitación'].min(), df_anual_map['Precipitación'].max()]
            fig = px.scatter_mapbox(
                df_anual_map,
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
                mapbox_center={"lat": df_anual_map['Latitud'].mean(), "lon": df_anual_map['Longitud'].mean()},
            )
            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("El rango de años seleccionado no contiene datos de precipitación para las estaciones seleccionadas. Por favor, ajusta el rango de años.")

else:
    st.warning("Por favor, carga los archivos `mapaCV.csv`, de precipitación, y el shapefile para ver las visualizaciones.")
    if st.session_state.df_enso is None:
        st.info("El análisis ENSO no estará disponible hasta que cargues el archivo correctamente.")
