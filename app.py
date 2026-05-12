import streamlit as st
import pandas as pd
import plotly.express as px
import time
import uuid
import os
from scraper import get_google_sheet, ensure_worksheets
from datetime import datetime
from streamlit_option_menu import option_menu

st.set_page_config(page_title="Gestor Inmobiliario Elche", page_icon="🏠", layout="wide")

# --- ESTILOS PREMIUM ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    /* Tipografía Global */
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Aumentar legibilidad en formularios */
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>select {
        font-size: 16px !important;
    }
    
    /* Tarjetas para Métricas */
    div[data-testid="stMetric"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 15px 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }
    
    /* Estilos para el contenedor principal de métricas personalizadas si las usamos */
    .premium-card {
        background-color: white;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- DATABASE FUNCTIONS ---
@st.cache_data(ttl=60)
def load_data(sheet_name):
    """Carga datos de una pestaña específica con cache."""
    sheet = get_google_sheet()
    if not sheet:
        return pd.DataFrame()
    try:
        ws = sheet.worksheet(sheet_name)
        records = ws.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Error cargando {sheet_name}: {e}")
        return pd.DataFrame()

def move_row(row_data, from_sheet_name, to_sheet_name):
    """Mueve una fila de una pestaña a otra."""
    sheet = get_google_sheet()
    if not sheet: return False
    
    from_ws = sheet.worksheet(from_sheet_name)
    to_ws = sheet.worksheet(to_sheet_name)
    
    # Encontrar la fila (asumiendo que ID es único y está en la columna A)
    try:
        cell = from_ws.find(row_data['ID'])
        row_idx = cell.row
        
        # Insertar en to_ws
        headers = to_ws.row_values(1)
        # Preparar los datos en el orden de las cabeceras
        new_row = [row_data.get(h, "") for h in headers]
        to_ws.append_row(new_row)
        
        # Eliminar de from_ws
        from_ws.delete_rows(row_idx)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error moviendo fila: {e}")
        return False

def delete_row(row_id, sheet_name):
    """Elimina una fila por ID."""
    sheet = get_google_sheet()
    if not sheet: return False
    ws = sheet.worksheet(sheet_name)
    try:
        cell = ws.find(row_id)
        ws.delete_rows(cell.row)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error eliminando fila: {e}")
        return False

def append_to_approved(data_dict):
    """Añade una fila directamente a Approved."""
    sheet = get_google_sheet()
    if not sheet: return False
    ws = sheet.worksheet("Approved")
    try:
        headers = ws.row_values(1)
        if not headers:
            headers = ["ID", "Tipo_Propiedad", "Fecha_Extraccion", "Origen", "URL", "Titulo", "Precio", "Ubicacion", "Metros", "Habitaciones", "Baños", "Planta", "Antigüedad", "Ascensor", "Garaje", "Piscina", "Terraza", "Terraza_Metros", "Caracteristicas", "Notas", "Imagen"]
            ws.append_row(headers)
        new_row = [data_dict.get(h, "") for h in headers]
        ws.append_row(new_row)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error guardando manual: {e}")
        return False

# --- UI COMPONENTS ---
def main():
    with st.sidebar:
        st.markdown("<h2 style='text-align: center; color: #1e3a8a; font-weight: 800;'>🏠 Gestor Elche</h2>", unsafe_allow_html=True)
        choice = option_menu(
            menu_title=None,
            options=["Validación Diaria", "Entrada Manual", "Base de Datos", "Simulador"],
            icons=["inbox-fill", "pencil-square", "bar-chart-fill", "calculator-fill"],
            menu_icon="cast",
            default_index=2,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#3b82f6", "font-size": "18px"}, 
                "nav-link": {"font-size": "16px", "text-align": "left", "margin":"5px", "--hover-color": "#e0f2fe"},
                "nav-link-selected": {"background-color": "#1e3a8a", "color": "white", "font-weight": "600"},
            }
        )
        st.divider()
    
    # Comprobar conexión DB al inicio
    if not os.environ.get("GOOGLE_CREDENTIALS_JSON"):
         st.sidebar.error("Faltan Credenciales de Google (Secretos)")

    if choice == "Validación Diaria":
        st.markdown("<h1 style='color: #1e3a8a; font-weight: 800;'>✅ Validación Diaria</h1>", unsafe_allow_html=True)
        st.markdown("Revisa las propiedades preseleccionadas por el sistema automático y decide si las apruebas para la base de datos.")
        st.divider()
        
        df_pre = load_data("Preselection")
        
        if df_pre.empty:
            st.info("No hay propiedades pendientes de validación.")
        else:
            for index, row in df_pre.iterrows():
                with st.container():
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        img_url = row.get('Imagen', 'https://via.placeholder.com/300x200?text=Sin+Imagen')
                        if not img_url: img_url = 'https://via.placeholder.com/300x200'
                        st.image(img_url, use_column_width=True)
                    
                    with col2:
                        st.subheader(f"{row.get('Titulo', 'Sin título')} - {row.get('Precio', 'N/A')} €")
                        st.write(f"**Ubicación:** {row.get('Ubicacion', 'N/A')} | **Metros:** {row.get('Metros', 'N/A')} m²")
                        st.write(f"**Categoría Detectada:** {row.get('Categoria_Detectada', 'N/A')}")
                        st.markdown(f"[Ver Anuncio Original]({row.get('URL', '#')})")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("Aprobar ✅", key=f"apr_{row.get('ID', index)}"):
                                if move_row(row.to_dict(), "Preselection", "Approved"):
                                    st.success("Propiedad aprobada.")
                                    time.sleep(1)
                                    st.rerun()
                        with col_btn2:
                            if st.button("Descartar ❌", key=f"dsc_{row.get('ID', index)}"):
                                if delete_row(row.get('ID'), "Preselection"):
                                    st.warning("Propiedad descartada.")
                                    time.sleep(1)
                                    st.rerun()
                    st.divider()

    elif choice == "Entrada Manual":
        st.markdown("<h1 style='color: #1e3a8a; font-weight: 800;'>✍️ Entrada Manual</h1>", unsafe_allow_html=True)
        st.markdown("Añade una propiedad o pega una URL para auto-completar los datos.")
        st.divider()
        st.subheader("Extracción por URL (BETA)")
        url_input = st.text_input("Introduce URL de Idealista, Fotocasa o de Agencia")
        if st.button("Extraer Datos"):
            if not url_input:
                st.warning("Por favor, introduce una URL.")
            else:
                with st.spinner("Intentando extraer..."):
                    import requests
                    from bs4 import BeautifulSoup
                    import re
                    try:
                        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
                        res = requests.get(url_input, headers=headers, timeout=10)
                        if res.status_code == 403:
                            st.error("❌ El portal ha bloqueado la conexión (Sistema Anti-bots). Idealista y Fotocasa requieren proxies para la extracción en vivo.")
                        elif res.status_code == 200:
                            soup = BeautifulSoup(res.text, 'html.parser')
                            title = soup.title.string if soup.title else "Anuncio Extraído"
                            
                            import urllib.parse
                            domain = urllib.parse.urlparse(url_input).netloc.replace('www.', '').split('.')[0].capitalize()
                            
                            text_lines = soup.get_text(separator='\n').split('\n')
                            clean_text = '\n'.join([line.strip() for line in text_lines if line.strip()])
                            
                            from scraper import parse_property_data
                            prop_data = parse_property_data(url_input, title, clean_text, domain)
                            
                            habs = prop_data['Habitaciones'] if prop_data['Habitaciones'] else 0
                            banos = prop_data['Baños'] if prop_data['Baños'] else 0
                            planta = prop_data['Planta']
                            metros = prop_data['Metros']
                            precio_est = prop_data['Precio']
                            tiene_terraza = True if prop_data['Terraza'] == "Sí" else False
                            terraza_m2 = prop_data['Terraza_Metros'] if prop_data['Terraza_Metros'] else 0
                            tiene_ascensor = True if prop_data['Ascensor'] == "Sí" else False
                            tiene_garaje = True if prop_data['Garaje'] == "Sí" else False
                            tiene_piscina = True if prop_data['Piscina'] == "Sí" else False
                            tipo_prop = prop_data['Tipo_Propiedad']
                            title = prop_data['Titulo']
                                    
                            st.session_state['ext_titulo'] = title.strip()[:100]
                            st.session_state['ext_precio'] = precio_est
                            st.session_state['ext_metros'] = metros
                            st.session_state['ext_habs'] = habs
                            st.session_state['ext_banos'] = banos
                            st.session_state['ext_planta'] = planta
                            st.session_state['ext_terraza'] = tiene_terraza
                            st.session_state['ext_terraza_m2'] = terraza_m2
                            st.session_state['ext_ascensor'] = tiene_ascensor
                            st.session_state['ext_garaje'] = tiene_garaje
                            st.session_state['ext_piscina'] = tiene_piscina
                            st.session_state['ext_origen'] = domain
                            st.session_state['ext_url'] = url_input
                            st.session_state['ext_tipo'] = tipo_prop
                            st.success("✅ Datos extraídos. Por favor, revisa el formulario abajo.")
                        else:
                            st.warning(f"⚠️ El servidor devolvió el código {res.status_code}")
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")
            
        st.divider()
        st.subheader("Formulario Manual")
        
        # Helper para autodetectar origen
        origen_opts = ["Idealista", "Fotocasa", "Agencia Local", "Offline", "Otro"]
        default_origen = st.session_state.get('ext_origen', '')
        if default_origen and default_origen not in origen_opts:
            origen_opts.insert(0, default_origen)
        
        tab_piso, tab_terreno = st.tabs(["🏢 Piso Centro", "🏞️ Terreno / Ruina"])
        
        with tab_piso:
            with st.form("manual_form_piso", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    titulo = st.text_input("Título del Anuncio *", value=st.session_state.get('ext_titulo', ''))
                    precio = st.number_input("Precio (€) *", min_value=0, step=1000, value=st.session_state.get('ext_precio', 0))
                    metros = st.number_input("Metros Cuadrados *", min_value=0, step=5, value=st.session_state.get('ext_metros', 0))
                    habitaciones = st.number_input("Habitaciones", min_value=0, step=1, value=st.session_state.get('ext_habs', 0))
                    banos = st.number_input("Baños", min_value=0, step=1, value=st.session_state.get('ext_banos', 0))
                    planta = st.text_input("Planta (Bajo, 1º...)", value=st.session_state.get('ext_planta', ''))
                with col2:
                    antiguedad = st.number_input("Antigüedad (Año)", min_value=1800, max_value=2030, step=1, value=None, placeholder="Ej: 1995")
                    ubicacion = st.selectbox("Ubicación", ["Centro", "Raval", "Altabix", "Carrús", "Sector 5", "Otro"])
                    origen_idx = origen_opts.index(default_origen) if default_origen in origen_opts else 2
                    origen = st.selectbox("Origen", origen_opts, index=origen_idx)
                    url = st.text_input("URL del Anuncio", value=st.session_state.get('ext_url', ''))
                with col3:
                    ascensor = st.checkbox("Tiene Ascensor", value=st.session_state.get('ext_ascensor', False))
                    garaje = st.checkbox("Tiene Garaje/Parking", value=st.session_state.get('ext_garaje', False))
                    piscina = st.checkbox("Tiene Piscina", value=st.session_state.get('ext_piscina', False))
                    terraza = st.checkbox("Tiene Terraza/Balcón", value=st.session_state.get('ext_terraza', False))
                    terraza_m2 = st.number_input("Metros de Terraza", min_value=0, step=1, value=st.session_state.get('ext_terraza_m2', 0))
                    caracteristicas = st.text_area("Otras Características")
                    notas = st.text_area("Notas / Valoración cualitativa")
                
                submit_piso = st.form_submit_button("Guardar Piso")
                
                if submit_piso:
                    if not titulo or precio == 0 or metros == 0:
                        st.error("Por favor, rellena los campos obligatorios (*)")
                    else:
                        new_data = {
                            "ID": f"MAN_{uuid.uuid4().hex[:8]}", "Tipo_Propiedad": "Piso",
                            "Fecha_Extraccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Origen": origen, "URL": url, "Titulo": titulo, "Precio": precio, "Ubicacion": ubicacion,
                            "Metros": metros, "Habitaciones": habitaciones, "Baños": banos, "Planta": planta, "Antigüedad": antiguedad if antiguedad else "",
                            "Ascensor": "Sí" if ascensor else "No", "Garaje": "Sí" if garaje else "No", "Piscina": "Sí" if piscina else "No",
                            "Terraza": "Sí" if terraza else "No", "Terraza_Metros": terraza_m2 if terraza_m2 > 0 else "",
                            "Caracteristicas": caracteristicas, "Notas": notas, "Imagen": ""
                        }
                        if append_to_approved(new_data):
                            st.success("Piso guardado exitosamente.")
                            st.balloons()
                            for k in ['ext_titulo', 'ext_precio', 'ext_metros', 'ext_habs', 'ext_banos', 'ext_planta', 'ext_terraza', 'ext_terraza_m2', 'ext_ascensor', 'ext_garaje', 'ext_piscina', 'ext_origen', 'ext_url', 'ext_tipo']:
                                if k in st.session_state: del st.session_state[k]
                        else: st.error("❌ Error guardando.")

        with tab_terreno:
            with st.form("manual_form_terreno", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    titulo_t = st.text_input("Título del Terreno/Ruina *", value=st.session_state.get('ext_titulo', ''))
                    precio_t = st.number_input("Precio (€) *", min_value=0, step=1000, value=st.session_state.get('ext_precio', 0), key="prec_t")
                    metros_t = st.number_input("Metros de Parcela/Superficie *", min_value=0, step=5, value=st.session_state.get('ext_metros', 0), key="met_t")
                    url_t = st.text_input("URL del Anuncio", value=st.session_state.get('ext_url', ''), key="url_t")
                with col2:
                    ubicacion_t = st.selectbox("Ubicación", ["Centro", "Raval", "Altabix", "Carrús", "Sector 5", "Otro"], key="ubi_t")
                    origen_idx_t = origen_opts.index(default_origen) if default_origen in origen_opts else 2
                    origen_t = st.selectbox("Origen", origen_opts, index=origen_idx_t, key="ori_t")
                    caracteristicas_t = st.text_area("Características Especiales (ej. A demoler, Licencia concedida)", key="car_t")
                    notas_t = st.text_area("Notas / Edificabilidad Máxima", key="not_t")
                
                submit_terreno = st.form_submit_button("Guardar Terreno")
                
                if submit_terreno:
                    if not titulo_t or precio_t == 0 or metros_t == 0:
                        st.error("Por favor, rellena los campos obligatorios (*)")
                    else:
                        new_data = {
                            "ID": f"MAN_{uuid.uuid4().hex[:8]}", "Tipo_Propiedad": "Terreno",
                            "Fecha_Extraccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Origen": origen_t, "URL": url_t, "Titulo": titulo_t, "Precio": precio_t, "Ubicacion": ubicacion_t,
                            "Metros": metros_t, "Habitaciones": "", "Baños": "", "Planta": "", "Antigüedad": "",
                            "Ascensor": "", "Garaje": "", "Piscina": "",
                            "Terraza": "", "Terraza_Metros": "",
                            "Caracteristicas": caracteristicas_t, "Notas": notas_t, "Imagen": ""
                        }
                        if append_to_approved(new_data):
                            st.success("Terreno guardado exitosamente.")
                            st.balloons()
                            for k in ['ext_titulo', 'ext_precio', 'ext_metros', 'ext_habs', 'ext_banos', 'ext_planta', 'ext_terraza', 'ext_terraza_m2', 'ext_ascensor', 'ext_garaje', 'ext_piscina', 'ext_origen', 'ext_url', 'ext_tipo']:
                                if k in st.session_state: del st.session_state[k]
                        else: st.error("❌ Error guardando. Comprueba que las credenciales de Google Sheets son correctas en los Secrets.")

    elif choice == "Base de Datos":
        st.markdown("<h1 style='color: #1e3a8a; font-weight: 800;'>📊 Base de Datos y Análisis</h1>", unsafe_allow_html=True)
        st.markdown("Analiza el mercado inmobiliario de Elche con datos en tiempo real.")
        st.divider()
        
        df_app = load_data("Approved")
        
        if df_app.empty:
            st.info("La base de datos está vacía. Aprueba propiedades o añádelas manualmente.")
        else:
            if 'Tipo_Propiedad' not in df_app.columns:
                df_app['Tipo_Propiedad'] = "Piso" # Fallback datos antiguos
                
            tipo_filtro = st.radio("Filtro de Activo:", ["Todos", "Pisos", "Terrenos"], horizontal=True)
            
            if tipo_filtro == "Pisos":
                df_mostrar = df_app[df_app['Tipo_Propiedad'] == 'Piso'].copy()
            elif tipo_filtro == "Terrenos":
                df_mostrar = df_app[df_app['Tipo_Propiedad'] == 'Terreno'].copy()
            else:
                df_mostrar = df_app.copy()
                
            if df_mostrar.empty:
                st.warning(f"No hay datos para la selección: {tipo_filtro}")
            else:
                # Asegurar tipos numéricos para cálculos
                df_mostrar['Precio'] = pd.to_numeric(df_mostrar['Precio'], errors='coerce')
                df_mostrar['Metros'] = pd.to_numeric(df_mostrar['Metros'], errors='coerce')
                df_mostrar['Precio_m2'] = df_mostrar['Precio'] / df_mostrar['Metros']
                
                st.markdown("### ⚡ KPIs del Mercado")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Propiedades", len(df_mostrar))
                col2.metric("Precio Medio", f"{df_mostrar['Precio'].mean():,.0f} €".replace(',', '.'))
                col3.metric("Mediana Precio", f"{df_mostrar['Precio'].median():,.0f} €".replace(',', '.'))
                col4.metric("Precio/m² Medio", f"{df_mostrar['Precio_m2'].mean():,.0f} €/m²".replace(',', '.'))
                
                st.divider()
                st.markdown("### 📈 Análisis Visual Avanzado")
                
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    # Distribución de Precios (Histograma)
                    fig_hist = px.histogram(df_mostrar, x="Precio", nbins=20, 
                                            title="Distribución de Precios", 
                                            color_discrete_sequence=['#3b82f6'])
                    fig_hist.update_layout(bargap=0.1, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_hist, use_container_width=True)
                    
                with col_chart2:
                    # Boxplot por Ubicación para ver dispersión y outliers
                    fig_box = px.box(df_mostrar, x="Ubicacion", y="Precio_m2", 
                                     title="Precio/m² por Zona (Boxplot)", color="Ubicacion")
                    fig_box.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
                    st.plotly_chart(fig_box, use_container_width=True)
                
                st.divider()
                st.markdown("### 📋 Directorio de Activos")
                st.dataframe(df_mostrar.astype(str), use_container_width=True, height=300)
                
                # Botones de acción alineados
                col_btn1, col_btn2 = st.columns([1, 4])
                with col_btn1:
                    csv = df_mostrar.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Exportar CSV",
                        data=csv,
                        file_name=f'propiedades_{tipo_filtro.lower()}.csv',
                        mime='text/csv',
                    )
                with col_btn2:
                    sheet_url = os.environ.get("GOOGLE_SHEET_URL", "#")
                    st.markdown(f"<a href='{sheet_url}' target='_blank' style='display: inline-block; padding: 0.5rem 1rem; background-color: #10b981; color: white; border-radius: 0.375rem; text-decoration: none; font-weight: 600;'>🔗 Abrir en Google Sheets</a>", unsafe_allow_html=True)
                
    elif choice == "Simulador":
        st.markdown("<h1 style='color: #1e3a8a; font-weight: 800;'>🧮 Simulador y Comparador Financiero</h1>", unsafe_allow_html=True)
        st.markdown("Estima todos los costes ocultos (ITP, Notaría, Reformas) de tus opciones favoritas.")
        st.divider()
        
        df_app = load_data("Approved")
        
        if df_app.empty:
            st.warning("Necesitas propiedades en la base de datos para comparar.")
            return
            
        if 'Tipo_Propiedad' not in df_app.columns:
            df_app['Tipo_Propiedad'] = "Piso"
            
        tipo_simulador = st.radio("Tipo de Simulación:", ["🏢 Pisos (Reforma)", "🏞️ Terrenos (Obra Nueva)"], horizontal=True)
        is_terreno = "Terrenos" in tipo_simulador
        
        df_filtrado = df_app[df_app['Tipo_Propiedad'] == ("Terreno" if is_terreno else "Piso")].copy()
        
        if df_filtrado.empty:
            st.warning("No hay propiedades de este tipo para simular.")
            return
            
        # Opciones para comparar
        opciones = df_filtrado['Titulo'] + " (" + df_filtrado['Ubicacion'] + ") - €" + df_filtrado['Precio'].astype(str)
        df_filtrado['Label'] = opciones
        
        seleccionadas = st.multiselect("Selecciona hasta 3 propiedades para comparar", df_filtrado['Label'].tolist(), max_selections=3)
        
        if seleccionadas:
            st.subheader("Parámetros de Simulación")
            col_params1, col_params2, col_params3 = st.columns(3)
            with col_params1:
                porcentaje_itp = st.number_input("ITP (%)", value=10.0, step=0.5, help="Impuesto de Transmisiones Patrimoniales (CV es 10%)")
            with col_params2:
                porcentaje_notaria = st.number_input("Notaría/Registro/Gestoría (%)", value=1.5, step=0.1)
            with col_params3:
                if is_terreno:
                    coste_reforma_m2 = st.number_input("Coste Construcción (€/m²)", value=1200, step=100)
                    coste_licencia_arq = st.number_input("Licencias y Arquitecto (€ est.)", value=30000, step=5000)
                else:
                    coste_reforma_m2 = st.number_input("Coste Reforma Estimado (€/m²)", value=400, step=50)
                    coste_licencia_arq = 0
                
            st.divider()
            st.subheader("Comparativa")
            
            cols = st.columns(len(seleccionadas))
            
            for i, sel in enumerate(seleccionadas):
                prop_data = df_filtrado[df_filtrado['Label'] == sel].iloc[0]
                
                with cols[i]:
                    st.markdown(f"### Opción {i+1}")
                    st.markdown(f"**{prop_data['Titulo']}**")
                    
                    precio = float(prop_data['Precio'])
                    metros = float(prop_data['Metros'])
                    
                    itp_calc = precio * (porcentaje_itp / 100)
                    notaria_calc = precio * (porcentaje_notaria / 100)
                    reforma_calc = metros * coste_reforma_m2
                    total = precio + itp_calc + notaria_calc + reforma_calc + coste_licencia_arq
                    
                    st.write(f"- **Precio Compra:** €{precio:,.2f}")
                    st.write(f"- **Impuestos (ITP):** €{itp_calc:,.2f}")
                    st.write(f"- **Gastos Notaría:** €{notaria_calc:,.2f}")
                    if is_terreno:
                        st.write(f"- **Construcción Estimada:** €{reforma_calc:,.2f}")
                        st.write(f"- **Licencias/Arq:** €{coste_licencia_arq:,.2f}")
                    else:
                        st.write(f"- **Reforma Estimada:** €{reforma_calc:,.2f}")
                    st.markdown("---")
                    st.markdown(f"#### **Total Estimado:** €{total:,.2f}")

if __name__ == "__main__":
    main()
