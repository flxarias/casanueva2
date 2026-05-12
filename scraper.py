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
import uuid

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

NEW_HEADERS = ["ID", "Tipo_Propiedad", "Fecha_Extraccion", "Origen", "URL", "Titulo", "Precio", "Ubicacion", "Metros", "Habitaciones", "Baños", "Planta", "Antigüedad", "Ascensor", "Garaje", "Piscina", "Terraza", "Terraza_Metros", "Caracteristicas", "Notas", "Imagen"]

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
import requests
from bs4 import BeautifulSoup
import re

def parse_property_data(url, title, clean_text, domain, price_override=0):
    """Lógica genérica de extracción basada en Regex (similar a app.py)"""
    metros = 0
    metros_match = re.search(r'(\d{2,4})\s*(?:m2|m²|metros)', clean_text, re.IGNORECASE)
    if metros_match: metros = int(metros_match.group(1))

    habs = 0
    habs_match = re.search(r'(\d+)\s*(?:hab|dormitorio|habitacion)', clean_text, re.IGNORECASE)
    if habs_match: habs = int(habs_match.group(1))

    banos = 0
    banos_match = re.search(r'(\d+)\s*(?:baño|aseo)', clean_text, re.IGNORECASE)
    if banos_match: banos = int(banos_match.group(1))
    
    planta = ""
    planta_match = re.search(r'((?:Bajo|Entresuelo|Ático|Atico|\d{1,2}ª|\d{1,2}º)\s*planta|Bajo|Entresuelo|Ático|Atico)', clean_text, re.IGNORECASE)
    if planta_match: planta = planta_match.group(1).capitalize()

    tiene_ascensor = "Sí" if re.search(r'\bAscensor\b', clean_text, re.IGNORECASE) else "No"
    tiene_garaje = "Sí" if re.search(r'\b(?:Garaje|Parking|Aparcamiento)\b', clean_text, re.IGNORECASE) else "No"
    tiene_piscina = "Sí" if re.search(r'\bPiscina\b', clean_text, re.IGNORECASE) else "No"
    
    terraza_m2 = 0
    terraza_match = re.search(r'Terraza[^\d]*(\d{1,3})\s*m', clean_text, re.IGNORECASE)
    if terraza_match: terraza_m2 = int(terraza_match.group(1))
    tiene_terraza = "Sí" if terraza_m2 > 0 or re.search(r'\bTerraza\b', clean_text, re.IGNORECASE) else "No"

    tipo_prop = "Piso"
    if re.search(r'\b(?:Terreno|Parcela|Solar|Ruina|Finca|Chalet)\b', title + " " + clean_text, re.IGNORECASE):
        tipo_prop = "Terreno"

    precio_est = price_override
    if precio_est == 0:
        precio_match = re.search(r'Precio\s*[:\n]\s*(\d{1,3}[\.,]?\d{3})', clean_text, re.IGNORECASE)
        if precio_match:
            try: precio_est = int(precio_match.group(1).replace('.', '').replace(',', ''))
            except: pass
        else:
            precios = re.findall(r'(\d{2,3}[\.,]?\d{3})\s*[€|euros]', clean_text, re.IGNORECASE)
            if precios:
                try: precio_est = int(precios[0].replace('.', '').replace(',', ''))
                except: pass

    if "|" in title: title = title.split("|")[0].strip()

    return {
        "ID": f"AUT_{uuid.uuid4().hex[:8]}",
        "Tipo_Propiedad": tipo_prop,
        "Fecha_Extraccion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Origen": domain,
        "URL": url,
        "Titulo": title.strip()[:100],
        "Precio": precio_est,
        "Ubicacion": "Desconocida", # Se actualizará por IA o revisión manual
        "Metros": metros,
        "Habitaciones": habs if habs > 0 else "",
        "Baños": banos if banos > 0 else "",
        "Planta": planta,
        "Antigüedad": "",
        "Ascensor": tiene_ascensor,
        "Garaje": tiene_garaje,
        "Piscina": tiene_piscina,
        "Terraza": tiene_terraza,
        "Terraza_Metros": terraza_m2 if terraza_m2 > 0 else "",
        "Caracteristicas": "",
        "Notas": "Extraído automáticamente",
        "Imagen": ""
    }

