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

def update_row(row_id, sheet_name, new_data):
    """Actualiza una fila existente."""
    sheet = get_google_sheet()
    if not sheet: return False
    ws = sheet.worksheet(sheet_name)
    try:
        cell = ws.find(row_id)
        row_idx = cell.row
        headers = ws.row_values(1)
        
        existing_row = ws.row_values(row_idx)
        while len(existing_row) < len(headers):
            existing_row.append("")
            
        updated_row = []
        for i, h in enumerate(headers):
            if h in new_data:
                updated_row.append(str(new_data[h]))
            else:
                updated_row.append(existing_row[i] if i < len(existing_row) else "")
                
        cell_list = ws.range(row_idx, 1, row_idx, len(headers))
        for i, cell_obj in enumerate(cell_list):
            cell_obj.value = updated_row[i]
        ws.update_cells(cell_list)
        
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error actualizando fila: {e}")
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
            headers = ["ID", "Tipo_Propiedad", "Fecha_Extraccion", "Origen", "URL", "Titulo", "Precio", "Ubicacion", "Metros", "Habitaciones", "Baños", "Planta", "Antigüedad", "Ascensor", "Garaje", "Piscina", "Terraza", "Terraza_Metros", "Caracteristicas", "Notas", "Imagen", "Favorito", "Visitado"]
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
        st.markdown("<h3 style='text-align: left; color: #1e3a8a; font-weight: 800; padding-left: 5px;'>📌 Apartados</h3>", unsafe_allow_html=True)
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

    # Título global en la parte superior de todas las páginas
    st.markdown("""
        <div style='border-bottom: 3px solid #1e3a8a; padding-bottom: 10px; margin-bottom: 30px;'>
            <h1 style='color: #1e3a8a; font-size: 3.5rem; font-weight: 900; margin-bottom: 0;'>🏠 Casa nueva de Arias-Brotóns</h1>
        </div>
    """, unsafe_allow_html=True)

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
                            
                            # Limpiar las keys específicas del formulario de terrenos para forzar su actualización
                            for k in ['fav_t', 'vis_t', 'prec_t', 'met_t', 'url_t', 'ubi_t', 'ori_t', 'car_t', 'not_t']:
                                if k in st.session_state:
                                    del st.session_state[k]
                                    
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
        
        tipo_form = st.radio("Selecciona el tipo de formulario a rellenar:", ["🏢 Piso Centro", "🏞️ Terreno / Ruina"], index=0 if st.session_state.get('ext_tipo') != 'Terreno' else 1, horizontal=True)
        
        if tipo_form == "🏢 Piso Centro":
            with st.form("manual_form_piso", clear_on_submit=True):
                col_fav1, col_fav2, col_vend = st.columns(3)
                with col_fav1:
                    favorito = st.checkbox("Favorito ⭐")
                with col_fav2:
                    visitado = st.checkbox("Visitado 👁️")
                with col_vend:
                    vendedor = st.selectbox("Vendedor", ["Particular", "Inmobiliaria"])
                st.divider()
                
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
                            "Caracteristicas": caracteristicas, "Notas": notas, "Imagen": "",
                            "Favorito": "Sí" if favorito else "No", "Visitado": "Sí" if visitado else "No",
                            "Vendedor": vendedor
                        }
                        if append_to_approved(new_data):
                            st.success("Piso guardado exitosamente.")
                            st.balloons()
                            for k in ['ext_titulo', 'ext_precio', 'ext_metros', 'ext_habs', 'ext_banos', 'ext_planta', 'ext_terraza', 'ext_terraza_m2', 'ext_ascensor', 'ext_garaje', 'ext_piscina', 'ext_origen', 'ext_url', 'ext_tipo']:
                                if k in st.session_state: del st.session_state[k]
                        else: st.error("❌ Error guardando.")

        elif tipo_form == "🏞️ Terreno / Ruina":
            with st.form("manual_form_terreno", clear_on_submit=True):
                col_fav1_t, col_fav2_t, col_vend_t = st.columns(3)
                with col_fav1_t:
                    favorito_t = st.checkbox("Favorito ⭐", key="fav_t")
                with col_fav2_t:
                    visitado_t = st.checkbox("Visitado 👁️", key="vis_t")
                with col_vend_t:
                    vendedor_t = st.selectbox("Vendedor", ["Particular", "Inmobiliaria"], key="vend_t")
                st.divider()
                
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
                            "Caracteristicas": caracteristicas_t, "Notas": notas_t, "Imagen": "",
                            "Favorito": "Sí" if favorito_t else "No", "Visitado": "Sí" if visitado_t else "No",
                            "Vendedor": vendedor_t
                        }
                        if append_to_approved(new_data):
                            st.success("Terreno guardado exitosamente.")
                            st.balloons()
                            for k in ['ext_titulo', 'ext_precio', 'ext_metros', 'ext_habs', 'ext_banos', 'ext_planta', 'ext_terraza', 'ext_terraza_m2', 'ext_ascensor', 'ext_garaje', 'ext_piscina', 'ext_origen', 'ext_url', 'ext_tipo']:
                                if k in st.session_state: del st.session_state[k]
                        else: st.error("❌ Error guardando. Comprueba que las credenciales de Google Sheets son correctas en los Secrets.")

    elif choice == "Base de Datos":
        st.markdown("<h1 style='color: #1e3a8a; font-weight: 800;'>📊 Análisis y base de datos</h1>", unsafe_allow_html=True)
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
                
                st.markdown("### ⚡ Datos clave")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Propiedades", len(df_mostrar))
                col2.metric("Precio Medio", f"{df_mostrar['Precio'].mean():,.0f} €".replace(',', '.'))
                col3.metric("Mediana Precio", f"{df_mostrar['Precio'].median():,.0f} €".replace(',', '.'))
                col4.metric("Precio/m² Medio", f"{df_mostrar['Precio_m2'].mean():,.0f} €/m²".replace(',', '.'))
                
                st.divider()
                st.markdown("### 📈 Gráficos")
                
                # Fila 1: Histograma y Dispersión
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    # Distribución de Precios (Histograma)
                    fig_hist = px.histogram(df_mostrar, x="Precio", nbins=20, 
                                            title="Distribución de Precios", 
                                            color_discrete_sequence=['#3b82f6'])
                    fig_hist.update_layout(bargap=0.1, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_hist, use_container_width=True)
                    
                with col_chart2:
                    # Gráfico de Dispersión (Precio vs Metros)
                    fig_scatter = px.scatter(df_mostrar, x="Metros", y="Precio", color="Ubicacion",
                                             title="Precio vs Metros (Dispersión)",
                                             hover_data=["Titulo", "Precio_m2"])
                    fig_scatter.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_scatter, use_container_width=True)
                    
                # Fila 2: Líneas temporales y Gráficos de Sectores
                col_chart3, col_chart4, col_chart5 = st.columns([2, 1.5, 1.5])
                with col_chart3:
                    # Evolución de inserciones por fecha
                    df_mostrar['Fecha'] = pd.to_datetime(df_mostrar['Fecha_Extraccion'], errors='coerce').dt.date
                    df_fechas = df_mostrar.groupby('Fecha').size().reset_index(name='Nuevas Propiedades')
                    fig_line = px.line(df_fechas, x="Fecha", y="Nuevas Propiedades", title="Evolución de Inserciones", markers=True, color_discrete_sequence=['#10b981'])
                    fig_line.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', yaxis_title="Cantidad", xaxis_title="Fecha")
                    st.plotly_chart(fig_line, use_container_width=True)
                    
                with col_chart4:
                    # Sectores: Ubicación
                    fig_pie_ubi = px.pie(df_mostrar, names="Ubicacion", title="Zonas", hole=0.4)
                    fig_pie_ubi.update_traces(textposition='inside', textinfo='percent+label')
                    fig_pie_ubi.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
                    st.plotly_chart(fig_pie_ubi, use_container_width=True)
                    
                with col_chart5:
                    # Sectores: Habitaciones (excluyendo terrenos que no tienen)
                    df_habs = df_mostrar[df_mostrar['Habitaciones'].astype(str).str.strip() != ""]
                    if not df_habs.empty:
                        fig_pie_habs = px.pie(df_habs, names="Habitaciones", title="Habitaciones", hole=0.4, color_discrete_sequence=px.colors.sequential.Teal)
                        fig_pie_habs.update_traces(textposition='inside', textinfo='percent+label')
                        fig_pie_habs.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
                        st.plotly_chart(fig_pie_habs, use_container_width=True)
                    else:
                        st.info("Sin datos de habitaciones")
                
                st.divider()
                st.markdown("### 📋 Directorio de propiedades (Editable)")
                st.info("Haz doble clic en cualquier celda para editarla. Puedes marcar 'Favorito' o 'Visitado' fácilmente. Luego pulsa en 'Guardar Cambios' para sincronizar.")
                
                # Asegurar columnas
                if 'Favorito' not in df_mostrar.columns:
                    df_mostrar['Favorito'] = "No"
                if 'Visitado' not in df_mostrar.columns:
                    df_mostrar['Visitado'] = "No"
                    
                def to_bool(val):
                    if isinstance(val, bool): return val
                    if isinstance(val, str): return val.lower() in ['sí', 'si', 'true', '1']
                    return False

                df_para_editar = df_mostrar.copy()
                df_para_editar['Favorito'] = df_para_editar['Favorito'].apply(to_bool)
                df_para_editar['Visitado'] = df_para_editar['Visitado'].apply(to_bool)
                
                # Bloquear únicamente el ID (necesario para buscar en Google Sheets)
                disabled_cols = ["ID"]
                
                df_editado = st.data_editor(
                    df_para_editar,
                    use_container_width=True, 
                    height=400,
                    disabled=disabled_cols
                )
                
                if st.button("💾 Guardar Cambios en Sheets", type="primary"):
                    with st.spinner("Sincronizando..."):
                        # Revertir a strings
                        df_final = df_editado.copy()
                        df_final['Favorito'] = df_final['Favorito'].apply(lambda x: 'Sí' if x else 'No')
                        df_final['Visitado'] = df_final['Visitado'].apply(lambda x: 'Sí' if x else 'No')
                        
                        df_original = df_mostrar.copy()
                        df_original['Favorito'] = df_original['Favorito'].apply(lambda x: 'Sí' if to_bool(x) else 'No')
                        df_original['Visitado'] = df_original['Visitado'].apply(lambda x: 'Sí' if to_bool(x) else 'No')
                        
                        cambios_realizados = 0
                        for i, row in df_final.iterrows():
                            if i in df_original.index:
                                orig_row = df_original.loc[i]
                                differ = False
                                for col in df_final.columns:
                                    if str(row[col]) != str(orig_row[col]):
                                        differ = True
                                        break
                                if differ:
                                    if update_row(row['ID'], "Approved", row.to_dict()):
                                        cambios_realizados += 1
                                        
                        if cambios_realizados > 0:
                            st.success(f"✅ ¡Se han actualizado {cambios_realizados} propiedades!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.info("No se han detectado cambios.")
                
                st.divider()
                st.markdown("### 🗑️ Eliminar Propiedad")
                with st.expander("Eliminar una propiedad manualmente de la base de datos"):
                    if not df_mostrar.empty:
                        # Crear un diccionario para mostrar nombre legible en el selectbox
                        opciones_eliminar = dict(zip(df_mostrar['ID'], df_mostrar['Titulo'] + " (" + df_mostrar['ID'] + ")"))
                        id_a_eliminar = st.selectbox("Selecciona la propiedad a eliminar", options=df_mostrar['ID'], format_func=lambda x: opciones_eliminar.get(x, x))
                        if st.button("Eliminar Seleccionada", type="primary"):
                            with st.spinner("Eliminando..."):
                                if delete_row(id_a_eliminar, "Approved"):
                                    st.success("Propiedad eliminada correctamente.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Hubo un problema al eliminar la propiedad.")
                
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
        st.markdown("<h1 style='color: #1e3a8a; font-weight: 800;'>🧮 Simulador Avanzado</h1>", unsafe_allow_html=True)
        st.markdown("Estima la viabilidad de la operación, gastos desglosados y cuotas hipotecarias.")
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
            st.markdown("### ⚙️ Parámetros de Simulación")
            
            tab1, tab2, tab3 = st.tabs(["💳 Financiación", "🏛️ Impuestos y Gastos", "🏗️ Costes Obra/Reforma"])
            
            with tab1:
                col_f1, col_f2, col_f3 = st.columns(3)
                ahorro_inicial = col_f1.number_input("Aportación inicial (Ahorros €)", min_value=0, value=30000, step=5000)
                plazo_anos = col_f2.slider("Plazo de la hipoteca (Años)", min_value=5, max_value=40, value=30, step=1)
                tipo_interes = col_f3.number_input("Tipo de Interés Anual (%)", min_value=0.0, value=2.95, step=0.1)
                
            with tab2:
                col_g1, col_g2, col_g3 = st.columns(3)
                if is_terreno:
                    porcentaje_impuesto = col_g1.number_input("IVA Terreno (%)", value=21.0, step=1.0)
                else:
                    porcentaje_impuesto = col_g1.number_input("ITP (%)", value=10.0, step=0.5, help="10% general en Com. Valenciana")
                
                notaria_base = col_g2.number_input("Coste Notaría y Registro estimado (€)", value=1200, step=100)
                gestoria_tasacion = col_g3.number_input("Gestoría y Tasación (€)", value=800, step=100)
                
            with tab3:
                col_o1, col_o2, col_o3 = st.columns(3)
                if is_terreno:
                    coste_reforma_m2 = col_o1.number_input("Coste Ejecución Material (€/m²)", value=1200, step=50)
                    honorarios_tec = col_o2.number_input("Honorarios Arquitecto/Aparejador (€)", value=18000, step=1000)
                    porcentaje_licencias = col_o3.number_input("Licencias Municipales (%)", value=4.0, step=0.5, help="Sobre el coste de ejecución")
                    iva_obra = col_o1.number_input("IVA de Construcción (%)", value=10.0, step=1.0)
                else:
                    coste_reforma_m2 = col_o1.number_input("Presupuesto de Reforma (€/m²)", value=400, step=50)
                    honorarios_tec = 0
                    porcentaje_licencias = col_o2.number_input("Licencia Obra Menor (%)", value=4.0, step=0.5)
                    iva_obra = col_o3.number_input("IVA Reforma (%)", value=10.0, step=1.0)
                    
            st.divider()
            st.markdown("### 📊 Resultados de la Comparativa")
            
            cols = st.columns(len(seleccionadas))
            
            nombres_props = []
            compra_vals = []
            impuestos_vals = []
            reforma_vals = []
            intereses_vals = []
            
            for i, sel in enumerate(seleccionadas):
                prop_data = df_filtrado[df_filtrado['Label'] == sel].iloc[0]
                
                with cols[i]:
                    st.markdown(f"#### {prop_data['Titulo']}")
                    
                    precio = float(prop_data['Precio'])
                    metros = float(prop_data['Metros'])
                    
                    # Impuestos y gastos
                    impuesto_compra = precio * (porcentaje_impuesto / 100)
                    gastos_compra = notaria_base + gestoria_tasacion
                    
                    # Obra/Reforma
                    coste_ejecucion = metros * coste_reforma_m2
                    licencias = coste_ejecucion * (porcentaje_licencias / 100)
                    iva_obra_calc = coste_ejecucion * (iva_obra / 100)
                    coste_total_obra = coste_ejecucion + licencias + iva_obra_calc + honorarios_tec
                    
                    necesidad_total = precio + impuesto_compra + gastos_compra + coste_total_obra
                    hipoteca_necesaria = necesidad_total - ahorro_inicial
                    
                    # Viabilidad (LTV sobre precio de compra)
                    ltv = (hipoteca_necesaria / precio) * 100 if precio > 0 else 0
                    
                    st.metric("Inversión Total", f"€{necesidad_total:,.0f}")
                    
                    if hipoteca_necesaria > 0:
                        r = (tipo_interes / 100) / 12
                        n = plazo_anos * 12
                        if r > 0:
                            cuota_mensual = hipoteca_necesaria * (r * (1 + r)**n) / ((1 + r)**n - 1)
                        else:
                            cuota_mensual = hipoteca_necesaria / n
                            
                        intereses_totales = (cuota_mensual * n) - hipoteca_necesaria
                        
                        st.metric("Cuota Hipoteca", f"€{cuota_mensual:,.2f} / mes")
                        
                        if ltv > 80 and not is_terreno:
                            st.warning(f"⚠️ Financiación alta (LTV {ltv:.1f}%). Te faltan ahorros para la entrada.")
                        elif ahorro_inicial < (impuesto_compra + gastos_compra):
                            st.error(f"❌ Los ahorros no cubren gastos mínimos (Faltan €{(impuesto_compra + gastos_compra - ahorro_inicial):,.0f})")
                        else:
                            st.success(f"✅ Operación Viable (LTV: {ltv:.1f}%)")
                    else:
                        st.success("✅ Pagado al contado sin hipoteca")
                        intereses_totales = 0
                        
                    with st.expander("Ver desglose detallado"):
                        st.write(f"- **Precio Inmueble:** €{precio:,.0f}")
                        st.write(f"- **Impuestos/Gastos:** €{(impuesto_compra + gastos_compra):,.0f}")
                        st.write(f"- **Reforma/Construcción:** €{coste_total_obra:,.0f}")
                        if hipoteca_necesaria > 0:
                            st.write(f"- **Intereses al Banco:** €{intereses_totales:,.0f}")
                            st.write(f"- **Capital a Financiar:** €{hipoteca_necesaria:,.0f}")
                            
                    nombres_props.append(prop_data['Titulo'][:15] + ("..." if len(prop_data['Titulo']) > 15 else ""))
                    compra_vals.append(precio)
                    impuestos_vals.append(impuesto_compra + gastos_compra)
                    reforma_vals.append(coste_total_obra)
                    intereses_vals.append(intereses_totales)

            if seleccionadas:
                st.divider()
                st.markdown("### 📈 Gráfico de Inversión Total")
                
                fig = px.bar(
                    x=nombres_props, 
                    y=[compra_vals, impuestos_vals, reforma_vals, intereses_vals],
                    labels={'x': 'Propiedad', 'y': 'Euros (€)'},
                    title="Distribución de Costes",
                    barmode="stack",
                    color_discrete_sequence=['#3b82f6', '#ef4444', '#10b981', '#f59e0b']
                )
                
                newnames = {'wide_variable_0':'Compra', 'wide_variable_1': 'Gastos e Impuestos', 'wide_variable_2': 'Construcción/Reforma', 'wide_variable_3': 'Intereses Banco'}
                fig.for_each_trace(lambda t: t.update(name = newnames.get(t.name, t.name), legendgroup = newnames.get(t.name, t.name), hovertemplate = t.hovertemplate.replace(t.name, newnames.get(t.name, t.name))))

                st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
