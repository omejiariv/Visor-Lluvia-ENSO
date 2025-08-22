# --- Preprocesamiento de datos de precipitación mensual ---
try:
    # Eliminar espacios en los nombres de las columnas
    df_precip_mensual.columns = df_precip_mensual.columns.str.strip()
    
    # Convertir la columna 'Id_Fecha' a formato de fecha
    df_precip_mensual['Fecha'] = pd.to_datetime(df_precip_mensual['Id_Fecha'], format='%d/%m/%Y')
    
    # Extraer el año y el mes de la nueva columna 'Fecha'
    df_precip_mensual['Year'] = df_precip_mensual['Fecha'].dt.year
    df_precip_mensual['Mes'] = df_precip_mensual['Fecha'].dt.month
    
    # Derretir el dataframe para tener un formato largo
    df_long = df_precip_mensual.melt(id_vars=['Fecha', 'Year', 'Mes'], var_name='Id_estacion', value_name='Precipitation')
    
    # Eliminar filas con valores 'n.d' y convertir la columna de precipitación a float
    df_long['Precipitation'] = df_long['Precipitation'].replace('n.d', np.nan).astype(float)
    df_long = df_long.dropna(subset=['Precipitation'])

except Exception as e:
    st.error(f"Error en el preprocesamiento del archivo de precipitación mensual: {e}")
    st.stop()
