iimport math
import random
import time
from collections import Counter, defaultdict
from urllib.parse import urlparse

import requests
import streamlit as st
from spotipy.oauth2 import SpotifyOAuth

st.set_page_config(
    page_title="Spotify Auto-Mix DJ",
    page_icon="🎧",
    layout="wide",
)

# ============================================================
# CONFIGURACIÓN
# ============================================================

SCOPES = (
    "user-library-read "
    "playlist-read-private "
    "playlist-modify-private "
    "playlist-modify-public"
)

SPOTIFY_API = "https://api.spotify.com/v1"

TOKEN_KEY = "spotify_token"
PROFILE_KEY = "spotify_profile"
LIKED_KEY = "spotify_liked_tracks"
ARTIST_GENRES_KEY = "spotify_artist_genres"
LAST_CREATED_KEY = "spotify_last_created"

# Géneros que el usuario indicó como parte de su biblioteca.
USER_GENRES = [
    "Reggaeton",
    "Latin",
    "Pop Rock",
    "Cumbia",
    "Hip Hop",
    "Romantic",
    "Salsa",
    "Dance",
    "Rock",
    "Norteño",
    "Bolero",
    "Relaxing",
    "Pump Up",
    "Reggae spooky",
]

# Reglas de transición.
# No obligan a seguir este orden.
# Sirven para que un bloque pueda pasar naturalmente a otro.
GENRE_TRANSITIONS = {
    "reggaeton": [
        "latin", "dance", "pump up", "cumbia", "hip hop", "romantic"
    ],
    "latin": [
        "cumbia", "salsa", "reggaeton", "romantic", "bolero",
        "norteño", "dance"
    ],
    "pop rock": [
        "rock", "hip hop", "latin", "romantic", "dance", "reggaeton"
    ],
    "cumbia": [
        "latin", "salsa", "reggaeton", "norteño", "romantic", "vallenato"
    ],
    "hip hop": [
        "reggaeton", "dance", "pop rock", "latin", "rock"
    ],
    "romantic": [
        "bolero", "latin", "pop rock", "relaxing", "cumbia"
    ],
    "salsa": [
        "latin", "cumbia", "reggaeton", "dance", "romantic"
    ],
    "dance": [
        "pump up", "reggaeton", "pop rock", "hip hop", "latin"
    ],
    "rock": [
        "pop rock", "hip hop", "latin", "reggaeton", "relaxing"
    ],
    "norteño": [
        "cumbia", "latin", "romantic", "bolero"
    ],
    "bolero": [
        "romantic", "latin", "relaxing", "cumbia"
    ],
    "relaxing": [
        "romantic", "bolero", "pop rock", "latin", "reggae spooky"
    ],
    "pump up": [
        "dance", "reggaeton", "hip hop", "rock", "cumbia"
    ],
    "reggae spooky": [
        "relaxing", "rock", "latin", "reggaeton", "hip hop"
    ],
}

GENRE_ALIASES = {
    "reggaeton": "Reggaeton",
    "reggaetón": "Reggaeton",
    "reggae": "Reggae spooky",
    "reggae spooky": "Reggae spooky",
    "latin": "Latin",
    "latin pop": "Latin",
    "latin music": "Latin",
    "latin hip hop": "Hip Hop",
    "pop rock": "Pop Rock",
    "rock": "Rock",
    "alternative rock": "Rock",
    "indie rock": "Rock",
    "classic rock": "Rock",
    "hard rock": "Rock",
    "cumbia": "Cumbia",
    "cumbia villera": "Cumbia",
    "cumbia pop": "Cumbia",
    "hip hop": "Hip Hop",
    "rap": "Hip Hop",
    "trap": "Hip Hop",
    "romantic": "Romantic",
    "romantic ballads": "Romantic",
    "salsa": "Salsa",
    "salsa romantica": "Salsa",
    "dance": "Dance",
    "dance pop": "Dance",
    "edm": "Dance",
    "electropop": "Dance",
    "norteno": "Norteño",
    "norteño": "Norteño",
    "regional mexican": "Norteño",
    "northern mexican": "Norteño",
    "bolero": "Bolero",
    "relaxing": "Relaxing",
    "ambient": "Relaxing",
    "chill": "Relaxing",
    "chillout": "Relaxing",
    "sleep": "Relaxing",
    "pump up": "Pump Up",
    "workout": "Pump Up",
    "gym": "Pump Up",
}

