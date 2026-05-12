import json
import os
import argparse
import time
import random
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables (for local testing)
load_dotenv()

# --- GOOGLE SHEETS SETUP ---
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_google_sheet():
    """Conecta a Google Sheets y devuelve el objeto del documento."""
    # Intentar obtener credenciales de variable de entorno (formato JSON como string)
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    sheet_url = os.environ.get("GOOGLE_SHEET_URL")
    
    if not creds_json or not sheet_url:
        try:
            import streamlit as st
            creds_json = st.secrets.get("GOOGLE_CREDENTIALS_JSON")
            sheet_url = st.secrets.get("GOOGLE_SHEET_URL")
        except:
            pass

    if not creds_json or not sheet_url:
        print("Error: GOOGLE_CREDENTIALS_JSON o GOOGLE_SHEET_URL no están definidos.")
        try:
            import streamlit as st
            st.error("Faltan Credenciales de Google o URL en los Secretos.")
        except: pass
        return None

    try:
        if isinstance(creds_json, str):
            creds_dict = json.loads(creds_json)
        else:
            creds_dict = creds_json # Si ya es un dict de st.secrets
            
        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(credentials)
        sheet = client.open_by_url(sheet_url)
        ensure_worksheets(sheet)
        return sheet
    except Exception as e:
        print(f"Error conectando a Google Sheets: {e}")
        try:
            import streamlit as st
            st.error(f"Error al conectar con Google Sheets: {e}")
        except: pass
        return None

NEW_HEADERS = ["ID", "Tipo_Propiedad", "Fecha_Extraccion", "Origen", "URL", "Titulo", "Precio", "Ubicacion", "Metros", "Habitaciones", "Baños", "Antigüedad", "Ascensor", "Garaje", "Piscina", "Terraza", "Terraza_Metros", "Caracteristicas", "Notas", "Imagen"]

def ensure_worksheets(sheet):
    """Asegura que las pestañas necesarias existen."""
    required_sheets = ["Raw_Data", "Preselection", "Approved"]
    existing_sheets = [ws.title for ws in sheet.worksheets()]
    
    for req in required_sheets:
        if req not in existing_sheets:
            print(f"Creando pestaña: {req}")
            ws = sheet.add_worksheet(title=req, rows="1000", cols="30")
            ws.append_row(NEW_HEADERS)
        else:
            try:
                ws = sheet.worksheet(req)
                headers = ws.row_values(1)
                # Si las cabeceras son menos o diferentes, actualizamos la fila 1
                # En Preselection puede haber "Categoria_Detectada" extra, pero debe empezar por NEW_HEADERS
                if len(headers) < len(NEW_HEADERS) or headers[:len(NEW_HEADERS)] != NEW_HEADERS:
                    cell_list = ws.range(1, 1, 1, len(NEW_HEADERS))
                    for i, val in enumerate(NEW_HEADERS):
                        cell_list[i].value = val
                    ws.update_cells(cell_list)
            except Exception as e:
                print(f"Error comprobando cabeceras en {req}: {e}")

# --- SCRAPING LOGIC ---
def setup_driver():
    """Configura y devuelve una instancia de undetected-chromedriver."""
    import undetected_chromedriver as uc
    options = uc.ChromeOptions()
    # options.add_argument('--headless') # Headless a veces dispara más captchas, pero es necesario en CI
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # En GitHub actions, el path de Chrome puede variar o requerir versión específica
    # uc.Chrome se encarga de descargar el binario parchado automáticamente
    try:
        driver = uc.Chrome(options=options)
        return driver
    except Exception as e:
        print(f"Error iniciando undetected-chromedriver: {e}")
        return None

def simulate_human_behavior(driver):
    """Simula comportamiento humano para evitar bloqueos."""
    time.sleep(random.uniform(2.5, 5.5))
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
    time.sleep(random.uniform(1.0, 3.0))
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(random.uniform(1.5, 3.5))

def extract_idealista_mock(driver):
    """
    Función de extracción (Mock/Ejemplo).
    NOTA: Idealista tiene un anti-bot Datadome extremadamente agresivo.
    Para producción, se requiere proxy residencial.
    Aquí simulamos la estructura de datos extraída.
    """
    # En un escenario real:
    # driver.get("https://www.idealista.com/venta-viviendas/elche-elx-alicante/centro/")
    # simulate_human_behavior(driver)
    # html = driver.page_source
    # from bs4 import BeautifulSoup
    # soup = BeautifulSoup(html, 'html.parser')
    
    print("Simulando extracción de Idealista...")
    time.sleep(2)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Datos simulados basados en las categorías requeridas
    mock_data = [
        # Cat 1: Piso centro, 250k, 120m2, terraza
        {
            "ID": f"ID_{int(time.time())}_1", "Fecha_Extraccion": now, "Origen": "Idealista",
            "URL": "https://www.idealista.com/inmueble/mock1", "Titulo": "Piso espectacular en centro",
            "Precio": 250000, "Ubicacion": "Centro", "Metros": 120, "Habitaciones": 3,
            "Caracteristicas": "Terraza, Ascensor", "Imagen": "https://via.placeholder.com/300x200"
        },
        # Cat 2: Terreno a restaurar Raval
        {
            "ID": f"ID_{int(time.time())}_2", "Fecha_Extraccion": now, "Origen": "Idealista",
            "URL": "https://www.idealista.com/inmueble/mock2", "Titulo": "Edificio a restaurar",
            "Precio": 150000, "Ubicacion": "Raval", "Metros": 300, "Habitaciones": 0,
            "Caracteristicas": "A restaurar", "Imagen": "https://via.placeholder.com/300x200"
        },
        # Ruido: Piso en centro pero pequeño (No debe pasar filtro 1)
        {
            "ID": f"ID_{int(time.time())}_3", "Fecha_Extraccion": now, "Origen": "Fotocasa",
            "URL": "https://www.fotocasa.es/inmueble/mock3", "Titulo": "Pisito coqueto",
            "Precio": 210000, "Ubicacion": "Centro", "Metros": 70, "Habitaciones": 1,
            "Caracteristicas": "Balcón", "Imagen": "https://via.placeholder.com/300x200"
        },
        # Ruido: Piso muy caro (No debe pasar filtro 1)
        {
            "ID": f"ID_{int(time.time())}_4", "Fecha_Extraccion": now, "Origen": "Idealista",
            "URL": "https://www.idealista.com/inmueble/mock4", "Titulo": "Ático lujo",
            "Precio": 600000, "Ubicacion": "Centro", "Metros": 150, "Habitaciones": 4,
            "Caracteristicas": "Terraza enorme", "Imagen": "https://via.placeholder.com/300x200"
        }
    ]
    return mock_data

