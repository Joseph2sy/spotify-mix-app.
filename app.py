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

SPOTIFY_API = "https://api.spotify.com/v1"

SCOPES = (
    "user-library-read "
    "playlist-read-private "
    "playlist-modify-private "
    "playlist-modify-public"
)

TOKEN_KEY = "spotify_token"
PROFILE_KEY = "spotify_profile"
LIKED_KEY = "spotify_liked_tracks"
ARTIST_GENRES_KEY = "spotify_artist_genres"
ENRICHED_KEY = "spotify_enriched_tracks"
CREATED_KEY = "spotify_created_playlists"

# Géneros base indicados por el usuario.
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


# ============================================================
# MAPEO DE GÉNEROS
# ============================================================

GENRE_ALIASES = {
    "reggaeton": "Reggaeton",
    "reggaetón": "Reggaeton",
    "perreo": "Reggaeton",
    "urbano": "Reggaeton",

    "latin": "Latin",
    "latin music": "Latin",
    "latin pop": "Latin",
    "latin alternative": "Latin",
    "bachata": "Latin",

    "pop rock": "Pop Rock",
    "pop-rock": "Pop Rock",

    "cumbia": "Cumbia",
    "cumbia villera": "Cumbia",
    "cumbia pop": "Cumbia",

    "hip hop": "Hip Hop",
    "hip-hop": "Hip Hop",
    "rap": "Hip Hop",
    "trap": "Hip Hop",

    "romantic": "Romantic",
    "romantic ballads": "Romantic",
    "balada": "Romantic",
    "ballad": "Romantic",

    "salsa": "Salsa",
    "salsa romantica": "Salsa",

    "dance": "Dance",
    "dance pop": "Dance",
    "edm": "Dance",
    "electronic": "Dance",
    "electropop": "Dance",

    "rock": "Rock",
    "alternative rock": "Rock",
    "indie rock": "Rock",
    "classic rock": "Rock",
    "hard rock": "Rock",
    "soft rock": "Rock",

    "norteno": "Norteño",
    "norteño": "Norteño",
    "regional mexican": "Norteño",
    "regional mexicano": "Norteño",

    "bolero": "Bolero",

    "relaxing": "Relaxing",
    "relax": "Relaxing",
    "ambient": "Relaxing",
    "chill": "Relaxing",
    "chillout": "Relaxing",
    "downtempo": "Relaxing",

    "pump up": "Pump Up",
    "workout": "Pump Up",
    "gym": "Pump Up",
    "fitness": "Pump Up",

    "reggae": "Reggae spooky",
    "reggae spooky": "Reggae spooky",
}


# ============================================================
# TRANSICIONES
# ============================================================

GENRE_TRANSITIONS = {
    "reggaeton": [
        "Latin",
        "Cumbia",
        "Dance",
        "Hip Hop",
        "Salsa",
        "Romantic",
    ],

    "latin": [
        "Cumbia",
        "Salsa",
        "Reggaeton",
        "Romantic",
        "Bolero",
        "Norteño",
        "Dance",
    ],

    "pop rock": [
        "Rock",
        "Latin",
        "Hip Hop",
        "Romantic",
        "Dance",
    ],

    "cumbia": [
        "Latin",
        "Salsa",
        "Reggaeton",
        "Norteño",
        "Romantic",
    ],

    "hip hop": [
        "Reggaeton",
        "Dance",
        "Pop Rock",
        "Rock",
        "Latin",
    ],

    "romantic": [
        "Bolero",
        "Latin",
        "Relaxing",
        "Pop Rock",
        "Cumbia",
    ],

    "salsa": [
        "Latin",
        "Cumbia",
        "Reggaeton",
        "Dance",
        "Romantic",
    ],

    "dance": [
        "Pump Up",
        "Reggaeton",
        "Hip Hop",
        "Pop Rock",
        "Latin",
    ],

    "rock": [
        "Pop Rock",
        "Hip Hop",
        "Latin",
        "Relaxing",
        "Reggaeton",
    ],

    "norteño": [
        "Cumbia",
        "Latin",
        "Romantic",
        "Bolero",
    ],

    "bolero": [
        "Romantic",
        "Latin",
        "Relaxing",
        "Cumbia",
    ],

    "relaxing": [
        "Romantic",
        "Bolero",
        "Pop Rock",
        "Latin",
        "Reggae spooky",
    ],

    "pump up": [
        "Dance",
        "Reggaeton",
        "Hip Hop",
        "Rock",
        "Cumbia",
    ],

    "reggae spooky": [
        "Relaxing",
        "Rock",
        "Latin",
        "Reggaeton",
        "Hip Hop",
    ],
}


