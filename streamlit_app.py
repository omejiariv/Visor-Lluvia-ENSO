# --- Análisis ENSO ---
st.header("Análisis de Precipitación y el Fenómeno ENSO")
st.markdown("Esta sección explora la relación entre la precipitación y los eventos de El Niño-Oscilación del Sur.")

# Preparar los datos para el análisis
df_analisis = df_long.copy()

# Fusión con los datos ENSO
try:
    # Convertir la columna de fecha de la precipitación a formato 'YYYY-MM'
    df_analisis['fecha_merge'] = df_analisis['Fecha'].dt.strftime('%Y-%m')

    # Convertir las columnas de año y mes del ENSO a formato 'YYYY-MM'
    df_enso['fecha_merge'] = pd.to_datetime(df_enso['Year'].astype(str) + '-' + df_enso['mes'], format='%Y-%b').dt.strftime('%Y-%m')
    
    # Fusionar los dataframes
    df_analisis = pd.merge(df_analisis, df_enso[['fecha_merge', 'Anomalia_ONI', 'ENSO']], on='fecha_merge', how='left')
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