# ============================================================
# UTILIDADES
# ============================================================


def get_config():
    try:
        client_id = st.secrets["SPOTIPY_CLIENT_ID"]
        client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
        redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"]

        if not client_id or not client_secret or not redirect_uri:
            raise ValueError("Faltan credenciales de Spotify.")

        return client_id, client_secret, redirect_uri

    except Exception as exc:
        st.error("No se pudieron cargar los Secrets de Spotify.")
        st.exception(exc)
        return None


def create_oauth():
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
        show_dialog=True,
    )


def get_authorize_url():
    try:
        oauth = create_oauth()

        if oauth is None:
            return None

        url = oauth.get_authorize_url()
        parsed = urlparse(url)

        if parsed.scheme != "https":
            raise ValueError("La URL OAuth no utiliza HTTPS.")

        if parsed.netloc != "accounts.spotify.com":
            raise ValueError("La URL generada no pertenece a Spotify.")

        return url

    except Exception as exc:
        st.error("No se pudo generar el inicio de sesión con Spotify.")
        st.exception(exc)
        return None


def process_callback():
    code = st.query_params.get("code")
    error = st.query_params.get("error")

    if error:
        st.error(f"Spotify rechazó la autorización: {error}")
        st.query_params.clear()
        return

    if not code:
        return

    try:
        oauth = create_oauth()

        if oauth is None:
            return

        token_info = oauth.get_access_token(
            code=code,
            as_dict=True,
            check_cache=False,
        )

        if not token_info or not token_info.get("access_token"):
            raise ValueError("Spotify no devolvió un token válido.")

        st.session_state[TOKEN_KEY] = token_info
        st.query_params.clear()
        st.rerun()

    except Exception as exc:
        st.error("No se pudo completar el inicio de sesión.")
        st.exception(exc)


def refresh_token():
    token_info = st.session_state.get(TOKEN_KEY)

    if not token_info:
        return None

    try:
        oauth = create_oauth()

        if oauth is None:
            return None

        if oauth.is_token_expired(token_info):
            refresh = token_info.get("refresh_token")

            if not refresh:
                st.session_state.pop(TOKEN_KEY, None)
                return None

            token_info = oauth.refresh_access_token(refresh)
            st.session_state[TOKEN_KEY] = token_info

        return token_info.get("access_token")

    except Exception as exc:
        st.error("La sesión de Spotify no pudo renovarse.")
        st.exception(exc)

        for key in [
            TOKEN_KEY,
            PROFILE_KEY,
            LIKED_KEY,
            ARTIST_GENRES_KEY,
            LAST_CREATED_KEY,
        ]:
            st.session_state.pop(key, None)

        return None


