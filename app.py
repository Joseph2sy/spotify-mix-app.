import streamlit as st

st.set_page_config(
    page_title="Spotify Auto-Mix",
    page_icon="🎵",
    layout="wide",
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
PROFILE_KEY = "spotify_profile"
PLAYLISTS_KEY = "spotify_playlists"


# ============================================================
# CONFIGURACIÓN DE SPOTIFY
# ============================================================

def get_spotify_oauth():
    try:
        client_id = st.secrets["SPOTIPY_CLIENT_ID"]
        client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
        redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"]

        if not client_id or not client_secret or not redirect_uri:
            raise ValueError(
                "Faltan SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET "
                "o SPOTIPY_REDIRECT_URI en los Secrets."
            )

        return SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=SCOPES,
            cache_path=None,
            open_browser=False,
            show_dialog=True,
        )

    except Exception as e:
        st.error("No se pudieron cargar las credenciales de Spotify.")
        st.exception(e)
        return None


# ============================================================
# AUTENTICACIÓN
# ============================================================

def login():
    """
    Genera directamente la URL externa de Spotify.
    SpotifyOAuth.get_authorize_url() debe devolver una URL
    que comienza por https://accounts.spotify.com/authorize
    """
    sp_oauth = get_spotify_oauth()

    if sp_oauth is None:
        return None

    try:
        auth_url = sp_oauth.get_authorize_url()

        # Validación adicional para evitar enviar una URL incorrecta.
        if not auth_url.startswith(
            "https://accounts.spotify.com/authorize"
        ):
            raise ValueError(
                "SpotifyOAuth generó una URL de autorización inválida."
            )

        return auth_url

    except Exception as e:
        st.error(
            "No se pudo generar la URL de inicio de sesión de Spotify."
        )
        st.exception(e)
        return None


def process_callback():
    """
    Procesa ?code=... después de que Spotify redirige
    nuevamente a la aplicación.
    """
    code = st.query_params.get("code")
    error = st.query_params.get("error")

    if error:
        st.error(
            f"Spotify rechazó la autorización: {error}"
        )

        st.query_params.clear()
        return

    if not code:
        return

    try:
        sp_oauth = get_spotify_oauth()

        if sp_oauth is None:
            return

        token_info = sp_oauth.get_access_token(
            code=code,
            as_dict=True,
            check_cache=False,
        )

        if not token_info:
            raise ValueError(
                "Spotify no devolvió información del token."
            )

        if "access_token" not in token_info:
            raise ValueError(
                "La respuesta de Spotify no contiene access_token."
            )

        st.session_state[TOKEN_KEY] = token_info

        # Elimina ?code=... de la URL.
        st.query_params.clear()

        st.rerun()

    except Exception as e:
        st.error(
            "No se pudo completar la autenticación con Spotify."
        )
        st.exception(e)


# ============================================================
# TOKEN
# ============================================================

def get_access_token():
    token_info = st.session_state.get(TOKEN_KEY)

    if not token_info:
        return None

    try:
        sp_oauth = get_spotify_oauth()

        if sp_oauth is None:
            return None

        if sp_oauth.is_token_expired(token_info):
            refresh_token = token_info.get("refresh_token")

            if not refresh_token:
                st.session_state.pop(TOKEN_KEY, None)
                return None

            token_info = sp_oauth.refresh_access_token(
                refresh_token
            )

            st.session_state[TOKEN_KEY] = token_info

        return token_info.get("access_token")

    except Exception as e:
        st.error(
            "La sesión de Spotify no pudo renovarse."
        )
        st.exception(e)

        st.session_state.pop(TOKEN_KEY, None)
        st.session_state.pop(PROFILE_KEY, None)
        st.session_state.pop(PLAYLISTS_KEY, None)

        return None


def get_spotify_client():
    access_token = get_access_token()

    if not access_token:
        return None

    try:
        return spotipy.Spotify(
            auth=access_token
        )

    except Exception as e:
        st.error(
            "No se pudo crear la conexión con Spotify."
        )
        st.exception(e)
        return None


# ============================================================
# LOGOUT
# ============================================================

def logout():
    for key in [
        TOKEN_KEY,
        PROFILE_KEY,
        PLAYLISTS_KEY,
    ]:
        st.session_state.pop(key, None)

    st.query_params.clear()
    st.rerun()


# ============================================================
# CALLBACK OAUTH
# ============================================================

# Solo procesamos el callback cuando todavía no existe
# una sesión autenticada.
if not st.session_state.get(TOKEN_KEY):
    if st.query_params.get("code") or st.query_params.get("error"):
        process_callback()


