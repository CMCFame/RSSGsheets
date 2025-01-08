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

# Constantes
MAX_ENTRIES_PER_FEED = 5  # Límite de entradas por feed

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
    """Limpia el HTML del texto manteniendo el formato básico"""
    if not text:
        return ""
    
    # Reemplazar algunos elementos HTML comunes con formato legible
    text = text.replace('</p>', '\n')
    text = text.replace('<br>', '\n')
    text = text.replace('<br/>', '\n')
    text = text.replace('<br />', '\n')
    
    # Eliminar cualquier otro tag HTML
    text = re.sub(r'<[^>]+>', '', text)
    
    # Limpiar espacios múltiples y líneas en blanco
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    
    # Limpiar espacios al inicio y final
    text = text.strip()
    
    return text

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
        if "google_credentials" not in st.secrets:
            st.error("No se encontró la sección 'google_credentials' en los secrets")
            return None

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

def get_content_or_summary(entry):
    """Obtiene el contenido más completo disponible del entry"""
    # Intentar obtener el contenido completo primero
    if 'content' in entry and entry.content:
        content = entry.content[0].value if isinstance(entry.content, list) else entry.content
        return clean_html(content)
    
    # Si no hay contenido, intentar con el resumen
    if 'summary' in entry:
        return clean_html(entry.get('summary', ''))
    
    # Si no hay resumen, intentar con la descripción
    if 'description' in entry:
        return clean_html(entry.get('description', ''))
    
    return 'No hay descripción disponible'

def batch_update_sheet(service, spreadsheet_id, values_to_append):
    """Actualiza la hoja en lotes para reducir llamadas a la API"""
    if not values_to_append:
        return True
        
    try:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='Noticias!A:E',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': values_to_append}
        ).execute()
        time.sleep(2)  # Pausa para respetar límites de la API
        return True
    except HttpError as e:
        st.error(f"Error al actualizar la hoja: {str(e.error_details)}")
        return False
    except Exception as e:
        st.error(f"Error inesperado: {str(e)}")
        return False

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
            st.stop()

        # Crear barra de progreso
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Inicializar cache y variables
        cache = URLCache()
        total_new_entries = 0
        total_feeds = len(selected_feeds)
        batch_size = 10  # Número de entradas por lote
        current_batch = []
        
        for idx, (source, feed_url) in enumerate(selected_feeds.items()):
            status_text.text(f"Procesando {source}...")
            try:
                feed = feedparser.parse(feed_url)
                entries_processed = 0  # Contador para este feed
                
                # Tomar solo las primeras MAX_ENTRIES_PER_FEED entradas
                for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
                    link = extract_url(entry.get('link', '#'))
                    if '?' in link:
                        link = link.split('?')[0]
                    
                    if cache.is_new_url(link, source):
                        # Obtener el contenido más completo disponible
                        content = get_content_or_summary(entry)
                        
                        current_batch.append([
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            source,
                            entry.get('title', 'Sin título'),
                            link,
                            content
                        ])
                        total_new_entries += 1
                        entries_processed += 1
                        
                        # Si alcanzamos el tamaño del lote, actualizamos la hoja
                        if len(current_batch) >= batch_size:
                            if not batch_update_sheet(service, spreadsheet_id, current_batch):
                                st.error("Error al actualizar el lote. Deteniendo el proceso.")
                                st.stop()
                            current_batch = []
                            time.sleep(1)  # Pausa adicional entre lotes
                
                st.write(f"Procesadas {entries_processed} entradas nuevas de {source}")
                time.sleep(0.5)  # Pausa entre fuentes
                
            except Exception as e:
                st.warning(f"Error procesando {source}: {str(e)}")
            
            # Actualizar barra de progreso
            progress_bar.progress((idx + 1) / total_feeds)
        
        # Actualizar cualquier entrada restante
        if current_batch:
            if not batch_update_sheet(service, spreadsheet_id, current_batch):
                st.error("Error al actualizar el último lote.")
                st.stop()
        
        # Mostrar resultados
        progress_bar.empty()
        status_text.empty()
        st.success(f'¡Proceso completado! Se añadieron {total_new_entries} nuevas entradas.')
        
    except Exception as e:
        st.error(f'Error: {str(e)}')

# Instrucciones
with st.expander("Ver instrucciones"):
    st.markdown(f"""
    ### Cómo usar esta aplicación:
    
    1. Verifica el ID de la hoja de Google Sheets en la barra lateral
    2. Selecciona las fuentes que quieres procesar
    3. Haz clic en 'Recolectar Noticias'
    
    La aplicación recolectará las {MAX_ENTRIES_PER_FEED} noticias más recientes de cada fuente seleccionada.
    
    ### Columnas en la hoja:
    - Fecha
    - Fuente
    - Título
    - URL
    - Resumen/Contenido completo
    """)