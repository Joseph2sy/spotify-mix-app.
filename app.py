import streamlit as st

st.set_page_config(
    page_title="Spotify Auto-Mix",
    page_icon="🎵",
    layout="wide",
)

from urllib.parse import urlparse

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
LIKED_TRACKS_KEY = "spotify_liked_tracks"
MIX_DATA_KEY = "spotify_mix_data"


# ============================================================
# SPOTIFY OAUTH
# ============================================================

def create_spotify_oauth():
    try:
        client_id = st.secrets["SPOTIPY_CLIENT_ID"]
        client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
        redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"]

        return SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=SCOPES,
            cache_path=None,
            open_browser=False,
            show_dialog=True,
        )

    except KeyError as e:
        st.error(
            f"Falta el secreto de Spotify: {e}"
        )
        return None

    except Exception as e:
        st.error(
            "No se pudo configurar la autenticación de Spotify."
        )
        st.exception(e)
        return None


def get_spotify_auth_url():
    try:
        sp_oauth = create_spotify_oauth()

        if sp_oauth is None:
            return None

        auth_url = sp_oauth.get_authorize_url()

        parsed = urlparse(auth_url)

        if parsed.scheme != "https":
            raise ValueError(
                "La URL de autorización no usa HTTPS."
            )

        if parsed.netloc != "accounts.spotify.com":
            raise ValueError(
                "SpotifyOAuth no generó una URL válida de Spotify."
            )

        return auth_url

    except Exception as e:
        st.error(
            "No se pudo generar el enlace de inicio de sesión."
        )
        st.exception(e)
        return None


# ============================================================
# CALLBACK
# ============================================================

def process_spotify_callback():
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
        sp_oauth = create_spotify_oauth()

        if sp_oauth is None:
            return

        token_info = sp_oauth.get_access_token(
            code=code,
            as_dict=True,
            check_cache=False,
        )

        if not token_info:
            raise ValueError(
                "Spotify no devolvió un token."
            )

        access_token = token_info.get("access_token")

        if not access_token:
            raise ValueError(
                "Spotify no devolvió un access_token válido."
            )

        st.session_state[TOKEN_KEY] = token_info

        st.query_params.clear()

        st.rerun()

    except Exception as e:
        st.error(
            "No se pudo completar el inicio de sesión con Spotify."
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
        sp_oauth = create_spotify_oauth()

        if sp_oauth is None:
            return None

        if sp_oauth.is_token_expired(token_info):
            refresh_token = token_info.get("refresh_token")

            if not refresh_token:
                raise ValueError(
                    "La sesión expiró y no existe refresh token."
                )

            new_token = sp_oauth.refresh_access_token(
                refresh_token
            )

            st.session_state[TOKEN_KEY] = new_token
            token_info = new_token

        return token_info.get("access_token")

    except Exception as e:
        st.error(
            "Tu sesión de Spotify expiró o no pudo renovarse."
        )
        st.exception(e)

        st.session_state.pop(TOKEN_KEY, None)
        st.session_state.pop(PROFILE_KEY, None)
        st.session_state.pop(PLAYLISTS_KEY, None)
        st.session_state.pop(LIKED_TRACKS_KEY, None)
        st.session_state.pop(MIX_DATA_KEY, None)

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
        LIKED_TRACKS_KEY,
        MIX_DATA_KEY,
    ]:
        st.session_state.pop(key, None)

    st.query_params.clear()
    st.rerun()


# ============================================================
# CARGAR PERFIL
# ============================================================

def load_profile(sp):
    if PROFILE_KEY in st.session_state:
        return st.session_state[PROFILE_KEY]

    try:
        profile = sp.current_user()

        st.session_state[PROFILE_KEY] = profile

        return profile

    except Exception as e:
        st.error(
            "No se pudo cargar tu perfil de Spotify."
        )
        st.exception(e)
        return None


# ============================================================
# CARGAR MIS ME GUSTA
# ============================================================