# ============================================================
# ESTILO DE SESIÓN
# ============================================================

SESSION_MODES = {
    "DJ Profesional": {
        "name_prefix": "Auto-Mix DJ",
        "min_block": 3,
        "max_block": 6,
    },
    "Tarde": {
        "name_prefix": "Auto-Mix Tarde",
        "min_block": 4,
        "max_block": 7,
    },
    "Manejo": {
        "name_prefix": "Auto-Mix Manejo",
        "min_block": 4,
        "max_block": 7,
    },
    "Fiesta": {
        "name_prefix": "Auto-Mix Fiesta",
        "min_block": 3,
        "max_block": 5,
    },
}


# ============================================================
# SPOTIFY OAUTH
# ============================================================

def create_oauth():
    try:
        client_id = st.secrets["SPOTIPY_CLIENT_ID"]
        client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
        redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"]

        if not client_id or not client_secret or not redirect_uri:
            raise ValueError(
                "Faltan credenciales de Spotify en Secrets."
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

    except Exception as exc:
        st.error(
            "No se pudo configurar la autenticación de Spotify."
        )
        st.exception(exc)
        return None


def get_authorize_url():
    try:
        oauth = create_oauth()

        if oauth is None:
            return None

        auth_url = oauth.get_authorize_url()
        parsed = urlparse(auth_url)

        if parsed.scheme != "https":
            raise ValueError(
                "Spotify generó una URL que no utiliza HTTPS."
            )

        if parsed.netloc != "accounts.spotify.com":
            raise ValueError(
                "La URL generada no pertenece a Spotify."
            )

        return auth_url

    except Exception as exc:
        st.error(
            "No se pudo generar el enlace de Spotify."
        )
        st.exception(exc)
        return None


def process_callback():
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
        oauth = create_oauth()

        if oauth is None:
            return

        token_info = oauth.get_access_token(
            code=code,
            as_dict=True,
            check_cache=False,
        )

        if not token_info:
            raise ValueError(
                "Spotify no devolvió información del token."
            )

        if not token_info.get("access_token"):
            raise ValueError(
                "Spotify no devolvió un access_token."
            )

        st.session_state[TOKEN_KEY] = token_info

        st.query_params.clear()
        st.rerun()

    except Exception as exc:
        st.error(
            "No se pudo completar el inicio de sesión."
        )
        st.exception(exc)


# ============================================================
# TOKEN
# ============================================================

def get_token():
    token_info = st.session_state.get(TOKEN_KEY)

    if not token_info:
        return None

    try:
        oauth = create_oauth()

        if oauth is None:
            return None

        if oauth.is_token_expired(token_info):
            refresh_token = token_info.get("refresh_token")

            if not refresh_token:
                raise ValueError(
                    "La sesión expiró y no existe refresh token."
                )

            token_info = oauth.refresh_access_token(
                refresh_token
            )

            st.session_state[TOKEN_KEY] = token_info

        return token_info.get("access_token")

    except Exception as exc:
        st.error(
            "No se pudo renovar tu sesión de Spotify."
        )
        st.exception(exc)

        clear_session()
        return None


# ============================================================
# PETICIONES CON BACKOFF
# ============================================================

def spotify_request(
    method,
    endpoint,
    token,
    params=None,
    json_data=None,
    max_retries=5,
):
    url = f"{SPOTIFY_API}{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for attempt in range(max_retries):

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=30,
            )

        except requests.RequestException as exc:

            if attempt >= max_retries - 1:
                raise RuntimeError(
                    f"Error de conexión con Spotify: {exc}"
                )

            time.sleep(
                min(
                    2 ** attempt,
                    8,
                )
            )

            continue

        # ----------------------------------------------------
        # RATE LIMIT
        # ----------------------------------------------------

        if response.status_code == 429:

            retry_after = response.headers.get(
                "Retry-After",
                "5",
            )

            try:
                wait_seconds = int(
                    float(retry_after)
                )
            except ValueError:
                wait_seconds = 5

            wait_seconds = max(
                1,
                min(
                    wait_seconds,
                    30,
                ),
            )

            if attempt >= max_retries - 1:
                raise RuntimeError(
                    "Spotify está limitando las peticiones. "
                    "Espera unos segundos antes de volver a generar "
                    "el Auto-Mix."
                )

            st.warning(
                f"Spotify está limitando temporalmente las peticiones. "
                f"Reintentando en {wait_seconds} segundos..."
            )

            time.sleep(wait_seconds)
            continue

        # ----------------------------------------------------
        # ERRORES DE SERVIDOR
        # ----------------------------------------------------

        if response.status_code >= 500:

            if attempt >= max_retries - 1:
                raise RuntimeError(
                    f"Spotify devolvió un error {response.status_code}."
                )

            time.sleep(
                min(
                    2 ** attempt,
                    8,
                )
            )

            continue

        # ----------------------------------------------------
        # OTROS ERRORES
        # ----------------------------------------------------

        if response.status_code >= 400:

            try:
                detail = response.json()
            except Exception:
                detail = response.text

            raise RuntimeError(
                f"Spotify API {response.status_code}: {detail}"
            )

        # ----------------------------------------------------
        # RESPUESTA VACÍA
        # ----------------------------------------------------

        if not response.content:
            return {}

        try:
            return response.json()
        except ValueError:
            return {}

    raise RuntimeError(
        "No fue posible completar la solicitud a Spotify."
    )


