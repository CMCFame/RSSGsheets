def create_headers(service, spreadsheet_id):
    """Create headers if they don't exist"""
    try:
        # Añadir más logging para debug
        st.write("Intentando acceder a la hoja...")
        st.write(f"Spreadsheet ID: {spreadsheet_id}")
        
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
    except HttpError as e:
        st.error(f"Error HTTP: {str(e.error_details)}")
        return False
    except Exception as e:
        st.error(f"Error inesperado: {str(e)}")
        return False
    return True

def get_sheet_service():
    """Initialize Google Sheets API service"""
    try:
        st.write("Verificando configuración de credenciales...")
        
        # Intentar acceder a los secrets para verificar que están configurados
        if "google_credentials" not in st.secrets:
            st.error("No se encontró la sección 'google_credentials' en los secrets")
            return None
            
        required_fields = ["project_id", "private_key_id", "private_key", 
                          "client_email", "client_id", "client_x509_cert_url"]
        
        missing_fields = [field for field in required_fields 
                         if field not in st.secrets.google_credentials]
        
        if missing_fields:
            st.error(f"Faltan los siguientes campos en los secrets: {', '.join(missing_fields)}")
            return None

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
        
        st.write("Credenciales configuradas correctamente")
        
        creds = Credentials.from_service_account_info(
            credentials,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        
        st.write("Credenciales creadas, intentando construir el servicio...")
        
        service = build('sheets', 'v4', credentials=creds)
        st.write("Servicio construido exitosamente")
        
        return service
        
    except Exception as e:
        st.error(f"Error al configurar el servicio: {str(e)}")
        return None