def load_liked_tracks(sp, force_reload=False):
    if (
        LIKED_TRACKS_KEY in st.session_state
        and not force_reload
    ):
        return st.session_state[LIKED_TRACKS_KEY]

    tracks = []

    try:
        offset = 0
        limit = 50

        while True:
            response = sp.current_user_saved_tracks(
                limit=limit,
                offset=offset,
            )

            items = response.get(
                "items",
                []
            )

            for item in items:
                track = item.get("track")

                if not track:
                    continue

                if track.get("type") != "track":
                    continue

                track_id = track.get("id")

                if not track_id:
                    continue

                artists = ", ".join(
                    artist.get(
                        "name",
                        "Desconocido",
                    )
                    for artist in track.get(
                        "artists",
                        []
                    )
                )

                tracks.append(
                    {
                        "id": track_id,
                        "name": track.get(
                            "name",
                            "Sin nombre",
                        ),
                        "artist": artists,
                        "uri": track.get(
                            "uri"
                        ),
                        "duration_ms": track.get(
                            "duration_ms"
                        ),
                        "album": track.get(
                            "album",
                            {}
                        ).get(
                            "name",
                            "Sin álbum",
                        ),
                        "added_at": item.get(
                            "added_at"
                        ),
                    }
                )

            if not response.get("next"):
                break

            offset += limit

        st.session_state[LIKED_TRACKS_KEY] = tracks

        return tracks

    except Exception as e:
        st.error(
            "No se pudieron cargar tus canciones de 'Me gusta'."
        )
        st.exception(e)
        return []


# ============================================================
# CARGAR PLAYLISTS
# ============================================================

def load_playlists(sp):
    if PLAYLISTS_KEY in st.session_state:
        return st.session_state[PLAYLISTS_KEY]

    playlists = []

    try:
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

        return playlists

    except Exception as e:
        st.error(
            "No se pudieron cargar tus playlists."
        )
        st.exception(e)
        return []


# ============================================================
# CARGAR CANCIONES DE PLAYLIST
# ============================================================

def load_playlist_tracks(sp, playlist_id):
    tracks = []

    try:
        offset = 0
        limit = 100

        while True:
            response = sp.playlist_items(
                playlist_id,
                limit=limit,
                offset=offset,
            )

            items = response.get(
                "items",
                []
            )

            for item in items:
                track = item.get("track")

                if not track:
                    continue

                if track.get("type") != "track":
                    continue

                track_id = track.get("id")

                if not track_id:
                    continue

                artists = ", ".join(
                    artist.get(
                        "name",
                        "Desconocido",
                    )
                    for artist in track.get(
                        "artists",
                        []
                    )
                )

                tracks.append(
                    {
                        "id": track_id,
                        "name": track.get(
                            "name",
                            "Sin nombre",
                        ),
                        "artist": artists,
                        "uri": track.get(
                            "uri"
                        ),
                        "duration_ms": track.get(
                            "duration_ms"
                        ),
                        "album": track.get(
                            "album",
                            {}
                        ).get(
                            "name",
                            "Sin álbum",
                        ),
                    }
                )

            if not response.get("next"):
                break

            offset += limit

        return tracks

    except Exception as e:
        st.error(
            "No se pudieron cargar las canciones de la playlist."
        )
        st.exception(e)
        return []


# ============================================================
# MÉTRICAS DE AUDIO
# ============================================================

def load_audio_features(sp, track_ids):
    """
    Intenta recuperar las métricas de audio de las canciones.

    Spotify restringe actualmente el acceso a Audio Features
    para determinadas aplicaciones nuevas, por lo que la función
    tolera fallos y deja las métricas como no disponibles.
    """

    features = {}

    if not track_ids:
        return features

    for start in range(
        0,
        len(track_ids),
        100,
    ):
        batch = track_ids[
            start:start + 100
        ]

        try:
            result = sp.audio_features(batch)

            if not result:
                continue

            for feature in result:
                if not feature:
                    continue

                track_id = feature.get("id")

                if track_id:
                    features[track_id] = feature

        except Exception:
            continue

    return features


# ============================================================
# CREAR DATOS DEL MIX
# ============================================================

def build_mix_data(tracks, audio_features):
    result = []

    for track in tracks:
        track_id = track.get("id")

        if not track_id:
            continue

        feature = audio_features.get(
            track_id,
            {}
        )

        result.append(
            {
                "id": track_id,
                "name": track.get(
                    "name",
                    "Sin nombre",
                ),
                "artist": track.get(
                    "artist",
                    "Desconocido",
                ),
                "album": track.get(
                    "album",
                    "Sin álbum",
                ),
                "uri": track.get(
                    "uri"
                ),
                "energy": feature.get(
                    "energy"
                ),
                "danceability": feature.get(
                    "danceability"
                ),
                "tempo": feature.get(
                    "tempo"
                ),
                "valence": feature.get(
                    "valence"
                ),
                "acousticness": feature.get(
                    "acousticness"
                ),
            }
        )

    return result


