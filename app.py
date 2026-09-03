import streamlit as st

st.set_page_config(
    page_title="Spotify Auto-Mix",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

import spotipy
from spotipy.oauth2 import SpotifyOAuth


# ============================================================
# CONFIGURACIÓN
# ============================================================

SCOPES = (
    "playlist-read-private "
    "playlist-modify-public "
    "playlist-modify-private "
    "user-library-read"
)

TOKEN_KEY = "spotify_token"
PLAYLISTS_KEY = "spotify_playlists"
PROFILE_KEY = "spotify_profile"

APP_TITLE = "Spotify Auto-Mix"
APP_DESCRIPTION = (
    "Organiza y prepara tus playlists para mezclas más fluidas "
    "usando información musical disponible en Spotify."
)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def get_config():
    """Obtiene las credenciales desde st.secrets."""
    try:
        client_id = st.secrets["SPOTIPY_CLIENT_ID"]
        client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
        redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"]

        if not all([client_id, client_secret, redirect_uri]):
            raise ValueError("Faltan una o más credenciales de Spotify.")

        return client_id, client_secret, redirect_uri

    except Exception as exc:
        st.error(
            "No se pudieron cargar las credenciales de Spotify. "
            "Revisa los valores de tu archivo/secrets de Streamlit."
        )
        st.exception(exc)
        return None


def create_oauth():
    """Crea el gestor OAuth de Spotipy."""
    config = get_config()

    if config is None:
        return None

    client_id, client_secret, redirect_uri = config

    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPES,
        cache_path=None,
        open_browser=False,
    )


def get_auth_url():
    """Genera la URL de autorización de Spotify."""
    try:
        oauth = create_oauth()

        if oauth is None:
            return None

        return oauth.get_authorize_url()

    except Exception as exc:
        st.error("No se pudo generar el enlace de inicio de sesión.")
        st.exception(exc)
        return None


def process_callback():
    """
    Procesa el parámetro ?code=... devuelto por Spotify.
    No se ejecuta ninguna llamada a la API antes de comprobar el estado.
    """
    try:
        code = st.query_params.get("code")

        if not code:
            return False

        oauth = create_oauth()

        if oauth is None:
            return False

        token_info = oauth.get_access_token(
            code,
            as_dict=True,
            check_cache=False,
        )

        if not token_info or "access_token" not in token_info:
            raise ValueError("Spotify no devolvió un token de acceso válido.")

        st.session_state[TOKEN_KEY] = token_info

        # Limpia el código OAuth de la URL.
        st.query_params.clear()

        st.rerun()

        return True

    except Exception as exc:
        st.error(
            "No se pudo completar el inicio de sesión con Spotify. "
            "Vuelve a intentarlo."
        )
        st.exception(exc)
        return False


def refresh_token_if_needed(token_info):
    """
    Comprueba si el token necesita renovación.
    Devuelve el token actualizado.
    """
    try:
        oauth = create_oauth()

        if oauth is None:
            return token_info

        if oauth.is_token_expired(token_info):
            refresh_token = token_info.get("refresh_token")

            if not refresh_token:
                raise ValueError("No existe refresh token disponible.")

            new_token = oauth.refresh_access_token(refresh_token)

            st.session_state[TOKEN_KEY] = new_token
            return new_token

        return token_info

    except Exception as exc:
        st.error(
            "No se pudo renovar la sesión de Spotify. "
            "Inicia sesión nuevamente."
        )
        st.exception(exc)

        st.session_state.pop(TOKEN_KEY, None)
        st.session_state.pop(PROFILE_KEY, None)
        st.session_state.pop(PLAYLISTS_KEY, None)

        return None


def get_spotify_client():
    """Devuelve un cliente Spotipy autenticado."""
    token_info = st.session_state.get(TOKEN_KEY)

    if not token_info:
        return None

    token_info = refresh_token_if_needed(token_info)

    if not token_info:
        return None

    access_token = token_info.get("access_token")

    if not access_token:
        return None

    return spotipy.Spotify(auth=access_token)


def logout():
    """Cierra la sesión local."""
    st.session_state.pop(TOKEN_KEY, None)
    st.session_state.pop(PROFILE_KEY, None)
    st.session_state.pop(PLAYLISTS_KEY, None)

    st.query_params.clear()
    st.rerun()


