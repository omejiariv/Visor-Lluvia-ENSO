# --- Preprocesamiento de datos de precipitación mensual ---
    try:
        # Renombrar columnas para estandarizar 'año' y 'mes' sin importar mayúsculas o tildes
        df_precip_mensual.columns = df_precip_mensual.columns.str.lower()
        
        # Buscar la columna del año de forma flexible
        year_col_candidates = [col for col in df_precip_mensual.columns if 'año' in col or 'year' in col]
        if year_col_candidates:
            df_precip_mensual.rename(columns={year_col_candidates[0]: 'Year'}, inplace=True)
        else:
            raise KeyError("No se encontró la columna de 'año' o 'year' en el archivo de precipitación mensual.")

        # Buscar la columna del mes de forma flexible
        mes_col_candidates = [col for col in df_precip_mensual.columns if 'mes' in col]
        if mes_col_candidates:
            df_precip_mensual.rename(columns={mes_col_candidates[0]: 'Mes'}, inplace=True)
        else:
            raise KeyError("No se encontró la columna de 'mes' en el archivo de precipitación mensual.")
            
        # Identificar columnas de estaciones para melt
        station_cols = [col for col in df_precip_mensual.columns if col.isdigit() and len(col) == 8]
        
        if not station_cols:
            st.error("No se encontraron columnas de estación válidas en el archivo de precipitación mensual. Verifique el formato de los IDs.")
            st.stop()
            
        df_long = df_precip_mensual.melt(
            id_vars=['id_fecha', 'Year', 'Mes'], 
            value_vars=station_cols,
            var_name='Id_estacion', 
            value_name='Precipitation'
        )
        
        # Convertir a fecha y crear la columna de fecha para la fusión
        df_long['Precipitation'] = df_long['Precipitation'].replace('n.d', np.nan).astype(float)
        df_long = df_long.dropna(subset=['Precipitation'])
        
        df_long['Fecha'] = pd.to_datetime(df_long['Year'].astype(str) + '-' + df_long['Mes'].astype(str), format='%Y-%m')
        
    except Exception as e:
        st.error(f"Error en el preprocesamiento del archivo de precipitación mensual: {e}")
        st.stop()