# ============================================================
# ORDENAMIENTO
# ============================================================

def sort_for_mix(mix_data, strategy):
    if not mix_data:
        return []

    metric_map = {
        "Energía": "energy",
        "BPM": "tempo",
        "Bailabilidad": "danceability",
        "Ánimo": "valence",
        "Acústica": "acousticness",
    }

    metric = metric_map.get(
        strategy
    )

    if not metric:
        return mix_data

    valid = [
        track
        for track in mix_data
        if track.get(metric) is not None
    ]

    invalid = [
        track
        for track in mix_data
        if track.get(metric) is None
    ]

    valid.sort(
        key=lambda track: track.get(
            metric,
            0
        )
    )

    return valid + invalid


# ============================================================
# ESTADO INICIAL
# ============================================================

if TOKEN_KEY not in st.session_state:
    st.session_state[TOKEN_KEY] = None


# ============================================================
# PROCESAR CALLBACK
# ============================================================

if not st.session_state.get(TOKEN_KEY):

    if (
        st.query_params.get("code")
        or st.query_params.get("error")
    ):
        process_spotify_callback()


# ============================================================
# PANTALLA DE LOGIN
# ============================================================

if not st.session_state.get(TOKEN_KEY):

    st.markdown(
        """
        <style>
        .title {
            text-align: center;
            font-size: 3rem;
            font-weight: 800;
            margin-top: 4rem;
        }

        .subtitle {
            text-align: center;
            max-width: 750px;
            margin: 1rem auto 2rem auto;
            font-size: 1.1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="title">🎵 Spotify Auto-Mix</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="subtitle">
            Convierte tus <b>Me gusta</b> de Spotify en una mezcla
            organizada y también trabaja con tus playlists.
            <br><br>
            Inicia sesión para cargar tu biblioteca.
        </div>
        """,
        unsafe_allow_html=True,
    )

    auth_url = get_spotify_auth_url()

    if auth_url:

        col1, col2, col3 = st.columns(
            [1, 2, 1]
        )

        with col2:

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
# CONEXIÓN
# ============================================================

sp = get_spotify_client()

if sp is None:

    st.error(
        "La conexión con Spotify no está disponible."
    )

    if st.button(
        "Volver a iniciar sesión"
    ):
        logout()

    st.stop()


# ============================================================
# PERFIL
# ============================================================

profile = load_profile(sp)

if not profile:
    st.stop()

display_name = (
    profile.get("display_name")
    or profile.get("id")
    or "Usuario"
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🎵 Auto-Mix")

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
    "Organiza tus canciones guardadas y crea una propuesta "
    "de mezcla según sus características."
)


# ============================================================
# FUENTE DE CANCIONES
# ============================================================

source = st.radio(
    "¿Qué quieres mezclar?",
    [
        "❤️ Mis Me gusta",
        "📁 Una playlist",
    ],
    horizontal=True,
)


tracks = []


# ============================================================
# MIS ME GUSTA
# ============================================================

if source == "❤️ Mis Me gusta":

    st.subheader("❤️ Mis Me gusta")

    col1, col2 = st.columns(
        [3, 1]
    )

    with col1:
        st.write(
            "Usaremos las canciones que tienes guardadas "
            "en tu biblioteca de Spotify."
        )

    with col2:

        if st.button(
            "🔄 Actualizar",
            use_container_width=True,
        ):
            tracks = load_liked_tracks(
                sp,
                force_reload=True,
            )
        else:
            tracks = load_liked_tracks(
                sp
            )


# ============================================================
# PLAYLIST
# ============================================================

