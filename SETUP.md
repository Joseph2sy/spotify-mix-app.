# Spotify Auto-Mix DJ — Despliegue en Streamlit Cloud

## 1. Archivos del proyecto
- `app.py` — aplicación completa (auth intacta + motor DJ nuevo)
- `requirements.txt`
- `secrets.toml.example` → renómbralo/copia su contenido a `.streamlit/secrets.toml`

## 2. Spotify Developer Dashboard
1. Ve a https://developer.spotify.com/dashboard y abre (o crea) tu app.
2. En "Redirect URIs" agrega exactamente la URL pública de tu app de
   Streamlit Cloud, por ejemplo: `https://tu-app.streamlit.app`
   (debe coincidir carácter por carácter con `SPOTIPY_REDIRECT_URI`).
3. Copia el `Client ID` y `Client Secret`.

## 3. Configurar Secrets en Streamlit Cloud
En tu app dentro de Streamlit Cloud → **Settings → Secrets**, pega:

```toml
SPOTIPY_CLIENT_ID = "..."
SPOTIPY_CLIENT_SECRET = "..."
SPOTIPY_REDIRECT_URI = "https://tu-app.streamlit.app"

# Opcional — la app funciona sin esto:
OPENAI_API_KEY = "..."
```

## 4. Despliegue
1. Sube `app.py` y `requirements.txt` a tu repositorio (GitHub/GitLab).
2. En Streamlit Cloud: "New app" → selecciona el repo → archivo principal
   `app.py`.
3. Deploy. La primera carga puede tardar unos segundos mientras se
   instalan `spotipy` y `streamlit`.

## 5. Uso
1. Inicia sesión con Spotify.
2. Elige fuente: ❤️ Mis Me gusta o 📁 una playlist.
3. Ajusta variedad/intensidad en **⚙️ Configuración DJ** (opcional).
4. Ve a **🔥 Generar Auto-Mix**, define canciones por sesión, número de
   sesiones y modo, y pulsa **🔥 GENERAR Y CREAR EN SPOTIFY**.
5. Revisa **📊 Mi Perfil Musical**, **🤖 Mi IA Musical** y
   **🕘 Historial de Auto-Mix** para más contexto.

## 6. Notas sobre límites de Spotify (429)
- El motor cachea géneros de artistas en `st.session_state` para no
  repetir llamadas.
- Si Spotify responde 429, la app muestra un mensaje amigable con el
  tiempo de espera indicado por `Retry-After` — no reintenta en bucle
  ni bloquea la interfaz.

## 7. IA externa (opcional)
- Si defines `OPENAI_API_KEY`, el motor le pide a un modelo un orden
  sugerido de bloques de género (solo nombres de género y conteos —
  nunca tokens, secretos ni datos personales).
- Si esa clave no existe, o la llamada falla, el Auto-Mix se genera
  igual con el motor local. La IA nunca es un requisito para que la
  app funcione.
