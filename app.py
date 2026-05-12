import streamlit as st
import pandas as pd
import plotly.express as px
import time
import uuid
import os
from scraper import get_google_sheet, ensure_worksheets
from datetime import datetime

st.set_page_config(page_title="Gestor Inmobiliario Elche", page_icon="🏠", layout="wide")

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
            headers = ["ID", "Fecha_Extraccion", "Origen", "URL", "Titulo", "Precio", "Ubicacion", "Metros", "Habitaciones", "Baños", "Antigüedad", "Ascensor", "Terraza", "Terraza_Metros", "Caracteristicas", "Notas", "Imagen"]
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
    st.sidebar.title("🏠 Menú Inmobiliario")
    menu = ["Validación Diaria", "Entrada Manual", "Base de Datos y Análisis", "Simulador y Comparador"]
    choice = st.sidebar.radio("Navegación", menu)
    
    # Comprobar conexión DB al inicio
    if not os.environ.get("GOOGLE_CREDENTIALS_JSON"):
         st.sidebar.error("Faltan Credenciales de Google (Secretos)")

    if choice == "Validación Diaria":
        st.title("✅ Validación Diaria (07:00)")
        st.write("Propiedades preseleccionadas por el sistema automático.")
        
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
        st.title("✍️ Entrada Manual y Semiautomática")
        
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
                            
                            # Extraer texto limpio
                            text_lines = soup.get_text(separator='\n').split('\n')
                            clean_text = '\n'.join([line.strip() for line in text_lines if line.strip()])
                            
                            # Habitaciones
                            habs_match = re.search(r'(?:Habitaciones|Dormitorios)\s*[:\n]\s*(\d+)', clean_text, re.IGNORECASE)
                            if not habs_match:
                                habs_match = re.search(r'(\d+)\s*(?:Habitaciones|Dormitorios)', clean_text, re.IGNORECASE)
                            habs = int(habs_match.group(1)) if habs_match else 0
                            
                            # Baños
                            banos_match = re.search(r'Baños\s*[:\n]\s*(\d+)', clean_text, re.IGNORECASE)
                            if not banos_match:
                                banos_match = re.search(r'(\d+)\s*Baños', clean_text, re.IGNORECASE)
                            banos = int(banos_match.group(1)) if banos_match else 0

                            # Metros
                            metros_match = re.search(r'(?:Útiles|Construidos|Superficie)\s*[:\n]\s*(\d+)', clean_text, re.IGNORECASE)
                            if not metros_match:
                                metros_match = re.search(r'(\d+)\s*m[2²]', clean_text, re.IGNORECASE)
                            metros = int(metros_match.group(1)) if metros_match else 0
                            
                            # Terraza
                            terraza_match = re.search(r'Terraza\s*[:\n]\s*(\d+)', clean_text, re.IGNORECASE)
                            terraza_m2 = int(terraza_match.group(1)) if terraza_match else 0
                            tiene_terraza = True if terraza_m2 > 0 or re.search(r'\bTerraza\b', clean_text, re.IGNORECASE) else False

                            # Ascensor
                            tiene_ascensor = bool(re.search(r'\bAscensor\b', clean_text, re.IGNORECASE))
                            
                            # Precio
                            precio_est = 0
                            precio_match = re.search(r'Precio\s*[:\n]\s*(\d{1,3}[\.,]?\d{3})', clean_text, re.IGNORECASE)
                            if precio_match:
                                try: precio_est = int(precio_match.group(1).replace('.', '').replace(',', ''))
                                except: pass
                            else:
                                precios = re.findall(r'(\d{2,3}[\.,]?\d{3})\s*[€|euros]', clean_text, re.IGNORECASE)
                                if precios:
                                    try: precio_est = int(precios[0].replace('.', '').replace(',', ''))
                                    except: pass
                                    
                            # Título limpio
                            if "|" in title: title = title.split("|")[0].strip()
                                    
                            st.session_state['ext_titulo'] = title.strip()[:100]
                            st.session_state['ext_precio'] = precio_est
                            st.session_state['ext_metros'] = metros
                            st.session_state['ext_habs'] = habs
                            st.session_state['ext_banos'] = banos
                            st.session_state['ext_terraza'] = tiene_terraza
                            st.session_state['ext_terraza_m2'] = terraza_m2
                            st.session_state['ext_ascensor'] = tiene_ascensor
                            st.session_state['ext_origen'] = domain
                            st.session_state['ext_url'] = url_input
                            st.success("✅ Datos extraídos. Por favor, revisa el formulario abajo.")
                        else:
                            st.warning(f"⚠️ El servidor devolvió el código {res.status_code}")
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")
            
        st.divider()
        st.subheader("Formulario Manual")
        
        with st.form("manual_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                titulo = st.text_input("Título del Anuncio *", value=st.session_state.get('ext_titulo', ''))
                precio = st.number_input("Precio (€) *", min_value=0, step=1000, value=st.session_state.get('ext_precio', 0))
                metros = st.number_input("Metros Cuadrados *", min_value=0, step=5, value=st.session_state.get('ext_metros', 0))
                habitaciones = st.number_input("Habitaciones", min_value=0, step=1, value=st.session_state.get('ext_habs', 0))
                banos = st.number_input("Baños", min_value=0, step=1, value=st.session_state.get('ext_banos', 0))
            with col2:
                antiguedad = st.number_input("Antigüedad (Año)", min_value=1800, max_value=2030, step=1, value=0, help="0 si es desconocido")
                ubicacion = st.selectbox("Ubicación", ["Centro", "Raval", "Altabix", "Carrús", "Sector 5", "Otro"])
                
                # Autodetect origen logic
                origen_opts = ["Idealista", "Fotocasa", "Agencia Local", "Offline", "Otro"]
                default_origen = st.session_state.get('ext_origen', '')
                if default_origen and default_origen not in origen_opts:
                    origen_opts.insert(0, default_origen)
                    origen_idx = 0
                else:
                    origen_idx = origen_opts.index(default_origen) if default_origen in origen_opts else 2
                origen = st.selectbox("Origen", origen_opts, index=origen_idx)
                
                url = st.text_input("URL del Anuncio", value=st.session_state.get('ext_url', ''))
            with col3:
                ascensor = st.checkbox("Tiene Ascensor", value=st.session_state.get('ext_ascensor', False))
                terraza = st.checkbox("Tiene Terraza/Balcón", value=st.session_state.get('ext_terraza', False))
                terraza_m2 = st.number_input("Metros de Terraza", min_value=0, step=1, value=st.session_state.get('ext_terraza_m2', 0))
                caracteristicas = st.text_area("Otras Características (ej. Garaje, Piscina)")
                notas = st.text_area("Notas / Valoración cualitativa")
            
            submit = st.form_submit_button("Guardar Propiedad")
            
            if submit:
                if not titulo or precio == 0 or metros == 0:
                    st.error("Por favor, rellena los campos obligatorios (*)")
                else:
                    new_data = {
                        "ID": f"MAN_{uuid.uuid4().hex[:8]}",
                        "Fecha_Extraccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Origen": origen,
                        "URL": url,
                        "Titulo": titulo,
                        "Precio": precio,
                        "Ubicacion": ubicacion,
                        "Metros": metros,
                        "Habitaciones": habitaciones,
                        "Baños": banos,
                        "Antigüedad": antiguedad if antiguedad > 0 else "",
                        "Ascensor": "Sí" if ascensor else "No",
                        "Terraza": "Sí" if terraza else "No",
                        "Terraza_Metros": terraza_m2 if terraza_m2 > 0 else "",
                        "Caracteristicas": caracteristicas,
                        "Notas": notas,
                        "Imagen": ""
                    }
                    if append_to_approved(new_data):
                        st.success("Propiedad guardada exitosamente en la base de datos.")
                        st.balloons()
                        # Limpiar variables de sesion
                        for k in ['ext_titulo', 'ext_precio', 'ext_metros', 'ext_habs', 'ext_banos', 'ext_terraza', 'ext_terraza_m2', 'ext_ascensor', 'ext_origen', 'ext_url']:
                            if k in st.session_state: del st.session_state[k]
                    else:
                        st.error("❌ No se pudo guardar la propiedad. Comprueba que las credenciales de Google Sheets son correctas en los Secrets.")

    elif choice == "Base de Datos y Análisis":
        st.title("📊 Base de Datos y Análisis")
        
        df_app = load_data("Approved")
        
        if df_app.empty:
            st.info("La base de datos está vacía. Aprueba propiedades o añádelas manualmente.")
        else:
            # Asegurar tipos numéricos para cálculos
            df_app['Precio'] = pd.to_numeric(df_app['Precio'], errors='coerce')
            df_app['Metros'] = pd.to_numeric(df_app['Metros'], errors='coerce')
            df_app['Precio_m2'] = df_app['Precio'] / df_app['Metros']
            
            st.subheader("Métricas Clave")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Propiedades", len(df_app))
            col2.metric("Precio Medio", f"€{df_app['Precio'].mean():,.2f}")
            col3.metric("Precio Medio / m²", f"€{df_app['Precio_m2'].mean():,.2f}")
            
            st.subheader("Tabla de Datos")
            st.dataframe(df_app, use_container_width=True)
            
            # Botón de descarga
            csv = df_app.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar datos como CSV",
                data=csv,
                file_name='propiedades_elche.csv',
                mime='text/csv',
            )
            
            # Enlace a Google Sheets
            sheet_url = os.environ.get("GOOGLE_SHEET_URL", "#")
            st.markdown(f"[🔗 Abrir en Google Sheets]({sheet_url})")
            
            st.divider()
            st.subheader("Dashboard Analítico")
            
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                # Distribución por ubicación
                fig_pie = px.pie(df_app, names='Ubicacion', title='Propiedades por Ubicación', hole=0.3)
                st.plotly_chart(fig_pie, use_container_width=True)
                
            with col_chart2:
                # Dispersión Precio vs Superficie
                fig_scatter = px.scatter(df_app, x='Metros', y='Precio', color='Ubicacion', 
                                         hover_data=['Titulo'], title='Precio vs Superficie')
                st.plotly_chart(fig_scatter, use_container_width=True)

    elif choice == "Simulador y Comparador":
        st.title("🧮 Simulador y Comparador")
        
        df_app = load_data("Approved")
        
        if df_app.empty:
            st.warning("Necesitas propiedades en la base de datos para comparar.")
            return
            
        # Opciones para comparar
        opciones = df_app['Titulo'] + " (" + df_app['Ubicacion'] + ") - €" + df_app['Precio'].astype(str)
        df_app['Label'] = opciones
        
        seleccionadas = st.multiselect("Selecciona hasta 3 propiedades para comparar", df_app['Label'].tolist(), max_selections=3)
        
        if seleccionadas:
            st.subheader("Parámetros de Simulación")
            col_params1, col_params2, col_params3 = st.columns(3)
            with col_params1:
                porcentaje_itp = st.number_input("ITP (%)", value=10.0, step=0.5, help="Impuesto de Transmisiones Patrimoniales (CV es 10%)")
            with col_params2:
                porcentaje_notaria = st.number_input("Notaría/Registro/Gestoría (%)", value=1.5, step=0.1)
            with col_params3:
                coste_reforma_m2 = st.number_input("Coste Reforma Estimado (€/m²)", value=400, step=50)
                
            st.divider()
            st.subheader("Comparativa")
            
            cols = st.columns(len(seleccionadas))
            
            for i, sel in enumerate(seleccionadas):
                prop_data = df_app[df_app['Label'] == sel].iloc[0]
                
                with cols[i]:
                    st.markdown(f"### Propiedad {i+1}")
                    st.markdown(f"**{prop_data['Titulo']}**")
                    
                    precio = float(prop_data['Precio'])
                    metros = float(prop_data['Metros'])
                    
                    itp_calc = precio * (porcentaje_itp / 100)
                    notaria_calc = precio * (porcentaje_notaria / 100)
                    reforma_calc = metros * coste_reforma_m2
                    total = precio + itp_calc + notaria_calc + reforma_calc
                    
                    st.write(f"- **Precio Compra:** €{precio:,.2f}")
                    st.write(f"- **Impuestos (ITP):** €{itp_calc:,.2f}")
                    st.write(f"- **Gastos Notaría:** €{notaria_calc:,.2f}")
                    st.write(f"- **Reforma Estimada:** €{reforma_calc:,.2f}")
                    st.markdown("---")
                    st.markdown(f"#### **Total Estimado:** €{total:,.2f}")

if __name__ == "__main__":
    main()