else:

    st.subheader("📁 Mis playlists")

    playlists = load_playlists(sp)

    if not playlists:

        st.warning(
            "No tienes playlists disponibles."
        )
        st.stop()

    playlist_options = {}

    for playlist in playlists:

        name = playlist.get(
            "name",
            "Sin nombre",
        )

        playlist_id = playlist.get(
            "id"
        )

        if not playlist_id:
            continue

        total = playlist.get(
            "items",
            playlist.get(
                "tracks",
                {}
            )
        )

        if isinstance(total, dict):
            total = total.get(
                "total",
                0
            )
        else:
            total = 0

        playlist_options[
            f"{name} ({total} canciones)"
        ] = playlist

    selected_label = st.selectbox(
        "Selecciona una playlist",
        list(
            playlist_options.keys()
        ),
    )

    selected_playlist = playlist_options[
        selected_label
    ]

    if st.button(
        "📥 Cargar playlist",
        type="primary",
        use_container_width=True,
    ):

        tracks = load_playlist_tracks(
            sp,
            selected_playlist["id"],
        )

        st.session_state[
            "selected_playlist_tracks"
        ] = tracks

    else:

        tracks = st.session_state.get(
            "selected_playlist_tracks",
            []
        )


# ============================================================
# INFORMACIÓN
# ============================================================

if tracks:

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Canciones",
            len(tracks),
        )

    with col2:
        artists = {
            track.get("artist")
            for track in tracks
            if track.get("artist")
        }

        st.metric(
            "Artistas",
            len(artists),
        )

    with col3:
        total_minutes = (
            sum(
                (
                    track.get(
                        "duration_ms"
                    )
                    or 0
                )
                for track in tracks
            )
            / 60000
        )

        st.metric(
            "Duración",
            f"{total_minutes:.1f} min",
        )


# ============================================================
# CONFIGURACIÓN DEL MIX
# ============================================================

if tracks:

    st.divider()

    st.subheader(
        "🎚️ Configuración del Auto-Mix"
    )

    strategy = st.selectbox(
        "Organizar por",
        [
            "Energía",
            "BPM",
            "Bailabilidad",
            "Ánimo",
            "Acústica",
        ],
    )

    analyze = st.button(
        "🔥 Crear Auto-Mix",
        type="primary",
        use_container_width=True,
    )

    if analyze:

        track_ids = [
            track.get("id")
            for track in tracks
            if track.get("id")
        ]

        with st.spinner(
            "Analizando tus canciones..."
        ):

            audio_features = load_audio_features(
                sp,
                track_ids,
            )

        mix_data = build_mix_data(
            tracks,
            audio_features,
        )

        ordered_mix = sort_for_mix(
            mix_data,
            strategy,
        )

        st.session_state[
            MIX_DATA_KEY
        ] = ordered_mix

        if not audio_features:

            st.warning(
                "Spotify no proporcionó métricas de audio "
                "para estas canciones. Se muestran las canciones "
                "cargadas, pero el orden musical no pudo calcularse."
            )

        elif len(audio_features) < len(track_ids):

            st.warning(
                f"Spotify proporcionó métricas para "
                f"{len(audio_features)} de {len(track_ids)} canciones."
            )


# ============================================================
# MOSTRAR AUTO-MIX
# ============================================================

mix_data = st.session_state.get(
    MIX_DATA_KEY,
    []
)

if mix_data:

    st.divider()

    st.subheader(
        f"🔥 Auto-Mix ordenado por {strategy}"
    )

    rows = []

    for index, track in enumerate(
        mix_data,
        start=1,
    ):

        rows.append(
            {
                "#": index,
                "Canción": track.get(
                    "name",
                    "Sin nombre",
                ),
                "Artista": track.get(
                    "artist",
                    "Desconocido",
                ),
                "Álbum": track.get(
                    "album",
                    "Sin álbum",
                ),
                "Energía": (
                    round(
                        track["energy"],
                        3,
                    )
                    if track.get(
                        "energy"
                    ) is not None
                    else None
                ),
                "Bailabilidad": (
                    round(
                        track["danceability"],
                        3,
                    )
                    if track.get(
                        "danceability"
                    ) is not None
                    else None
                ),
                "BPM": (
                    round(
                        track["tempo"],
                        1,
                    )
                    if track.get(
                        "tempo"
                    ) is not None
                    else None
                ),
                "Ánimo": (
                    round(
                        track["valence"],
                        3,
                    )
                    if track.get(
                        "valence"
                    ) is not None
                    else None
                ),
            }
        )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )

    st.success(
        f"Auto-Mix preparado con {len(mix_data)} canciones."
    )

st.divider()

st.caption(
    "Spotify Auto-Mix • Python + Streamlit + Spotipy"
)