# ============================================================
# LIMPIAR SESIÓN
# ============================================================

def clear_session():
    for key in [
        TOKEN_KEY,
        PROFILE_KEY,
        LIKED_KEY,
        ARTIST_GENRES_KEY,
        ENRICHED_KEY,
        CREATED_KEY,
    ]:
        st.session_state.pop(key, None)

    st.query_params.clear()


def logout():
    clear_session()
    st.rerun()


# ============================================================
# PERFIL
# ============================================================

def load_profile(token):
    if PROFILE_KEY in st.session_state:
        return st.session_state[PROFILE_KEY]

    profile = spotify_request(
        "GET",
        "/me",
        token,
    )

    st.session_state[PROFILE_KEY] = profile
    return profile


# ============================================================
# MIS ME GUSTA
# ============================================================

def load_liked_tracks(
    token,
    force_reload=False,
):
    if (
        LIKED_KEY in st.session_state
        and not force_reload
    ):
        return st.session_state[LIKED_KEY]

    tracks = []

    offset = 0
    limit = 50

    progress = st.progress(0)
    status = st.empty()

    while True:

        response = spotify_request(
            "GET",
            "/me/tracks",
            token,
            params={
                "limit": limit,
                "offset": offset,
            },
        )

        items = response.get(
            "items",
            [],
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

            artists = track.get(
                "artists",
                [],
            )

            tracks.append(
                {
                    "id": track_id,
                    "uri": track.get("uri"),
                    "name": track.get(
                        "name",
                        "Sin nombre",
                    ),
                    "artist_ids": [
                        artist.get("id")
                        for artist in artists
                        if artist.get("id")
                    ],
                    "artists": [
                        artist.get(
                            "name",
                            "Desconocido",
                        )
                        for artist in artists
                    ],
                    "album": track.get(
                        "album",
                        {},
                    ).get(
                        "name",
                        "Sin álbum",
                    ),
                    "duration_ms": track.get(
                        "duration_ms",
                        0,
                    ),
                    "explicit": bool(
                        track.get(
                            "explicit",
                            False,
                        )
                    ),
                }
            )

        total = response.get(
            "total",
            len(tracks),
        )

        progress.progress(
            min(
                len(tracks) / max(total, 1),
                1.0,
            )
        )

        status.write(
            f"Cargando Me gusta: "
            f"{len(tracks)} canciones..."
        )

        if not response.get("next"):
            break

        offset += limit

    progress.empty()
    status.empty()

    # Eliminamos duplicados por ID.
    unique = {}
    for track in tracks:
        unique[track["id"]] = track

    tracks = list(
        unique.values()
    )

    st.session_state[LIKED_KEY] = tracks

    return tracks


# ============================================================
# GÉNEROS DE ARTISTAS
# ============================================================

def get_artist_genres(
    token,
    artist_id,
):
    cache = st.session_state.setdefault(
        ARTIST_GENRES_KEY,
        {},
    )

    if artist_id in cache:
        return cache[artist_id]

    try:

        artist = spotify_request(
            "GET",
            f"/artists/{artist_id}",
            token,
        )

        genres = artist.get(
            "genres",
            [],
        ) or []

        cache[artist_id] = genres

        # Pausa muy pequeña para evitar ráfagas.
        time.sleep(0.15)

        return genres

    except Exception:
        cache[artist_id] = []
        return []


# ============================================================
# NORMALIZACIÓN
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
    value = normalize_text(
        raw_genre
    )

    if value in GENRE_ALIASES:
        return GENRE_ALIASES[value]

    for alias, canonical in GENRE_ALIASES.items():

        if alias in value:
            return canonical

    return None


# ============================================================
# INFERIR GÉNERO
# ============================================================

def infer_genre(
    track,
    spotify_genres,
):
    detected = []

    for raw_genre in spotify_genres:

        mapped = normalize_genre(
            raw_genre
        )

        if mapped:
            detected.append(
                mapped
            )

    if detected:

        counts = Counter(
            detected
        )

        return counts.most_common(1)[0][0]

    combined = normalize_text(
        track.get("name", "")
        + " "
        + " ".join(
            track.get(
                "artists",
                [],
            )
        )
    )

    fallback_rules = [
        (
            [
                "reggaeton",
                "reggaetón",
                "perreo",
            ],
            "Reggaeton",
        ),
        (
            ["cumbia"],
            "Cumbia",
        ),
        (
            ["salsa"],
            "Salsa",
        ),
        (
            [
                "bachata",
                "latin",
            ],
            "Latin",
        ),
        (
            [
                "bolero",
            ],
            "Bolero",
        ),
        (
            [
                "norteno",
                "norteño",
            ],
            "Norteño",
        ),
        (
            [
                "rock",
            ],
            "Rock",
        ),
        (
            [
                "pop",
            ],
            "Pop Rock",
        ),
        (
            [
                "rap",
                "hip hop",
                "hip-hop",
                "trap",
            ],
            "Hip Hop",
        ),
        (
            [
                "dance",
                "edm",
            ],
            "Dance",
        ),
        (
            [
                "relax",
                "chill",
                "ambient",
            ],
            "Relaxing",
        ),
        (
            [
                "reggae",
            ],
            "Reggae spooky",
        ),
    ]

    for keywords, genre in fallback_rules:

        if any(
            keyword in combined
            for keyword in keywords
        ):
            return genre

    return "Latin"


# ============================================================
# ENRIQUECER CANCIONES
# ============================================================

def enrich_tracks(
    tracks,
    token,
    force_reload=False,
):
    if (
        ENRICHED_KEY in st.session_state
        and not force_reload
    ):
        return st.session_state[
            ENRICHED_KEY
        ]

    # --------------------------------------------------------
    # Artistas únicos
    # --------------------------------------------------------

    artist_ids = []

    seen_artists = set()

    for track in tracks:

        for artist_id in track.get(
            "artist_ids",
            [],
        ):

            if artist_id not in seen_artists:

                seen_artists.add(
                    artist_id
                )

                artist_ids.append(
                    artist_id
                )

    artist_genres = {}

    total_artists = len(
        artist_ids
    )

    progress = st.progress(0)
    status = st.empty()

    # --------------------------------------------------------
    # Solamente una consulta por artista.
    # --------------------------------------------------------

    for index, artist_id in enumerate(
        artist_ids,
        start=1,
    ):

        status.write(
            f"Analizando artistas: "
            f"{index}/{total_artists}"
        )

        artist_genres[artist_id] = (
            get_artist_genres(
                token,
                artist_id,
            )
        )

        progress.progress(
            index / max(
                total_artists,
                1,
            )
        )

    progress.empty()
    status.empty()

    # --------------------------------------------------------
    # Clasificar canciones.
    # --------------------------------------------------------

    enriched = []

    for track in tracks:

        genres = []

        for artist_id in track.get(
            "artist_ids",
            [],
        ):

            genres.extend(
                artist_genres.get(
                    artist_id,
                    [],
                )
            )

        genre = infer_genre(
            track,
            genres,
        )

        item = dict(
            track
        )

        item["genre"] = genre
        item["genres_raw"] = genres

        enriched.append(
            item
        )

    st.session_state[
        ENRICHED_KEY
    ] = enriched

    return enriched


# ============================================================
# AGRUPAR
# ============================================================

def group_tracks_by_genre(
    tracks
):
    groups = defaultdict(list)

    for track in tracks:

        genre = track.get(
            "genre",
            "Latin",
        )

        groups[genre].append(
            track
        )

    return groups


# ============================================================
# PUNTUACIÓN DE TRANSICIÓN
# ============================================================

def transition_score(
    previous,
    candidate,
    current_genre,
):
    if previous is None:
        return 0.0

    score = 0.0

    previous_genre = normalize_text(
        previous.get(
            "genre",
            "",
        )
    )

    candidate_genre = normalize_text(
        candidate.get(
            "genre",
            "",
        )
    )

    # --------------------------------------------------------
    # Mismo género
    # --------------------------------------------------------

    if previous_genre == candidate_genre:
        score += 5.0

    # --------------------------------------------------------
    # Género compatible
    # --------------------------------------------------------

    possible_transitions = [
        normalize_text(
            item
        )
        for item in GENRE_TRANSITIONS.get(
            previous_genre,
            [],
        )
    ]

    if candidate_genre in possible_transitions:
        score += 8.0

    # --------------------------------------------------------
    # Evitar mismo artista consecutivo
    # --------------------------------------------------------

    previous_artists = {
        normalize_text(
            artist
        )
        for artist in previous.get(
            "artists",
            [],
        )
    }

    candidate_artists = {
        normalize_text(
            artist
        )
        for artist in candidate.get(
            "artists",
            [],
        )
    }

    if previous_artists & candidate_artists:
        score -= 5.0
    else:
        score += 1.5

    # --------------------------------------------------------
    # Duración parecida.
    # No es BPM, pero ayuda a que el flujo no sea extraño.
    # --------------------------------------------------------

    previous_duration = (
        previous.get(
            "duration_ms",
            0,
        )
        or 0
    )

    candidate_duration = (
        candidate.get(
            "duration_ms",
            0,
        )
        or 0
    )

    if previous_duration and candidate_duration:

        duration_difference = abs(
            previous_duration
            - candidate_duration
        ) / 1000

        if duration_difference < 20:
            score += 2.0

        elif duration_difference < 60:
            score += 1.0

        elif duration_difference > 180:
            score -= 1.0

    # Pequeña variación para que dos sesiones no queden idénticas.
    score += random.uniform(
        -1.0,
        1.0,
    )

    return score


# ============================================================
# ELEGIR CANCIÓN
# ============================================================

def choose_next_track(
    candidates,
    previous,
    current_genre,
):
    if not candidates:
        return None

    scored = []

    for candidate in candidates:

        score = transition_score(
            previous,
            candidate,
            current_genre,
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

    # Elegimos entre las mejores para no generar siempre
    # exactamente la misma playlist.
    top = scored[
        :min(
            5,
            len(scored),
        )
    ]

    return random.choice(
        top
    )[1]


# ============================================================
# CAMBIO DE GÉNERO
# ============================================================

def choose_next_genre(
    current_genre,
    available_genres,
    recent_genres,
):
    if not available_genres:
        return None

    current_key = normalize_text(
        current_genre
    )

    preferred = [
        normalize_text(
            genre
        )
        for genre in GENRE_TRANSITIONS.get(
            current_key,
            [],
        )
    ]

    mapped = {
        normalize_text(genre): genre
        for genre in available_genres
    }

    preferred_candidates = []

    for genre_key in preferred:

        if genre_key in mapped:

            genre = mapped[
                genre_key
            ]

            if genre != current_genre:
                preferred_candidates.append(
                    genre
                )

    # Evitar usar demasiado pronto un género reciente.
    fresh_candidates = [
        genre
        for genre in available_genres
        if genre not in recent_genres
        and genre != current_genre
    ]

    candidates = []

    candidates.extend(
        preferred_candidates
    )

    candidates.extend(
        genre
        for genre in fresh_candidates
        if genre not in candidates
    )

    candidates.extend(
        genre
        for genre in available_genres
        if genre not in candidates
        and genre != current_genre
    )

    if not candidates:
        return None

    # Preferencia fuerte por transiciones compatibles.
    weights = []

    for genre in candidates:

        if genre in preferred_candidates:
            weight = 5.0

        elif genre in fresh_candidates:
            weight = 2.5

        else:
            weight = 1.0

        weights.append(
            weight
        )

    return random.choices(
        candidates,
        weights=weights,
        k=1,
    )[0]


# ============================================================
# CREAR UNA SESIÓN DJ
# ============================================================

def create_dj_session(
    tracks,
    songs_per_session,
    mode,
    seed,
):
    if not tracks:
        return []

    if len(tracks) <= songs_per_session:
        return tracks[:]

    rng = random.Random(
        seed
    )

    groups = group_tracks_by_genre(
        tracks
    )

    available_genres = [
        genre
        for genre, songs
        in groups.items()
        if songs
    ]

    if not available_genres:
        return rng.sample(
            tracks,
            songs_per_session,
        )

    # Preferir géneros con más variedad.
    genre_weights = [
        max(
            1,
            len(
                groups[genre]
            ),
        )
        for genre in available_genres
    ]

    current_genre = rng.choices(
        available_genres,
        weights=genre_weights,
        k=1,
    )[0]

    mode_config = SESSION_MODES.get(
        mode,
        SESSION_MODES["DJ Profesional"],
    )

    min_block = mode_config[
        "min_block"
    ]

    max_block = mode_config[
        "max_block"
    ]

    session = []

    used_ids = set()

    previous = None

    recent_genres = []

    while (
        len(session)
        < songs_per_session
    ):

        available_tracks = [
            track
            for track
            in groups.get(
                current_genre,
                [],
            )
            if track.get("id")
            not in used_ids
        ]

        if not available_tracks:

            possible_genres = [
                genre
                for genre
                in available_genres
                if any(
                    track.get("id")
                    not in used_ids
                    for track
                    in groups.get(
                        genre,
                        [],
                    )
                )
            ]

            if not possible_genres:
                break

            current_genre = rng.choice(
                possible_genres
            )

            available_tracks = [
                track
                for track
                in groups.get(
                    current_genre,
                    [],
                )
                if track.get("id")
                not in used_ids
            ]

        block_size = rng.randint(
            min_block,
            max_block,
        )

        for _ in range(
            block_size
        ):

            if len(session) >= songs_per_session:
                break

            available_tracks = [
                track
                for track
                in groups.get(
                    current_genre,
                    [],
                )
                if track.get("id")
                not in used_ids
            ]

            if not available_tracks:
                break

            selected = choose_next_track(
                available_tracks,
                previous,
                current_genre,
            )

            if selected is None:
                break

            session.append(
                selected
            )

            used_ids.add(
                selected["id"]
            )

            previous = selected

        next_genre = choose_next_genre(
            current_genre,
            available_genres,
            recent_genres[-3:],
        )

        if next_genre is None:
            break

        recent_genres.append(
            current_genre
        )

        if len(
            recent_genres
        ) > 5:
            recent_genres.pop(0)

        current_genre = next_genre

    # Completar si quedaron pocos tracks.
    if len(session) < songs_per_session:

        remaining = [
            track
            for track in tracks
            if track.get("id")
            not in used_ids
        ]

        rng.shuffle(
            remaining
        )

        for track in remaining:

            if len(session) >= songs_per_session:
                break

            session.append(
                track
            )

    return session[
        :songs_per_session
    ]


# ============================================================
# CREAR VARIAS SESIONES
# ============================================================

def build_sessions(
    tracks,
    songs_per_session,
    session_count,
    mode,
):
    sessions = []

    for index in range(
        session_count
    ):

        session = create_dj_session(
            tracks=tracks,
            songs_per_session=songs_per_session,
            mode=mode,
            seed=(
                int(time.time())
                + index * 7919
                + random.randint(
                    0,
                    999999,
                )
            ),
        )

        if session:
            sessions.append(
                session
            )

    return sessions


# ============================================================
# CREAR PLAYLIST EN SPOTIFY
# ============================================================

def create_playlist(
    token,
    name,
    tracks,
    public=False,
):
    playlist = spotify_request(
        "POST",
        "/me/playlists",
        token,
        json_data={
            "name": name,
            "description": (
                "Creada automáticamente por Spotify Auto-Mix DJ."
            ),
            "public": public,
            "collaborative": False,
        },
    )

    playlist_id = playlist.get(
        "id"
    )

    if not playlist_id:
        raise RuntimeError(
            "Spotify no devolvió el ID de la playlist."
        )

    uris = [
        track.get("uri")
        for track in tracks
        if track.get("uri")
    ]

    # Spotify acepta lotes.
    for start in range(
        0,
        len(uris),
        100,
    ):

        batch = uris[
            start:start + 100
        ]

        spotify_request(
            "POST",
            f"/playlists/{playlist_id}/items",
            token,
            json_data={
                "uris": batch,
            },
        )

    return {
        "name": name,
        "id": playlist_id,
        "tracks": len(uris),
        "url": playlist.get(
            "external_urls",
            {},
        ).get(
            "spotify"
        ),
    }


# ============================================================
# CALLBACK OAUTH
# ============================================================

if not st.session_state.get(
    TOKEN_KEY
):

    if (
        st.query_params.get("code")
        or st.query_params.get("error")
    ):
        process_callback()


# ============================================================
# LOGIN
# ============================================================

if not st.session_state.get(
    TOKEN_KEY
):

    st.title(
        "🎧 Spotify Auto-Mix DJ"
    )

    st.write(
        "Convierte tus Me gusta en sesiones de DJ "
        "con bloques, cambios de género y variedad."
    )

    st.info(
        "La aplicación creará las playlists directamente "
        "en tu cuenta de Spotify."
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
            "No se pudo generar el enlace de Spotify."
        )

    st.stop()


# ============================================================
# TOKEN
# ============================================================

token = get_token()

if not token:

    st.error(
        "La sesión de Spotify no está disponible."
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

try:

    profile = load_profile(
        token
    )

except Exception as exc:

    st.error(
        "No se pudo cargar tu perfil."
    )
    st.exception(exc)
    st.stop()


display_name = (
    profile.get(
        "display_name"
    )
    or profile.get(
        "id"
    )
    or "Usuario"
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title(
        "🎧 Auto-Mix DJ"
    )

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
# HEADER
# ============================================================

st.title(
    "🎧 Spotify Auto-Mix DJ"
)

st.write(
    "La aplicación toma tus canciones y construye "
    "sesiones que cambian de ambiente progresivamente."
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.subheader(
    "⚙️ Configuración del DJ"
)

col1, col2, col3 = st.columns(
    3
)

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
        "Cantidad de playlists",
        min_value=2,
        max_value=10,
        value=5,
        step=1,
    )

with col3:

    mode = st.selectbox(
        "Modo",
        [
            "DJ Profesional",
            "Tarde",
            "Manejo",
            "Fiesta",
        ],
    )


public_playlists = st.checkbox(
    "Crear playlists públicas",
    value=False,
)

estimated_minutes = (
    songs_per_session * 3.5
)

st.caption(
    f"Duración aproximada de cada sesión: "
    f"{estimated_minutes:.0f} minutos."
)


# ============================================================
# CARGAR ME GUSTA
# ============================================================

st.divider()

st.subheader(
    "❤️ Biblioteca"
)

refresh_library = st.button(
    "🔄 Actualizar Mis Me gusta"
)

try:

    liked_tracks = load_liked_tracks(
        token,
        force_reload=refresh_library,
    )

except Exception as exc:

    st.error(
        "No se pudieron cargar tus canciones."
    )
    st.exception(exc)
    st.stop()


if not liked_tracks:

    st.warning(
        "No se encontraron canciones en tus Me gusta."
    )
    st.stop()


col1, col2 = st.columns(
    2
)

with col1:

    st.metric(
        "Canciones",
        len(liked_tracks),
    )

with col2:

    artists_count = len(
        {
            artist_id
            for track
            in liked_tracks
            for artist_id
            in track.get(
                "artist_ids",
                [],
            )
        }
    )

    st.metric(
        "Artistas",
        artists_count,
    )


# ============================================================
# INFORMACIÓN DE USO
# ============================================================

st.info(
    "La primera generación puede tardar más porque la aplicación "
    "necesita analizar los artistas. Después se reutiliza la "
    "información guardada para evitar repetir todas esas consultas."
)


# ============================================================
# CREAR AUTO-MIX
# ============================================================

st.divider()

create_mix = st.button(
    "🔥 GENERAR Y CREAR AUTO-MIX EN SPOTIFY",
    type="primary",
    use_container_width=True,
)


if create_mix:

    try:

        # ----------------------------------------------------
        # 1. Analizar géneros
        # ----------------------------------------------------

        with st.spinner(
            "Analizando géneros y preparando tu biblioteca..."
        ):

            enriched_tracks = enrich_tracks(
                liked_tracks,
                token,
            )


        genre_counts = Counter(
            track.get(
                "genre",
                "Latin",
            )
            for track
            in enriched_tracks
        )


        st.subheader(
            "🎼 Géneros detectados"
        )

        detected_text = " • ".join(
            f"{genre}: {count}"
            for genre, count
            in genre_counts.most_common()
        )

        st.write(
            detected_text
        )


        # ----------------------------------------------------
        # 2. Construir sesiones
        # ----------------------------------------------------

        with st.spinner(
            "Construyendo las sesiones como DJ..."
        ):

            sessions = build_sessions(
                tracks=enriched_tracks,
                songs_per_session=songs_per_session,
                session_count=session_count,
                mode=mode,
            )


        if not sessions:

            raise RuntimeError(
                "No se pudieron construir sesiones."
            )


        # ----------------------------------------------------
        # 3. Crear playlists
        # ----------------------------------------------------

        created_playlists = []

        progress = st.progress(0)
        status = st.empty()


        prefix = SESSION_MODES.get(
            mode,
            SESSION_MODES[
                "DJ Profesional"
            ],
        )["name_prefix"]


        for index, session in enumerate(
            sessions,
            start=1,
        ):

            status.write(
                f"Creando playlist "
                f"{index}/{len(sessions)}..."
            )

            playlist_name = (
                f"{prefix} #{index:02d}"
            )

            created = create_playlist(
                token=token,
                name=playlist_name,
                tracks=session,
                public=public_playlists,
            )

            created_playlists.append(
                created
            )

            progress.progress(
                index / len(sessions)
            )

        progress.empty()
        status.empty()


        st.session_state[
            CREATED_KEY
        ] = created_playlists


        # ----------------------------------------------------
        # 4. Resultado
        # ----------------------------------------------------

        st.divider()

        st.success(
            f"✅ Se crearon "
            f"{len(created_playlists)} playlists "
            f"directamente en Spotify."
        )


        for playlist in created_playlists:

            url = playlist.get(
                "url"
            )

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


    except Exception as exc:

        st.error(
            "No se pudo completar el Auto-Mix."
        )

        st.exception(exc)


# ============================================================
# ÚLTIMAS PLAYLISTS
# ============================================================

last_created = st.session_state.get(
    CREATED_KEY,
    [],
)

if last_created:

    st.divider()

    st.subheader(
        "🎶 Últimas playlists creadas"
    )

    for playlist in last_created:

        url = playlist.get(
            "url"
        )

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
# RESUMEN
# ============================================================

st.divider()

st.caption(
    "Spotify Auto-Mix DJ • Las canciones pueden reutilizarse "
    "entre diferentes sesiones, pero no se repiten dentro "
    "de una misma sesión."
)