def get_user_profile(sp):
    """Obtiene el perfil del usuario."""
    if PROFILE_KEY in st.session_state:
        return st.session_state[PROFILE_KEY]

    try:
        profile = sp.current_user()
        st.session_state[PROFILE_KEY] = profile
        return profile

    except Exception as exc:
        st.error(
            "No se pudo obtener el perfil de Spotify. "
            "La sesión puede haber expirado."
        )
        st.exception(exc)
        return None


def get_user_playlists(sp):
    """Obtiene todas las playlists disponibles para el usuario."""
    if PLAYLISTS_KEY in st.session_state:
        return st.session_state[PLAYLISTS_KEY]

    try:
        playlists = []
        offset = 0
        limit = 50

        while True:
            response = sp.current_user_playlists(
                limit=limit,
                offset=offset,
            )

            items = response.get("items", [])
            playlists.extend(items)

            if not response.get("next"):
                break

            offset += limit

        st.session_state[PLAYLISTS_KEY] = playlists

        return playlists

    except Exception as exc:
        st.error(
            "No se pudieron cargar tus playlists de Spotify."
        )
        st.exception(exc)
        return []


def get_playlist_tracks(sp, playlist_id):
    """Obtiene las canciones de una playlist."""
    try:
        tracks = []
        offset = 0
        limit = 100

        while True:
            response = sp.playlist_items(
                playlist_id,
                limit=limit,
                offset=offset,
                fields=(
                    "items(track(id,name,uri,artists("
                    "name),duration_ms,album(name)),"
                    "next,total)"
                ),
            )

            items = response.get("items", [])

            for item in items:
                track = item.get("track")

                if not track:
                    continue

                if track.get("type") != "track":
                    continue

                if not track.get("id"):
                    continue

                tracks.append(track)

            if not response.get("next"):
                break

            offset += limit

        return tracks

    except Exception as exc:
        st.error(
            "No se pudieron cargar las canciones de la playlist."
        )
        st.exception(exc)
        return []


def get_audio_metrics(sp, track_ids):
    """
    Recupera métricas de audio individualmente.

    Spotify ha cambiado el acceso a ciertos endpoints de Web API,
    por lo que cada pista se procesa con tolerancia a errores.
    """
    metrics = {}

    if not track_ids:
        return metrics

    for track_id in track_ids:
        try:
            features = sp.audio_features([track_id])

            if features and features[0]:
                metrics[track_id] = features[0]

        except Exception:
            # Una canción sin métricas no debe romper toda la interfaz.
            continue

    return metrics


def build_mix_data(tracks, metrics):
    """Combina datos de pistas y métricas disponibles."""
    result = []

    for track in tracks:
        track_id = track.get("id")

        if not track_id:
            continue

        artists = track.get("artists", [])
        artist_names = ", ".join(
            artist.get("name", "Artista desconocido")
            for artist in artists
        )

        data = {
            "id": track_id,
            "name": track.get("name", "Sin nombre"),
            "artist": artist_names,
            "duration_ms": track.get("duration_ms"),
            "uri": track.get("uri"),
        }

        audio = metrics.get(track_id, {})

        data.update(
            {
                "energy": audio.get("energy"),
                "danceability": audio.get("danceability"),
                "tempo": audio.get("tempo"),
                "valence": audio.get("valence"),
                "acousticness": audio.get("acousticness"),
                "instrumentalness": audio.get("instrumentalness"),
                "speechiness": audio.get("speechiness"),
            }
        )

        result.append(data)

    return result


def sort_tracks_for_mix(mix_data, strategy="Energía"):
    """
    Ordena las canciones según una estrategia de mezcla.
    """
    valid = [
        track
        for track in mix_data
        if any(
            track.get(metric) is not None
            for metric in (
                "energy",
                "danceability",
                "tempo",
                "valence",
            )
        )
    ]

    if not valid:
        return mix_data

    if strategy == "Energía":
        return sorted(
            valid,
            key=lambda x: x.get("energy") or 0,
        )

    if strategy == "BPM":
        return sorted(
            valid,
            key=lambda x: x.get("tempo") or 0,
        )

    if strategy == "Bailabilidad":
        return sorted(
            valid,
            key=lambda x: x.get("danceability") or 0,
        )

    if strategy == "Ánimo":
        return sorted(
            valid,
            key=lambda x: x.get("valence") or 0,
        )

    return valid