def api_request(method, endpoint, token, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"

    url = f"{SPOTIFY_API}{endpoint}"

    response = requests.request(
        method,
        url,
        headers=headers,
        timeout=20,
        **kwargs,
    )

    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text

        raise RuntimeError(
            f"Spotify API {response.status_code}: {detail}"
        )

    if not response.content:
        return {}

    return response.json()


def logout():
    for key in [
        TOKEN_KEY,
        PROFILE_KEY,
        LIKED_KEY,
        ARTIST_GENRES_KEY,
        LAST_CREATED_KEY,
    ]:
        st.session_state.pop(key, None)

    st.query_params.clear()
    st.rerun()


# ============================================================
# SPOTIFY API
# ============================================================


def get_profile(token):
    if PROFILE_KEY in st.session_state:
        return st.session_state[PROFILE_KEY]

    profile = api_request(
        "GET",
        "/me",
        token,
    )

    st.session_state[PROFILE_KEY] = profile
    return profile


def get_liked_tracks(token, force=False):
    if LIKED_KEY in st.session_state and not force:
        return st.session_state[LIKED_KEY]

    tracks = []
    offset = 0
    limit = 50

    while True:
        response = api_request(
            "GET",
            "/me/tracks",
            token,
            params={
                "limit": limit,
                "offset": offset,
            },
        )

        items = response.get("items", [])

        for saved in items:
            track = saved.get("track")

            if not track:
                continue

            if track.get("type") != "track":
                continue

            track_id = track.get("id")

            if not track_id:
                continue

            artists = track.get("artists", [])

            artist_ids = [
                artist.get("id")
                for artist in artists
                if artist.get("id")
            ]

            artist_names = [
                artist.get("name", "Desconocido")
                for artist in artists
            ]

            tracks.append(
                {
                    "id": track_id,
                    "uri": track.get("uri"),
                    "name": track.get("name", "Sin nombre"),
                    "artists": artist_names,
                    "artist_ids": artist_ids,
                    "album": track.get("album", {}).get(
                        "name",
                        "Sin álbum",
                    ),
                    "duration_ms": track.get("duration_ms", 0),
                    "explicit": bool(track.get("explicit", False)),
                }
            )

        if not response.get("next"):
            break

        offset += limit

    st.session_state[LIKED_KEY] = tracks
    return tracks


def get_artist_genres(token, artist_id):
    cache = st.session_state.setdefault(
        ARTIST_GENRES_KEY,
        {},
    )

    if artist_id in cache:
        return cache[artist_id]

    try:
        artist = api_request(
            "GET",
            f"/artists/{artist_id}",
            token,
        )

        genres = artist.get("genres", []) or []

        cache[artist_id] = genres

        return genres

    except Exception:
        cache[artist_id] = []
        return []


# ============================================================
# CLASIFICACIÓN DE GÉNEROS
# ============================================================


def normalize_text(value):
    return (
        str(value)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def normalize_genre(raw_genre):
    value = normalize_text(raw_genre)

    if value in GENRE_ALIASES:
        return GENRE_ALIASES[value]

    for alias, canonical in GENRE_ALIASES.items():
        if alias in value:
            return canonical

    return None


def infer_genre(track, artist_genres):
    normalized = []

    for genre in artist_genres:
        mapped = normalize_genre(genre)

        if mapped:
            normalized.append(mapped)

    if normalized:
        counts = Counter(normalized)
        return counts.most_common(1)[0][0]

    name = normalize_text(track.get("name", ""))
    artists = normalize_text(
        " ".join(track.get("artists", []))
    )

    combined = f"{name} {artists}"

    # Heurísticas de respaldo cuando Spotify no da género.
    keyword_rules = [
        (["reggaeton", "reggaetón"], "Reggaeton"),
        (["cumbia"], "Cumbia"),
        (["salsa"], "Salsa"),
        (["bachata"], "Latin"),
        (["bolero"], "Bolero"),
        (["norteno", "norteño"], "Norteño"),
        (["rock"], "Rock"),
        (["pop"], "Pop Rock"),
        (["hip hop", "rap"], "Hip Hop"),
        (["dance", "edm"], "Dance"),
        (["relax", "chill", "ambient"], "Relaxing"),
        (["reggae"], "Reggae spooky"),
    ]

    for keywords, genre in keyword_rules:
        if any(keyword in combined for keyword in keywords):
            return genre

    return "Latin"


def enrich_tracks_with_genres(tracks, token):
    enriched = []
    total = len(tracks)

    progress = st.progress(0)
    status = st.empty()

    for index, track in enumerate(tracks):
        artist_ids = track.get("artist_ids", [])

        all_genres = []

        for artist_id in artist_ids[:3]:
            genres = get_artist_genres(
                token,
                artist_id,
            )
            all_genres.extend(genres)

        genre = infer_genre(
            track,
            all_genres,
        )

        enriched_track = dict(track)
        enriched_track["genres_raw"] = all_genres
        enriched_track["genre"] = genre

        enriched.append(enriched_track)

        progress.progress(
            min(
                (index + 1) / max(total, 1),
                1.0,
            )
        )

        status.write(
            f"Analizando géneros: {index + 1}/{total}"
        )

        # Evita bombardear la API de forma agresiva.
        if index and index % 30 == 0:
            time.sleep(0.1)

    progress.empty()
    status.empty()

    return enriched


# ============================================================
# AGRUPAMIENTO
# ============================================================


def group_by_genre(tracks):
    groups = defaultdict(list)

    for track in tracks:
        genre = track.get("genre", "Latin")
        groups[genre].append(track)

    return groups


def genre_key(genre):
    return normalize_text(genre)


def next_genre(current_genre, available_genres, recent_genres):
    if not available_genres:
        return None

    current_key = genre_key(current_genre)

    preferred = GENRE_TRANSITIONS.get(
        current_key,
        [],
    )

    normalized_available = {
        genre_key(g): g
        for g in available_genres
    }

    candidates = []

    for preferred_genre in preferred:
        candidate = normalized_available.get(
            genre_key(preferred_genre)
        )

        if candidate:
            candidates.append(candidate)

    # Evita quedarse demasiado tiempo repitiendo el mismo género.
    for genre in available_genres:
        if genre not in candidates and genre not in recent_genres:
            candidates.append(genre)

    for genre in available_genres:
        if genre not in candidates:
            candidates.append(genre)

    if not candidates:
        return None

    weights = []

    for candidate in candidates:
        weight = 1.0

        if candidate in recent_genres:
            weight *= 0.25

        if candidate == current_genre:
            weight *= 0.35

        if candidate in preferred:
            weight *= 2.5

        weights.append(weight)

    return random.choices(
        candidates,
        weights=weights,
        k=1,
    )[0]


# ============================================================
# MOTOR DJ
# ============================================================


def score_transition(previous, candidate, genre_change=False):
    if previous is None:
        return 0.0

    score = 0.0

    prev_artist = " ".join(
        previous.get("artists", [])
    ).lower()

    cand_artist = " ".join(
        candidate.get("artists", [])
    ).lower()

    prev_genre = genre_key(
        previous.get("genre", "")
    )

    cand_genre = genre_key(
        candidate.get("genre", "")
    )

    if prev_genre == cand_genre:
        score += 5.0

    transition_targets = GENRE_TRANSITIONS.get(
        prev_genre,
        [],
    )

    if cand_genre in transition_targets:
        score += 8.0

    if prev_artist == cand_artist:
        score -= 2.5

    prev_duration = previous.get("duration_ms", 0) or 0
    cand_duration = candidate.get("duration_ms", 0) or 0

    # Duraciones parecidas suelen producir una sesión
    # más uniforme cuando no hay BPM disponible.
    if prev_duration and cand_duration:
        diff_seconds = abs(
            prev_duration - cand_duration
        ) / 1000

        if diff_seconds < 30:
            score += 2.0
        elif diff_seconds > 180:
            score -= 1.0

    if genre_change:
        score += 1.0

    score += random.uniform(
        -1.2,
        1.2,
    )

    return score


def choose_best_track(candidates, previous):
    if not candidates:
        return None

    scored = []

    for candidate in candidates:
        score = score_transition(
            previous,
            candidate,
            genre_change=(
                previous is not None
                and previous.get("genre")
                != candidate.get("genre")
            ),
        )

        scored.append(
            (
                score,
                candidate,
            )
        )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    top_n = min(
        5,
        len(scored),
    )

    return random.choice(
        scored[:top_n]
    )[1]


def create_dj_session(
    tracks,
    target_length,
    seed_offset=0,
):
    if len(tracks) <= target_length:
        return tracks[:]

    rng = random.Random(
        seed_offset + len(tracks)
    )

    groups = group_by_genre(tracks)

    available_genres = [
        genre
        for genre, songs in groups.items()
        if songs
    ]

    if not available_genres:
        return rng.sample(
            tracks,
            target_length,
        )

    # Mezcla inicial de géneros para que no sea una sola categoría.
    genre_counts = Counter(
        track.get("genre", "Latin")
        for track in tracks
    )

    sorted_genres = [
        genre
        for genre, _ in genre_counts.most_common()
    ]

    session = []
    used_ids = set()

    current_genre = rng.choice(
        sorted_genres[:min(5, len(sorted_genres))]
    )

    recent_genres = []

    previous = None

    while len(session) < target_length:

        candidates = [
            track
            for track in groups.get(
                current_genre,
                [],
            )
            if track.get("id") not in used_ids
        ]

        if not candidates:
            remaining_genres = [
                genre
                for genre in available_genres
                if any(
                    track.get("id") not in used_ids
                    for track in groups.get(genre, [])
                )
            ]

            if not remaining_genres:
                break

            current_genre = rng.choice(
                remaining_genres
            )
            candidates = [
                track
                for track in groups.get(
                    current_genre,
                    [],
                )
                if track.get("id") not in used_ids
            ]

        # Bloques variables para evitar que la sesión suene
        # como una simple alternancia de géneros.
        block_size = rng.randint(
            3,
            6,
        )

        for _ in range(block_size):

            if len(session) >= target_length:
                break

            candidates = [
                track
                for track in groups.get(
                    current_genre,
                    [],
                )
                if track.get("id") not in used_ids
            ]

            if not candidates:
                break

            selected = choose_best_track(
                candidates,
                previous,
            )

            if selected is None:
                break

            session.append(selected)
            used_ids.add(selected["id"])
            previous = selected

        # Cambio de ambiente.
        next_candidate = next_genre(
            current_genre,
            available_genres,
            recent_genres[-3:],
        )

        if next_candidate is None:
            break

        recent_genres.append(
            current_genre
        )

        current_genre = next_candidate

        if len(recent_genres) > 5:
            recent_genres.pop(0)

    # Completar huecos sin repetir dentro de la sesión.
    if len(session) < target_length:

        remaining = [
            track
            for track in tracks
            if track.get("id") not in used_ids
        ]

        rng.shuffle(remaining)

        session.extend(
            remaining[
                :target_length - len(session)
            ]
        )

    return session[:target_length]


def build_multiple_sessions(
    tracks,
    songs_per_session,
    session_count,
):
    sessions = []

    if not tracks:
        return sessions

    # Reutilización inteligente:
    # cada sesión vuelve a partir de toda la biblioteca,
    # pero construye una secuencia distinta.
    for session_index in range(session_count):

        session = create_dj_session(
            tracks,
            songs_per_session,
            seed_offset=session_index * 997,
        )

        if session:
            sessions.append(session)

    return sessions


# ============================================================
# CREACIÓN DE PLAYLISTS EN SPOTIFY
# ============================================================


def create_spotify_playlist(
    token,
    user_name,
    playlist_name,
    tracks,
    public=False,
):
    playlist = api_request(
        "POST",
        "/me/playlists",
        token,
        json={
            "name": playlist_name,
            "description": (
                "Creada automáticamente por Spotify Auto-Mix DJ. "
                "Sesión construida con transición entre estilos "
                "y variedad de géneros."
            ),
            "public": public,
            "collaborative": False,
        },
    )

    playlist_id = playlist.get("id")

    if not playlist_id:
        raise RuntimeError(
            "Spotify creó la playlist pero no devolvió su ID."
        )

    uris = [
        track.get("uri")
        for track in tracks
        if track.get("uri")
    ]

    # Spotify actual usa /items.
    batch_size = 100

    for start in range(
        0,
        len(uris),
        batch_size,
    ):
        batch = uris[
            start:start + batch_size
        ]

        api_request(
            "POST",
            f"/playlists/{playlist_id}/items",
            token,
            json={
                "uris": batch,
            },
        )

    return {
        "name": playlist_name,
        "url": playlist.get(
            "external_urls",
            {},
        ).get(
            "spotify"
        ),
        "id": playlist_id,
        "tracks": len(uris),
    }


# ============================================================
# UI - AUTH CALLBACK
# ============================================================


if not st.session_state.get(TOKEN_KEY):

    if (
        st.query_params.get("code")
        or st.query_params.get("error")
    ):
        process_callback()


# ============================================================
# UI - LOGIN
# ============================================================


if not st.session_state.get(TOKEN_KEY):

    st.title("🎧 Spotify Auto-Mix DJ")

    st.write(
        "Convierte tus Me gusta de Spotify en sesiones "
        "automáticas con cambios de género y bloques musicales."
    )

    st.info(
        "La aplicación crea las playlists directamente en tu Spotify. "
        "No tendrás que seleccionar las canciones una por una."
    )

    auth_url = get_authorize_url()

    if auth_url:
        st.link_button(
            "🎵 Iniciar sesión con Spotify",
            auth_url,
            use_container_width=True,
        )
    else:
        st.error(
            "No se pudo preparar el inicio de sesión."
        )

    st.stop()


# ============================================================
# UI - APP AUTENTICADA
# ============================================================


token = refresh_token()

if not token:
    st.error(
        "Tu sesión ya no está disponible."
    )

    if st.button(
        "Volver a iniciar sesión",
        type="primary",
    ):
        logout()

    st.stop()


try:
    profile = get_profile(token)

except Exception as exc:
    st.error(
        "No se pudo cargar tu perfil de Spotify."
    )
    st.exception(exc)
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

    st.title("🎧 Auto-Mix DJ")

    st.write(
        f"👤 **{display_name}**"
    )

    st.divider()

    songs_count = len(
        st.session_state.get(
            LIKED_KEY,
            [],
        )
    )

    if songs_count:
        st.metric(
            "Me gusta cargados",
            songs_count,
        )

    if st.button(
        "Cerrar sesión",
        use_container_width=True,
    ):
        logout()


# ============================================================
# HEADER
# ============================================================


st.title("🎧 Spotify Auto-Mix DJ")

st.write(
    "Tu biblioteca se convierte en varias sesiones de escucha. "
    "Las canciones pueden repetirse entre sesiones, pero no dentro "
    "de la misma sesión."
)


# ============================================================
# AJUSTES
# ============================================================


st.subheader("⚙️ Configuración")

col1, col2, col3 = st.columns(3)

with col1:
    songs_per_session = st.slider(
        "Canciones por sesión",
        min_value=15,
        max_value=25,
        value=20,
        step=1,
    )

with col2:
    session_count = st.slider(
        "Cantidad de sesiones",
        min_value=2,
        max_value=12,
        value=6,
        step=1,
    )

with col3:
    public_playlists = st.checkbox(
        "Crear playlists públicas",
        value=False,
    )


estimated_minutes = (
    songs_per_session * 3.5
)

st.caption(
    f"Duración aproximada por sesión: "
    f"{estimated_minutes:.0f} minutos."
)


# ============================================================
# CARGAR ME GUSTA
# ============================================================


st.divider()

st.subheader("❤️ Mis Me gusta")

load_col1, load_col2 = st.columns(
    [3, 1]
)

with load_col1:
    st.write(
        "La app utilizará tus canciones guardadas como "
        "biblioteca principal."
    )

with load_col2:
    refresh_library = st.button(
        "🔄 Actualizar",
        use_container_width=True,
    )


try:

    with st.spinner(
        "Cargando tus Me gusta..."
    ):
        liked_tracks = get_liked_tracks(
            token,
            force=refresh_library,
        )

except Exception as exc:

    st.error(
        "No se pudieron cargar tus Me gusta."
    )
    st.exception(exc)
    st.stop()


if not liked_tracks:

    st.warning(
        "No se encontraron canciones guardadas."
    )
    st.stop()


st.success(
    f"Se cargaron {len(liked_tracks)} canciones."
)


# ============================================================
# BOTÓN PRINCIPAL
# ============================================================


st.divider()

st.subheader("🔥 Crear sesiones DJ")

st.write(
    "La aplicación analizará los artistas, detectará los "
    "géneros disponibles y construirá varias sesiones diferentes."
)

create_mix = st.button(
    "🔥 GENERAR Y CREAR PLAYLISTS EN SPOTIFY",
    type="primary",
    use_container_width=True,
)


if create_mix:

    try:

        # ----------------------------------------------------
        # Géneros
        # ----------------------------------------------------

        with st.spinner(
            "Analizando géneros de tus canciones..."
        ):

            enriched_tracks = enrich_tracks_with_genres(
                liked_tracks,
                token,
            )

        genre_counts = Counter(
            track.get("genre", "Latin")
            for track in enriched_tracks
        )

        st.subheader("🎼 Géneros encontrados")

        genre_text = " • ".join(
            f"{genre}: {count}"
            for genre, count
            in genre_counts.most_common()
        )

        st.write(genre_text)


        # ----------------------------------------------------
        # Construcción
        # ----------------------------------------------------

        with st.spinner(
            "Construyendo sesiones de DJ..."
        ):

            sessions = build_multiple_sessions(
                enriched_tracks,
                songs_per_session,
                session_count,
            )


        if not sessions:

            st.error(
                "No se pudieron construir sesiones."
            )

            st.stop()


        st.success(
            f"Se generaron {len(sessions)} sesiones."
        )


        # ----------------------------------------------------
        # Crear playlists
        # ----------------------------------------------------

        created = []

        progress = st.progress(0)
        status = st.empty()

        for index, session in enumerate(
            sessions,
            start=1,
        ):

            status.write(
                f"Creando playlist {index}/{len(sessions)}..."
            )

            playlist_name = (
                f"🎧 Auto-Mix DJ {index:02d} "
                f"— {songs_per_session} tracks"
            )

            result = create_spotify_playlist(
                token=token,
                user_name=display_name,
                playlist_name=playlist_name,
                tracks=session,
                public=public_playlists,
            )

            created.append(result)

            progress.progress(
                index / len(sessions)
            )

        progress.empty()
        status.empty()


        st.session_state[
            LAST_CREATED_KEY
        ] = created


        # ----------------------------------------------------
        # Resultado
        # ----------------------------------------------------

        st.divider()

        st.subheader(
            "✅ Tus playlists fueron creadas"
        )

        for playlist in created:

            url = playlist.get("url")

            if url:

                st.link_button(
                    (
                        f"🎧 {playlist['name']} "
                        f"— {playlist['tracks']} canciones"
                    ),
                    url,
                    use_container_width=True,
                )

            else:

                st.write(
                    f"✅ {playlist['name']} "
                    f"— {playlist['tracks']} canciones"
                )


    except requests.Timeout:

        st.error(
            "Spotify tardó demasiado en responder. "
            "Vuelve a intentarlo; ninguna canción local "
            "se ha perdido."
        )


    except requests.RequestException as exc:

        st.error(
            "Hubo un problema de conexión con Spotify."
        )
        st.exception(exc)


    except Exception as exc:

        st.error(
            "No se pudo completar la creación del Auto-Mix."
        )
        st.exception(exc)


# ============================================================
# MOSTRAR EL ÚLTIMO RESULTADO
# ============================================================


last_created = st.session_state.get(
    LAST_CREATED_KEY,
    [],
)

if last_created:

    st.divider()

    st.subheader(
        "🎶 Últimas playlists creadas"
    )

    for playlist in last_created:

        url = playlist.get("url")

        if url:

            st.link_button(
                playlist["name"],
                url,
                use_container_width=True,
            )

        else:

            st.write(
                f"✅ {playlist['name']}"
            )


# ============================================================
# NOTA TÉCNICA
# ============================================================


st.divider()

st.caption(
    "Auto-Mix DJ utiliza tus canciones guardadas, géneros de artistas, "
    "bloques musicales y reglas de transición para construir sesiones "
    "diferentes. Spotify ha retirado/restringido varias funciones antiguas "
    "de la Web API en Development Mode, por lo que esta versión no depende "
    "obligatoriamente de Audio Features/BPM y continúa funcionando cuando "
    "esas métricas no están disponibles."
)
