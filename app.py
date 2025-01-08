import streamlit as st
import feedparser
import time
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import hashlib
import re

# Configuración de la página
st.set_page_config(
    page_title="RSS Gaming News Collector",
    page_icon="🎮",
    layout="wide"
)

# Lista de feeds
GAMING_FEEDS = {
    "Destructoid": "https://www.destructoid.com/feed/",
    "Xbox Wire": "https://news.xbox.com/en-us/feed/",
    "Escapist Magazine": "https://www.escapistmagazine.com/feed/",
    "Kotaku": "https://kotaku.com/rss",
    "VG247": "https://www.vg247.com/feed/news",
    "Touch Arcade": "https://toucharcade.com/feed/",
    "GameSpot": "https://www.gamespot.com/feeds/mashup/",
    "IGN": "http://feeds.feedburner.com/ign/news",
    "Polygon": "https://www.polygon.com/rss/index.xml",
    "DualShockers": "https://www.dualshockers.com/feed/",
    "Gematsu": "https://www.gematsu.com/feed",
    "PC Gamer": "https://www.pcgamer.com/rss/",
    "Eurogamer": "https://www.eurogamer.net/feed",
    "Twinfinite": "https://twinfinite.net/feed/",
    "Push Square": "https://www.pushsquare.com/feeds/latest",
    "Pocket Gamer": "https://pocket4957.rssing.com/chan-78169779/index-latest.php",
    "Siliconera": "https://www.siliconera.com/feed/",
    "Nintendo Everything": "https://nintendoeverything.com/feed/",
    "VGC": "https://www.videogameschronicle.com/category/news/feed/"
}

@st.cache_resource
class URLCache:
    def __init__(self):
        self.cache = {}

    def is_new_url(self, url, source):
        url_hash = hashlib.md5(url.encode()).hexdigest()
        
        if source not in self.cache:
            self.cache[source] = []
            
        if url_hash not in self.cache[source]:
            self.cache[source].append(url_hash)
            return True
        return False

def clean_html(text):
    """Limpia el HTML del texto"""
    text = re.sub(r'<img[^>]+>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_url(link):
    """Extracts URL from different link formats"""
    if isinstance(link, str):
        return link
    elif isinstance(link, list) and link:
        return extract_url(link[0])
    elif isinstance(link, dict):
        return link.get('href', '#')
    return '#'

def get_sheet_service():
    """Initialize Google Sheets API service"""
    try:
        # Crear el diccionario de credenciales usando los secrets
        credentials = {
            "type": "service_account",
            "project_id": st.secrets["google_credentials"]["project_id"],
            "private_key_id": st.secrets["google_credentials"]["private_key_id"],
            "private_key": st.secrets["google_credentials"]["private_key"],
            "client_email": st.secrets["google_credentials"]["client_email"],
            "client_id": st.secrets["google_credentials"]["client_id"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": st.secrets["google_credentials"]["client_x509_cert_url"]
        }
        
        creds = Credentials.from_service_account_info(
            credentials,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return build('sheets', 'v4', credentials=creds)
    except Exception as e:
        st.error(f"Error al configurar el servicio: {str(e)}")
        return None

def create_headers(service, spreadsheet_id):
    """Create headers if they don't exist"""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range='Noticias!A:E'
        ).execute()
        
        if 'values' not in result or not result['values']:
            headers = [['Fecha', 'Fuente', 'Título', 'URL', 'Resumen']]
            body = {'values': headers}
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='Noticias!A:E',
                valueInputOption='RAW',
                body=body
            ).execute()
            return True
    except HttpError:
        return False
    return True

# Interfaz de Streamlit
st.title('🎮 RSS Gaming News Collector')

# Sidebar para configuración
st.sidebar.header('Configuración')

spreadsheet_id = st.sidebar.text_input('ID de Google Spreadsheet', '1yIKuqRs9KlqMdqhPEbTpfoIwMNSWaNomRVUuFOsrokU')

# Selección de fuentes
st.sidebar.header('Fuentes')
selected_feeds = {}
for source, url in GAMING_FEEDS.items():
    if st.sidebar.checkbox(source, value=True):
        selected_feeds[source] = url

if st.button('Recolectar Noticias'):
    try:
        service = get_sheet_service()
        if service is None:
            st.error('Error al inicializar el servicio de Google Sheets.')
            st.error('Verifica que los secrets estén configurados correctamente.')
            st.stop()
        
        # Verificar acceso y crear headers
        if not create_headers(service, spreadsheet_id):
            st.error('Error al acceder a la hoja de cálculo. Verifica el ID y los permisos.')
            st.stop()
        
        # Crear barra de progreso
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Inicializar cache
        cache = URLCache()
        total_new_entries = 0
        total_feeds = len(selected_feeds)
        
        for idx, (source, feed_url) in enumerate(selected_feeds.items()):
            status_text.text(f"Procesando {source}...")
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries:
                    link = extract_url(entry.get('link', '#'))
                    if '?' in link:
                        link = link.split('?')[0]
                    
                    if cache.is_new_url(link, source):
                        summary = clean_html(entry.get('summary', ''))
                        if len(summary) > 300:
                            summary = summary[:297] + "..."
                        
                        values = [[
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            source,
                            entry.get('title', 'Sin título'),
                            link,
                            summary
                        ]]
                        
                        service.spreadsheets().values().append(
                            spreadsheetId=spreadsheet_id,
                            range='Noticias!A:E',
                            valueInputOption='RAW',
                            insertDataOption='INSERT_ROWS',
                            body={'values': values}
                        ).execute()
                        
                        total_new_entries += 1
                        
                        # Pequeña pausa
                        time.sleep(0.5)
                
            except Exception as e:
                st.warning(f"Error procesando {source}: {str(e)}")
            
            # Actualizar barra de progreso
            progress_bar.progress((idx + 1) / total_feeds)
        
        # Mostrar resultados
        progress_bar.empty()
        status_text.empty()
        st.success(f'¡Proceso completado! Se añadieron {total_new_entries} nuevas entradas.')
        
    except Exception as e:
        st.error(f'Error: {str(e)}')

# Instrucciones
with st.expander("Ver instrucciones"):
    st.markdown("""
    ### Cómo usar esta aplicación:
    
    1. Verifica el ID de la hoja de Google Sheets en la barra lateral
    
    2. Selecciona las fuentes que quieres procesar
    
    3. Haz clic en 'Recolectar Noticias'
    
    La aplicación recolectará las noticias y las añadirá a tu hoja de Google Sheets automáticamente.
    """)