def scrape_pisos_com():
    print("Iniciando scraping de pisos.com...")
    properties = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        url = "https://www.pisos.com/venta/pisos-elche_elx/"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # En pisos.com los anuncios suelen estar en divs con clases específicas, pero podemos buscar enlaces
            links = soup.find_all('a', href=re.compile(r'/comprar/.*-elche.*'))
            seen = set()
            for a in links[:15]: # Limitar a los primeros 15 para no saturar
                href = "https://www.pisos.com" + a['href']
                if href in seen: continue
                seen.add(href)
                
                # Para ser rápidos, extraemos texto del contenedor padre si existe, si no, lo dejamos básico
                parent = a.parent.parent
                clean_text = parent.get_text(separator=' ') if parent else a.get_text()
                title = a.get_text(strip=True)
                
                prop_data = parse_property_data(href, title, clean_text, "Pisos.com")
                if prop_data['Precio'] > 0: # Solo si encontró precio válido
                    properties.append(prop_data)
    except Exception as e:
        print(f"Error en pisos.com: {e}")
    return properties

def scrape_agencias_locales():
    print("Iniciando scraping de agencias locales (Inmovilla/Genéricas)...")
    properties = []
    # Lista de búsquedas de agencias locales
    urls = [
        "https://www.varaderoinmobiliaria.com/inmuebles/elche/venta/",
        "https://www.inmobiliariabh.com/propiedades/elche/venta/",
        "https://www.mmelche.com/inmuebles/elche/venta/"
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for url in urls:
        try:
            domain = url.split("//")[1].split("/")[0].replace("www.", "")
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                links = soup.find_all('a', href=re.compile(r'.*cod=\d+.*'))
                seen = set()
                for a in links[:5]: # 5 propiedades por agencia
                    href = a['href']
                    if not href.startswith("http"):
                        href = f"https://{domain}{href}" if href.startswith("/") else f"https://{domain}/{href}"
                    
                    if href in seen: continue
                    seen.add(href)
                    
                    # Para sacar datos precisos, entramos a la ficha
                    try:
                        ficha_res = requests.get(href, headers=headers, timeout=5)
                        if ficha_res.status_code == 200:
                            f_soup = BeautifulSoup(ficha_res.text, 'html.parser')
                            clean_text = f_soup.get_text(separator=' ')
                            title = f_soup.title.string if f_soup.title else "Propiedad"
                            prop_data = parse_property_data(href, title, clean_text, domain.capitalize())
                            if prop_data['Precio'] > 0:
                                properties.append(prop_data)
                    except: pass
        except Exception as e:
            print(f"Error en {url}: {e}")
    return properties

def run_scraper():
    """Ejecuta el scraping automatizado y guarda en Raw_Data."""
    print("Iniciando tarea de Scraping Diario...")
    sheet = get_google_sheet()
    if not sheet: return
    ensure_worksheets(sheet)
    
    data = []
    data.extend(scrape_pisos_com())
    data.extend(scrape_agencias_locales())
    
    if data:
        raw_ws = sheet.worksheet("Raw_Data")
        
        # Asegurarnos de que tienen exactamente los headers de NEW_HEADERS
        rows_to_insert = []
        for d in data:
            row = [d.get(h, "") for h in NEW_HEADERS]
            rows_to_insert.append(row)
            
        raw_ws.append_rows(rows_to_insert)
        print(f"Se han insertado {len(rows_to_insert)} filas en Raw_Data.")
    else:
        print("No se extrajeron datos hoy.")

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
