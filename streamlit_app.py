with tab_interp:
    st.subheader("Superficie de Precipitación Anual por Kriging")
    st.markdown("Mapa base con la superficie de lluvia interpolada a partir de la precipitación media anual.")

    if not df_precip_anual_filtered_melted.empty:
        # Calcular la precipitación media anual para cada estación
        df_mean_precip = df_precip_anual_filtered_melted.groupby('Nom_Est')[['Longitud_geo', 'Latitud_geo', 'Precipitación']].mean().reset_index()

        # Definir la grilla de interpolación
        longs = np.unique(df_mean_precip['Longitud_geo'])
        lats = np.unique(df_mean_precip['Latitud_geo'])

        # Verificar si hay suficientes puntos para interpolar
        if len(longs) < 2 or len(lats) < 2:
            st.warning("No hay suficientes estaciones seleccionadas para generar una superficie de interpolación. Seleccione al menos dos estaciones con diferentes longitudes y latitudes.")
        else:
            lon_grid = np.linspace(min(longs), max(longs), 100)
            lat_grid = np.linspace(min(lats), max(lats), 100)

            z_grid = None
            interpolation_method = "Kriging"
            
            # --- Intento de interpolación con Kriging ---
            try:
                OK = OrdinaryKriging(
                    df_mean_precip['Longitud_geo'].values,
                    df_mean_precip['Latitud_geo'].values,
                    df_mean_precip['Precipitación'].values,
                    variogram_model='linear',
                    verbose=False,
                    enable_plotting=False
                )
                z_grid, ss_grid = OK.execute("grid", lon_grid, lat_grid)
                z_grid = z_grid.data
                
                # Validar si el resultado de Kriging es válido
                if np.isnan(z_grid).all() or z_grid.size == 0:
                    raise ValueError("Kriging no pudo generar una grilla válida. Intentando con un método alternativo.")

            except Exception as e:
                st.warning(f"Kriging no pudo generar una superficie de interpolación válida: {e}. Esto puede suceder si los datos no son adecuados para este método. Usando un método de interpolación más simple como respaldo.")
                interpolation_method = "Griddata (Fallback)"
                
                # --- Método de respaldo: griddata de SciPy ---
                points = df_mean_precip[['Longitud_geo', 'Latitud_geo']].values
                values = df_mean_precip['Precipitación'].values
                grid_x, grid_y = np.meshgrid(lon_grid, lat_grid)
                
                z_grid = griddata(points, values, (grid_x, grid_y), method='linear')
            
            # --- Creación del mapa de contorno si la grilla es válida ---
            if z_grid is not None and not np.isnan(z_grid).all() and z_grid.size > 0:
                fig_interp = go.Figure(data=go.Contour(
                    x=lon_grid,
                    y=lat_grid,
                    z=z_grid.T, # NOTA: La transpuesta es crucial para que Plotly interprete la grilla correctamente
                    colorscale='YlGnBu',
                    contours_showlabels=True,
                    line_smoothing=0.85
                ))

                # Añadir las estaciones como puntos sobre el contorno
                fig_interp.add_trace(go.Scattergeo(
                    lat=df_mean_precip['Latitud_geo'],
                    lon=df_mean_precip['Longitud_geo'],
                    mode='markers',
                    marker=dict(
                        size=10,
                        color='black',
                        symbol='circle',
                        line=dict(width=1, color='white')
                    ),
                    hoverinfo='text',
                    hovertext=df_mean_precip['Nom_Est'] + '<br>Pptn. Anual: ' + df_mean_precip['Precipitación'].round(2).astype(str),
                    name='Estaciones de Lluvia'
                ))

                # Centrar el mapa manualmente
                center_lat = (max(lats) + min(lats)) / 2
                center_lon = (max(longs) + min(longs)) / 2
                zoom_factor = 10 

                fig_interp.update_layout(
                    title_text=f'Superficie de Precipitación Media Anual ({interpolation_method})',
                    geo=dict(
                        scope='south america',
                        showland=True,
                        landcolor='rgb(217, 217, 217)',
                        countrycolor='rgb(204, 204, 204)',
                        showcountries=True,
                        center=dict(lat=center_lat, lon=center_lon),
                        projection_scale=zoom_factor
                    )
                )
                st.plotly_chart(fig_interp, use_container_width=True)
            else:
                st.warning("La grilla de interpolación generada no es válida. Por favor, intente con una selección de estaciones diferente.")
    else:
        st.warning("No hay datos suficientes para generar el mapa de interpolación.")