def run_scraper():
    """Ejecuta el scraping y guarda en Raw_Data."""
    print("Iniciando tarea de Scraping (20:00)...")
    sheet = get_google_sheet()
    if not sheet: return
    ensure_worksheets(sheet)
    
    # driver = setup_driver()
    # if not driver: return
    
    # data = extract_idealista_mock(driver)
    data = extract_idealista_mock(None) # Usando mock sin driver para evitar fallos locales si no hay chrome instalado
    
    if data:
        raw_ws = sheet.worksheet("Raw_Data")
        rows_to_insert = [list(d.values()) for d in data]
        raw_ws.append_rows(rows_to_insert)
        print(f"Se han insertado {len(rows_to_insert)} filas en Raw_Data.")
    
    # if driver: driver.quit()

# --- FILTERING LOGIC ---
def is_cat_1(row):
    """Centro, 200k-500k, >=100m2, terraza/balcón"""
    try:
        ubicacion = str(row['Ubicacion']).lower()
        precio = float(row['Precio'])
        metros = float(row['Metros'])
        caract = str(row['Caracteristicas']).lower()
        
        if 'centro' in ubicacion and (200000 <= precio <= 500000) and (metros >= 100) and ('terraza' in caract or 'balcón' in caract or 'balcon' in caract):
            return True
        return False
    except:
        return False

def is_cat_2(row):
    """Centro o Raval, Terreno/Edificio a restaurar"""
    try:
        ubicacion = str(row['Ubicacion']).lower()
        caract = str(row['Caracteristicas']).lower()
        titulo = str(row['Titulo']).lower()
        
        texto_analizar = caract + " " + titulo
        
        if ('centro' in ubicacion or 'raval' in ubicacion) and ('terreno' in texto_analizar or 'restaurar' in texto_analizar or 'reformar' in texto_analizar):
            return True
        return False
    except:
        return False

def run_filter():
    """Lee de Raw_Data, filtra y mueve a Preselection. Limpia Raw_Data."""
    print("Iniciando tarea de Filtrado (07:00)...")
    sheet = get_google_sheet()
    if not sheet: return
    ensure_worksheets(sheet)
    
    raw_ws = sheet.worksheet("Raw_Data")
    pre_ws = sheet.worksheet("Preselection")
    
    raw_data = raw_ws.get_all_records()
    if not raw_data:
        print("No hay datos en Raw_Data para filtrar.")
        return
        
    df = pd.DataFrame(raw_data)
    
    # Aplicar filtros
    cat1_mask = df.apply(is_cat_1, axis=1)
    cat2_mask = df.apply(is_cat_2, axis=1)
    
    filtered_df = df[cat1_mask | cat2_mask].copy()
    
    # Añadir columna de categoría detectada
    def assign_cat(row):
        if is_cat_1(row): return "Cat 1: Piso Centro"
        if is_cat_2(row): return "Cat 2: A Restaurar"
        return "Unknown"
        
    if not filtered_df.empty:
        filtered_df['Categoria_Detectada'] = filtered_df.apply(assign_cat, axis=1)
        # Preparar para insertar (asegurar orden de columnas)
        # Asumiendo que Preselection tiene una columna extra 'Categoria_Detectada' al final
        headers_pre = pre_ws.row_values(1)
        if "Categoria_Detectada" not in headers_pre:
            pre_ws.update_cell(1, len(headers_pre) + 1, "Categoria_Detectada")
            headers_pre.append("Categoria_Detectada")
        
        # Insertar en Preselection
        rows_to_insert = filtered_df[headers_pre].values.tolist()
        pre_ws.append_rows(rows_to_insert)
        print(f"Se han movido {len(rows_to_insert)} propiedades a Preselection.")
    else:
        print("Ninguna propiedad pasó los filtros hoy.")
        
    # Limpiar Raw_Data (manteniendo encabezados)
    # Gspread no tiene un "clear_contents" excepto por rangos, mejor limpiar todo y reescribir encabezados
    headers_raw = list(df.columns)
    raw_ws.clear()
    raw_ws.append_row(headers_raw)
    print("Raw_Data limpiada.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script de Scraping y Filtrado Inmobiliario")
    parser.add_argument("--scrape", action="store_true", help="Ejecuta la extracción (20:00)")
    parser.add_argument("--filter", action="store_true", help="Ejecuta el filtrado (07:00)")
    
    args = parser.parse_args()
    
    if args.scrape:
        run_scraper()
    elif args.filter:
        run_filter()
    else:
        print("Por favor especifica --scrape o --filter")