# ============================================================
# ESTADO INICIAL
# ============================================================

if TOKEN_KEY not in st.session_state:
    st.session_state[TOKEN_KEY] = None

if PROFILE_KEY not in st.session_state:
    st.session_state[PROFILE_KEY] = None

if PLAYLISTS_KEY not in st.session_state:
    st.session_state[PLAYLISTS_KEY] = None


# ============================================================
# CALLBACK OAUTH
# ============================================================

# Procesar el callback solamente después de que Streamlit ya
# haya renderizado/configurado la aplicación.
if not st.session_state.get(TOKEN_KEY):
    if st.query_params.get("code"):
        process_callback()


# ============================================================
# PANTALLA NO AUTENTICADA
# ============================================================

if not st.session_state.get(TOKEN_KEY):

    st.markdown(
        """
        <style>
        .main-title {
            text-align: center;
            font-size: 3.2rem;
            font-weight: 800;
            margin-top: 4rem;
            margin-bottom: 1rem;
        }

        .main-description {
            text-align: center;
            font-size: 1.15rem;
            max-width: 760px;
            margin: 0 auto 2rem auto;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-title">🎵 Spotify Auto-Mix</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="main-description">
            {APP_DESCRIPTION}
            <br><br>
            Inicia sesión con Spotify para analizar tus playlists
            y preparar una organización basada en características
            musicales como energía, BPM, bailabilidad y ánimo.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    auth_url = get_auth_url()

    if auth_url:
        left, center, right = st.columns([1, 2, 1])

        with center:
            st.link_button(
                "🎧 Iniciar sesión con Spotify",
                auth_url,
                use_container_width=True,
            )
    else:
        st.error(
            "No fue posible preparar el inicio de sesión. "
            "Revisa los Secrets de Streamlit."
        )

    st.stop()


# ============================================================
# CLIENTE SPOTIFY
# ============================================================

sp = get_spotify_client()

if sp is None:
    st.error(
        "La sesión de Spotify no está disponible. "
        "Vuelve a iniciar sesión."
    )

    if st.button("🔐 Volver a iniciar sesión"):
        logout()

    st.stop()


# ============================================================
# PERFIL
# ============================================================

profile = get_user_profile(sp)

if profile is None:
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("🎵 Auto-Mix")

    display_name = (
        profile.get("display_name")
        or profile.get("id")
        or "Usuario"
    )

    st.write(f"👤 **{display_name}**")

    if st.button(
        "Cerrar sesión",
        use_container_width=True,
    ):
        logout()

    st.divider()

    st.caption(
        "Spotify Auto-Mix organiza tus canciones "
        "según sus características musicales."
    )


# ============================================================
# CABECERA
# ============================================================

st.title("🎵 Spotify Auto-Mix")

st.write(
    "Selecciona una playlist para preparar una mezcla "
    "ordenada por características musicales."
)


# ============================================================
# PLAYLISTS
# ============================================================

try:
    playlists = get_user_playlists(sp)

except Exception as exc:
    st.error("Ocurrió un problema al cargar tus playlists.")
    st.exception(exc)
    playlists = []


if not playlists:
    st.warning(
        "No se encontraron playlists disponibles para tu cuenta."
    )
    st.stop()


playlist_options = {
    f"{playlist.get('name', 'Sin nombre')} "
    f"({playlist.get('tracks', {}).get('total', 0)} canciones)": playlist
    for playlist in playlists
}


selected_label = st.selectbox(
    "Selecciona una playlist",
    options=list(playlist_options.keys()),
)

selected_playlist = playlist_options[selected_label]


# ============================================================
# INFORMACIÓN DE PLAYLIST
# ============================================================

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Playlist",
        selected_playlist.get("name", "Sin nombre"),
    )

with col2:
    total_tracks = selected_playlist.get(
        "tracks",
        {},
    ).get("total", 0)

    st.metric(
        "Canciones",
        total_tracks,
    )

with col3:
    owner = selected_playlist.get(
        "owner",
        {},
    ).get(
        "display_name",
        "Usuario",
    )

    st.metric(
        "Propietario",
        owner,
    )


# ============================================================
# CONFIGURACIÓN DE MEZCLA
# ============================================================

st.divider()

st.subheader("⚙️ Configuración del Auto-Mix")

strategy = st.selectbox(
    "Criterio principal de organización",
    [
        "Energía",
        "BPM",
        "Bailabilidad",
        "Ánimo",
    ],
)

analyze = st.button(
    "🔎 Analizar playlist",
    type="primary",
    use_container_width=True,
)


# ============================================================
# ANÁLISIS
# ============================================================

if analyze:

    with st.spinner("Cargando canciones de la playlist..."):

        tracks = get_playlist_tracks(
            sp,
            selected_playlist.get("id"),
        )

    if not tracks:
        st.warning(
            "La playlist no contiene canciones analizables."
        )
        st.stop()

    st.success(
        f"Se encontraron {len(tracks)} canciones."
    )

    track_ids = [
        track.get("id")
        for track in tracks
        if track.get("id")
    ]

    with st.spinner(
        "Preparando las métricas musicales disponibles..."
    ):

        metrics = get_audio_metrics(
            sp,
            track_ids,
        )

    mix_data = build_mix_data(
        tracks,
        metrics,
    )

    st.session_state["mix_data"] = mix_data

    ordered_tracks = sort_tracks_for_mix(
        mix_data,
        strategy,
    )

    if not ordered_tracks:
        st.warning(
            "No hay suficientes datos musicales para ordenar "
            "esta playlist."
        )
        st.stop()

    st.subheader(
        f"🎚️ Orden sugerido por {strategy}"
    )

    st.caption(
        "Este orden es una propuesta de organización. "
        "La playlist original no se modifica automáticamente."
    )

    # ========================================================
    # TABLA
    # ========================================================

    table_rows = []

    for index, track in enumerate(ordered_tracks, start=1):

        table_rows.append(
            {
                "#": index,
                "Canción": track.get("name", "Sin nombre"),
                "Artista": track.get(
                    "artist",
                    "Desconocido",
                ),
                "Energía": (
                    round(track["energy"], 3)
                    if track.get("energy") is not None
                    else None
                ),
                "Bailabilidad": (
                    round(track["danceability"], 3)
                    if track.get("danceability") is not None
                    else None
                ),
                "BPM": (
                    round(track["tempo"], 1)
                    if track.get("tempo") is not None
                    else None
                ),
                "Ánimo": (
                    round(track["valence"], 3)
                    if track.get("valence") is not None
                    else None
                ),
            }
        )

    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# RESUMEN SINCRONIZADO CON LA SELECCIÓN
# ============================================================

if "mix_data" in st.session_state:

    st.divider()

    st.subheader("📊 Métricas disponibles")

    current_mix = st.session_state["mix_data"]

    total_analyzed = len(current_mix)

    energy_values = [
        item["energy"]
        for item in current_mix
        if item.get("energy") is not None
    ]

    dance_values = [
        item["danceability"]
        for item in current_mix
        if item.get("danceability") is not None
    ]

    tempo_values = [
        item["tempo"]
        for item in current_mix
        if item.get("tempo") is not None
    ]

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)

    with metric_1:
        st.metric(
            "Analizadas",
            total_analyzed,
        )

    with metric_2:
        avg_energy = (
            sum(energy_values) / len(energy_values)
            if energy_values
            else 0
        )

        st.metric(
            "Energía media",
            f"{avg_energy:.2f}",
        )

    with metric_3:
        avg_dance = (
            sum(dance_values) / len(dance_values)
            if dance_values
            else 0
        )

        st.metric(
            "Bailabilidad media",
            f"{avg_dance:.2f}",
        )

    with metric_4:
        avg_tempo = (
            sum(tempo_values) / len(tempo_values)
            if tempo_values
            else 0
        )

        st.metric(
            "BPM medio",
            f"{avg_tempo:.1f}",
        )


# ============================================================
# PIE
# ============================================================

st.divider()

st.caption(
    "Spotify Auto-Mix • Aplicación desarrollada con "
    "Python, Streamlit y Spotipy"
)