# ============================================================
# INTERFAZ NO AUTENTICADA
# ============================================================

if not st.session_state.get(TOKEN_KEY):

    st.markdown(
        """
        <style>
        .spotify-title {
            text-align: center;
            font-size: 3rem;
            font-weight: 800;
            margin-top: 4rem;
            margin-bottom: 1rem;
        }

        .spotify-description {
            text-align: center;
            max-width: 700px;
            margin: auto;
            font-size: 1.1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="spotify-title">🎵 Spotify Auto-Mix</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="spotify-description">
            Organiza tus playlists y prepara mezclas más fluidas
            utilizando información musical de tus canciones.
            <br><br>
            Conecta tu cuenta de Spotify para comenzar.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.write("")

    auth_url = login()

    if auth_url:

        col1, col2, col3 = st.columns(
            [1, 2, 1]
        )

        with col2:

            # IMPORTANTE:
            # st.link_button utiliza directamente la URL externa.
            # No crea una ruta interna de Streamlit.
            st.link_button(
                "🎧 Iniciar sesión con Spotify",
                auth_url,
                use_container_width=True,
            )

    else:

        st.error(
            "No se pudo generar el enlace de Spotify."
        )

    st.stop()


# ============================================================
# CONEXIÓN AUTENTICADA
# ============================================================

sp = get_spotify_client()

if sp is None:

    st.error(
        "Tu sesión de Spotify no está disponible."
    )

    if st.button(
        "Volver a iniciar sesión",
        type="primary",
    ):
        logout()

    st.stop()


# ============================================================
# PERFIL
# ============================================================

if PROFILE_KEY not in st.session_state:

    try:
        st.session_state[PROFILE_KEY] = (
            sp.current_user()
        )

    except Exception as e:

        st.error(
            "No se pudo obtener tu perfil de Spotify."
        )
        st.exception(e)
        st.stop()


profile = st.session_state[PROFILE_KEY]

display_name = (
    profile.get("display_name")
    or profile.get("id")
    or "Usuario"
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🎵 Spotify Auto-Mix")

    st.write(
        f"👤 **{display_name}**"
    )

    st.divider()

    if st.button(
        "Cerrar sesión",
        use_container_width=True,
    ):
        logout()


# ============================================================
# CABECERA
# ============================================================

st.title("🎵 Spotify Auto-Mix")

st.write(
    "Selecciona una playlist para analizar y organizar "
    "sus canciones."
)


# ============================================================
# CARGAR PLAYLISTS
# ============================================================

if PLAYLISTS_KEY not in st.session_state:

    try:

        playlists = []
        offset = 0
        limit = 50

        while True:

            response = sp.current_user_playlists(
                limit=limit,
                offset=offset,
            )

            items = response.get(
                "items",
                []
            )

            playlists.extend(items)

            if not response.get("next"):
                break

            offset += limit

        st.session_state[PLAYLISTS_KEY] = playlists

    except Exception as e:

        st.error(
            "No se pudieron cargar tus playlists de Spotify."
        )
        st.exception(e)
        st.stop()


playlists = st.session_state[PLAYLISTS_KEY]


if not playlists:

    st.warning(
        "No se encontraron playlists disponibles."
    )
    st.stop()


# ============================================================
# SELECTOR
# ============================================================

playlist_options = {}

for playlist in playlists:

    name = playlist.get(
        "name",
        "Sin nombre",
    )

    total = playlist.get(
        "tracks",
        {},
    ).get(
        "total",
        0,
    )

    label = f"{name} ({total} canciones)"

    playlist_options[label] = playlist


selected_label = st.selectbox(
    "Selecciona una playlist",
    list(playlist_options.keys()),
)


selected_playlist = playlist_options[
    selected_label
]


# ============================================================
# INFORMACIÓN DE PLAYLIST
# ============================================================

st.divider()

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "Playlist",
        selected_playlist.get(
            "name",
            "Sin nombre",
        ),
    )


with col2:

    total_tracks = selected_playlist.get(
        "tracks",
        {},
    ).get(
        "total",
        0,
    )

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
        "Desconocido",
    )

    st.metric(
        "Propietario",
        owner,
    )


# ============================================================
# OPCIONES DE MEZCLA
# ============================================================

st.subheader("⚙️ Opciones de mezcla")

strategy = st.selectbox(
    "Ordenar canciones por",
    [
        "Energía",
        "BPM",
        "Bailabilidad",
        "Ánimo",
    ],
)


# ============================================================
# ANALIZAR
# ============================================================

if st.button(
    "🔎 Analizar playlist",
    type="primary",
    use_container_width=True,
):

    try:

        with st.spinner(
            "Cargando canciones..."
        ):

            tracks = []
            offset = 0
            limit = 100

            while True:

                response = sp.playlist_items(
                    selected_playlist["id"],
                    limit=limit,
                    offset=offset,
                )

                items = response.get(
                    "items",
                    []
                )

                for item in items:

                    track = item.get("track")

                    if (
                        track
                        and track.get("id")
                        and track.get("type") == "track"
                    ):
                        tracks.append(track)

                if not response.get("next"):
                    break

                offset += limit


        if not tracks:

            st.warning(
                "No se encontraron canciones analizables."
            )
            st.stop()


        st.success(
            f"Se encontraron {len(tracks)} canciones."
        )


        # ====================================================
        # MÉTRICAS DE AUDIO
        # ====================================================

        track_ids = [
            track["id"]
            for track in tracks
            if track.get("id")
        ]

        audio_features = {}

        with st.spinner(
            "Obteniendo métricas musicales..."
        ):

            # Spotify permite solicitar varias pistas por llamada.
            for start in range(
                0,
                len(track_ids),
                100,
            ):

                batch = track_ids[
                    start:start + 100
                ]

                try:

                    result = sp.audio_features(
                        batch
                    )

                    if result:

                        for feature in result:

                            if feature:

                                audio_features[
                                    feature["id"]
                                ] = feature

                except Exception:
                    # Una falla en un lote no rompe
                    # todo el análisis.
                    continue


        # ====================================================
        # CONSTRUIR RESULTADOS
        # ====================================================

        rows = []

        for track in tracks:

            track_id = track.get("id")

            feature = audio_features.get(
                track_id,
                {},
            )

            artists = ", ".join(
                artist.get(
                    "name",
                    "Desconocido",
                )
                for artist in track.get(
                    "artists",
                    [],
                )
            )

            rows.append(
                {
                    "Canción": track.get(
                        "name",
                        "Sin nombre",
                    ),
                    "Artista": artists,
                    "Energía": feature.get(
                        "energy"
                    ),
                    "Bailabilidad": feature.get(
                        "danceability"
                    ),
                    "BPM": feature.get(
                        "tempo"
                    ),
                    "Ánimo": feature.get(
                        "valence"
                    ),
                    "URI": track.get(
                        "uri"
                    ),
                }
            )


        # ====================================================
        # ORDENAMIENTO
        # ====================================================

        if strategy == "Energía":

            rows.sort(
                key=lambda x: (
                    x["Energía"]
                    if x["Energía"] is not None
                    else -1
                )
            )

        elif strategy == "BPM":

            rows.sort(
                key=lambda x: (
                    x["BPM"]
                    if x["BPM"] is not None
                    else -1
                )
            )

        elif strategy == "Bailabilidad":

            rows.sort(
                key=lambda x: (
                    x["Bailabilidad"]
                    if x["Bailabilidad"] is not None
                    else -1
                )
            )

        elif strategy == "Ánimo":

            rows.sort(
                key=lambda x: (
                    x["Ánimo"]
                    if x["Ánimo"] is not None
                    else -1
                )
            )


        # ====================================================
        # MOSTRAR RESULTADOS
        # ====================================================

        st.divider()

        st.subheader(
            f"🎚️ Orden sugerido por {strategy}"
        )

        st.caption(
            "Este análisis solamente organiza los resultados "
            "y no modifica automáticamente tu playlist."
        )

        display_rows = []

        for index, row in enumerate(
            rows,
            start=1,
        ):

            display_rows.append(
                {
                    "#": index,
                    "Canción": row["Canción"],
                    "Artista": row["Artista"],
                    "Energía": (
                        round(row["Energía"], 3)
                        if row["Energía"] is not None
                        else None
                    ),
                    "Bailabilidad": (
                        round(row["Bailabilidad"], 3)
                        if row["Bailabilidad"] is not None
                        else None
                    ),
                    "BPM": (
                        round(row["BPM"], 1)
                        if row["BPM"] is not None
                        else None
                    ),
                    "Ánimo": (
                        round(row["Ánimo"], 3)
                        if row["Ánimo"] is not None
                        else None
                    ),
                }
            )


        st.dataframe(
            display_rows,
            use_container_width=True,
            hide_index=True,
        )


    except Exception as e:

        st.error(
            "Ocurrió un error al analizar la playlist. "
            "La aplicación sigue funcionando."
        )

        st.exception(e)


# ============================================================
# PIE
# ============================================================

st.divider()

st.caption(
    "Spotify Auto-Mix • Python + Streamlit + Spotipy"
)
