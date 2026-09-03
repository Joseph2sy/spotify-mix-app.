import random
import time
from collections import Counter, defaultdict
from urllib.parse import urlparse

import requests
import streamlit as st
from spotipy.oauth2 import SpotifyOAuth


# ============================================================
# CONFIGURACIÓN DE STREAMLIT
# ============================================================

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

# Tus categorías.
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
# TRANSICIONES
# ============================================================
# No es un orden obligatorio.
# Es una red de posibles cambios para que el DJ pueda
# cambiar de ambiente sin hacer saltos absurdos todo el tiempo.
# ============================================================

GENRE_TRANSITIONS = {
    "reggaeton": [
        "Latin",
        "Cumbia",
        "Dance",
        "Hip Hop",
        "Salsa",
        "Pump Up",
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
        "Reggaeton",
    ],

    "cumbia": [
        "Latin",
        "Salsa",
        "Reggaeton",
        "Norteño",
        "Romantic",
        "Dance",
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
        "Salsa",
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
# ALIASES
# ============================================================

GENRE_ALIASES = {
    "reggaeton": "Reggaeton",
    "reggaetón": "Reggaeton",
    "perreo": "Reggaeton",
    "urbano": "Reggaeton",
    "latin": "Latin",
    "latin music": "Latin",
    "latin pop": "Latin",
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
# MODOS
# ============================================================

SESSION_MODES = {
    "DJ Profesional": {
        "prefix": "Auto-Mix DJ",
        "min_block": 3,
        "max_block": 6,
    },
    "Tarde": {
        "prefix": "Auto-Mix Tarde",
        "min_block": 4,
        "max_block": 7,
    },
    "Manejo": {
        "prefix": "Auto-Mix Manejo",
        "min_block": 4,
        "max_block": 7,
    },
    "Fiesta": {
        "prefix": "Auto-Mix Fiesta",
        "min_block": 3,
        "max_block": 5,
    },
}


# ============================================================
# EXCEPCIONES
# ============================================================

class SpotifyRateLimit(Exception):
    def __init__(self, retry_after=30):
        self.retry_after = retry_after
        super().__init__(
            f"Spotify limitó temporalmente las peticiones. "
            f"Espera aproximadamente {retry_after} segundos."
        )


# ============================================================
# OAUTH
# ============================================================

def create_oauth():
    try:
        client_id = st.secrets["SPOTIPY_CLIENT_ID"]
        client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
        redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"]

        if not client_id or not client_secret or not redirect_uri:
            raise ValueError(
                "Faltan las credenciales de Spotify."
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
            "No se pudo configurar la autenticación."
        )
        st.exception(exc)
        return None


def get_authorize_url():
    try:
        oauth = create_oauth()

        if oauth is None:
            return None

        url = oauth.get_authorize_url()
        parsed = urlparse(url)

        if parsed.scheme != "https":
            raise ValueError(
                "La URL OAuth no usa HTTPS."
            )

        if parsed.netloc != "accounts.spotify.com":
            raise ValueError(
                "La URL OAuth no pertenece a Spotify."
            )

        return url

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
                "Spotify no devolvió un token."
            )

        if not token_info.get("access_token"):
            raise ValueError(
                "No se recibió access_token."
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
# SESIÓN
# ============================================================

def clear_session():
    for key in [
        TOKEN_KEY,
        PROFILE_KEY,
        LIKED_KEY,
        ENRICHED_KEY,
        CREATED_KEY,
    ]:
        st.session_state.pop(key, None)

    st.query_params.clear()


def logout():
    clear_session()

    # Conservamos el caché de artistas durante la vida
    # de la aplicación, pero cerramos la sesión.
    st.rerun()


def get_token():
    token_info = st.session_state.get(
        TOKEN_KEY
    )

    if not token_info:
        return None

    try:
        oauth = create_oauth()

        if oauth is None:
            return None

        if oauth.is_token_expired(
            token_info
        ):
            refresh_token = token_info.get(
                "refresh_token"
            )

            if not refresh_token:
                clear_session()
                return None

            token_info = oauth.refresh_access_token(
                refresh_token
            )

            st.session_state[
                TOKEN_KEY
            ] = token_info

        return token_info.get(
            "access_token"
        )

    except Exception as exc:
        st.error(
            "No se pudo renovar la sesión de Spotify."
        )
        st.exception(exc)

        clear_session()
        return None


# ============================================================
# API REQUEST
# ============================================================

def spotify_request(
    method,
    endpoint,
    token,
    params=None,
    json_data=None,
    timeout=25,
):
    url = f"{SPOTIFY_API}{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data,
            timeout=timeout,
        )

    except requests.Timeout:
        raise RuntimeError(
            "Spotify tardó demasiado en responder."
        )

    except requests.RequestException as exc:
        raise RuntimeError(
            f"No se pudo conectar con Spotify: {exc}"
        )

    if response.status_code == 429:
        retry_after = response.headers.get(
            "Retry-After",
            "30",
        )

        try:
            retry_after = max(
                1,
                int(float(retry_after)),
            )
        except Exception:
            retry_after = 30

        raise SpotifyRateLimit(
            retry_after
        )

    if response.status_code >= 500:
        raise RuntimeError(
            f"Spotify está devolviendo un error de servidor "
            f"({response.status_code})."
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

    try:
        return response.json()
    except ValueError:
        return {}


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

    st.session_state[
        PROFILE_KEY
    ] = profile

    return profile


# ============================================================
# CARGAR MIS ME GUSTA
# ============================================================

def load_liked_tracks(
    token,
    force_reload=False,
):
    if (
        LIKED_KEY in st.session_state
        and not force_reload
    ):
        return st.session_state[
            LIKED_KEY
        ]

    tracks = []

    offset = 0
    limit = 50

    progress = st.progress(0)
    status = st.empty()

    try:

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

                track = item.get(
                    "track"
                )

                if not track:
                    continue

                if track.get(
                    "type"
                ) != "track":
                    continue

                track_id = track.get(
                    "id"
                )

                if not track_id:
                    continue

                artists = track.get(
                    "artists",
                    [],
                )

                artist_ids = [
                    artist.get("id")
                    for artist in artists
                    if artist.get("id")
                ]

                artist_names = [
                    artist.get(
                        "name",
                        "Desconocido",
                    )
                    for artist in artists
                ]

                tracks.append(
                    {
                        "id": track_id,
                        "uri": track.get(
                            "uri"
                        ),
                        "name": track.get(
                            "name",
                            "Sin nombre",
                        ),
                        "artist_ids": artist_ids,
                        "artists": artist_names,
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
                    }
                )

            total = response.get(
                "total",
                len(tracks),
            )

            progress.progress(
                min(
                    len(tracks)
                    / max(total, 1),
                    1.0,
                )
            )

            status.write(
                f"Cargando Mis Me gusta: "
                f"{len(tracks)} / {total}"
            )

            if not response.get(
                "next"
            ):
                break

            offset += limit

            # Evita una ráfaga innecesaria de llamadas.
            time.sleep(0.15)

    except SpotifyRateLimit as exc:

        progress.empty()
        status.empty()

        if tracks:
            st.warning(
                f"Spotify limitó temporalmente la carga. "
                f"Se pudieron cargar {len(tracks)} canciones. "
                f"Espera aproximadamente {exc.retry_after} segundos "
                f"antes de actualizar nuevamente."
            )
        else:
            raise

    finally:
        progress.empty()
        status.empty()

    unique = {}

    for track in tracks:
        unique[
            track["id"]
        ] = track

    tracks = list(
        unique.values()
    )

    st.session_state[
        LIKED_KEY
    ] = tracks

    return tracks


# ============================================================
# CACHE DE ARTISTAS
# ============================================================

def get_artist_cache():
    return st.session_state.setdefault(
        ARTIST_GENRES_KEY,
        {},
    )


def scan_artist_genres(
    tracks,
    token,
    max_new_artists=20,
):
    """
    IMPORTANTE:
    Ya no intenta consultar los cientos de artistas
    de una biblioteca completa.

    Analiza únicamente una pequeña cantidad de artistas
    nuevos por ejecución y conserva los resultados.
    """

    cache = get_artist_cache()

    artist_ids = []

    for track in tracks:

        for artist_id in track.get(
            "artist_ids",
            [],
        ):

            if artist_id not in cache:
                artist_ids.append(
                    artist_id
                )

    # Sin duplicados.
    artist_ids = list(
        dict.fromkeys(
            artist_ids
        )
    )

    # Límite intencional para evitar 429.
    artist_ids = artist_ids[
        :max_new_artists
    ]

    if not artist_ids:
        return cache, 0, False

    scanned = 0
    rate_limited = False

    progress = st.progress(0)
    status = st.empty()

    for index, artist_id in enumerate(
        artist_ids,
        start=1,
    ):

        status.write(
            f"Analizando información musical: "
            f"{index}/{len(artist_ids)}"
        )

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

            cache[
                artist_id
            ] = genres

            scanned += 1

            progress.progress(
                index / len(artist_ids)
            )

            # Separación intencional entre peticiones.
            # No hacer 20 requests instantáneos.
            time.sleep(0.8)

        except SpotifyRateLimit:

            rate_limited = True

            cache.setdefault(
                artist_id,
                [],
            )

            break

        except Exception:

            # No dejar que un artista malo
            # rompa todo el análisis.
            cache.setdefault(
                artist_id,
                [],
            )

            scanned += 1

            progress.progress(
                index / len(artist_ids)
            )

            time.sleep(0.5)

    progress.empty()
    status.empty()

    if rate_limited:
        st.warning(
            "Spotify limitó temporalmente el análisis de artistas. "
            "La aplicación continuará usando los géneros ya guardados "
            "y reglas locales para no quedarse bloqueada."
        )

    return cache, scanned, rate_limited


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
    artist_genres,
):
    detected = []

    for raw_genre in artist_genres:

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

        return counts.most_common(
            1
        )[0][0]

    # --------------------------------------------------------
    # Fallback local.
    # --------------------------------------------------------

    combined = normalize_text(
        track.get(
            "name",
            "",
        )
        + " "
        + " ".join(
            track.get(
                "artists",
                [],
            )
        )
    )

    rules = [
        (
            [
                "reggaeton",
                "reggaetón",
                "perreo",
                "urbano",
            ],
            "Reggaeton",
        ),
        (
            [
                "cumbia",
            ],
            "Cumbia",
        ),
        (
            [
                "salsa",
            ],
            "Salsa",
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
                "regional mexicano",
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
                "trap",
            ],
            "Hip Hop",
        ),
        (
            [
                "dance",
                "edm",
                "electronic",
            ],
            "Dance",
        ),
        (
            [
                "reggae",
            ],
            "Reggae spooky",
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
                "romantic",
                "balada",
                "love",
            ],
            "Romantic",
        ),
    ]

    for keywords, genre in rules:

        if any(
            keyword in combined
            for keyword in keywords
        ):
            return genre

    # Fallback distribuido para no colocar
    # todas las canciones desconocidas siempre
    # en la misma categoría.
    possible = [
        "Latin",
        "Pop Rock",
        "Rock",
        "Romantic",
        "Cumbia",
    ]

    # Determinista según el ID para que no cambie
    # en cada rerun.
    number = sum(
        ord(char)
        for char in track.get(
            "id",
            "",
        )
    )

    return possible[
        number % len(possible)
    ]


# ============================================================
# ENRIQUECER
# ============================================================

def enrich_tracks(
    tracks,
    token,
):
    """
    Usa primero los géneros guardados.
    Solo intenta descubrir un número pequeño de artistas
    que todavía no estén en caché.
    """

    cache = get_artist_cache()

    scan_artist_genres(
        tracks,
        token,
        max_new_artists=20,
    )

    enriched = []

    for track in tracks:

        genres = []

        for artist_id in track.get(
            "artist_ids",
            [],
        ):

            genres.extend(
                cache.get(
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
        item["spotify_genres"] = genres

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

def group_by_genre(
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
# SCORE DE TRANSICIÓN
# ============================================================

def transition_score(
    previous,
    candidate,
):
    if previous is None:
        return 0

    score = 0.0

    prev_genre = normalize_text(
        previous.get(
            "genre",
            "",
        )
    )

    cand_genre = normalize_text(
        candidate.get(
            "genre",
            "",
        )
    )

    # Mismo género:
    if prev_genre == cand_genre:
        score += 5

    # Transición conocida:
    possible = [
        normalize_text(
            genre
        )
        for genre
        in GENRE_TRANSITIONS.get(
            prev_genre,
            [],
        )
    ]

    if cand_genre in possible:
        score += 8

    # Evitar mismo artista inmediatamente.
    previous_artists = {
        normalize_text(
            artist
        )
        for artist
        in previous.get(
            "artists",
            [],
        )
    }

    current_artists = {
        normalize_text(
            artist
        )
        for artist
        in candidate.get(
            "artists",
            [],
        )
    }

    if previous_artists & current_artists:
        score -= 6
    else:
        score += 2

    # Duraciones parecidas.
    prev_duration = (
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

    if prev_duration and candidate_duration:

        difference = abs(
            prev_duration
            - candidate_duration
        ) / 1000

        if difference < 30:
            score += 2

        elif difference < 60:
            score += 1

        elif difference > 180:
            score -= 1

    score += random.uniform(
        -1.0,
        1.0,
    )

    return score


# ============================================================
# SIGUIENTE CANCIÓN
# ============================================================

def choose_next_track(
    candidates,
    previous,
):
    if not candidates:
        return None

    scored = []

    for candidate in candidates:

        scored.append(
            (
                transition_score(
                    previous,
                    candidate,
                ),
                candidate,
            )
        )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    top = scored[
        :min(
            6,
            len(scored),
        )
    ]

    return random.choice(
        top
    )[1]


# ============================================================
# SIGUIENTE GÉNERO
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
        normalize_text(
            genre
        ): genre
        for genre
        in available_genres
    }

    preferred_candidates = []

    for key in preferred:

        if key in mapped:

            candidate = mapped[
                key
            ]

            if candidate != current_genre:
                preferred_candidates.append(
                    candidate
                )

    fresh = [
        genre
        for genre
        in available_genres
        if genre not in recent_genres
        and genre != current_genre
    ]

    candidates = []

    candidates.extend(
        preferred_candidates
    )

    candidates.extend(
        genre
        for genre in fresh
        if genre not in candidates
    )

    candidates.extend(
        genre
        for genre
        in available_genres
        if genre != current_genre
        and genre not in candidates
    )

    if not candidates:
        return None

    weights = []

    for genre in candidates:

        if genre in preferred_candidates:
            weights.append(6)

        elif genre in fresh:
            weights.append(3)

        else:
            weights.append(1)

    return random.choices(
        candidates,
        weights=weights,
        k=1,
    )[0]


# ============================================================
# CREAR SESIÓN DJ
# ============================================================

def create_dj_session(
    tracks,
    songs_per_session,
    mode,
    seed,
):
    if not tracks:
        return []

    rng = random.Random(
        seed
    )

    groups = group_by_genre(
        tracks
    )

    available_genres = [
        genre
        for genre,
        songs
        in groups.items()
        if songs
    ]

    if not available_genres:
        return rng.sample(
            tracks,
            min(
                songs_per_session,
                len(tracks),
            ),
        )

    weights = [
        max(
            1,
            len(
                groups[genre]
            ),
        )
        for genre
        in available_genres
    ]

    current_genre = rng.choices(
        available_genres,
        weights=weights,
        k=1,
    )[0]

    config = SESSION_MODES.get(
        mode,
        SESSION_MODES[
            "DJ Profesional"
        ],
    )

    min_block = config[
        "min_block"
    ]

    max_block = config[
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

            alternatives = [
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

            if not alternatives:
                break

            current_genre = rng.choice(
                alternatives
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

            if (
                len(session)
                >= songs_per_session
            ):
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
            recent_genres[-4:],
        )

        if next_genre is None:
            break

        recent_genres.append(
            current_genre
        )

        if len(
            recent_genres
        ) > 6:
            recent_genres.pop(0)

        current_genre = next_genre

    # Completar la sesión.
    if len(session) < songs_per_session:

        remaining = [
            track
            for track
            in tracks
            if track.get("id")
            not in used_ids
        ]

        rng.shuffle(
            remaining
        )

        for track in remaining:

            if (
                len(session)
                >= songs_per_session
            ):
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

    base_seed = int(
        time.time()
    )

    for index in range(
        session_count
    ):

        session = create_dj_session(
            tracks=tracks,
            songs_per_session=songs_per_session,
            mode=mode,
            seed=(
                base_seed
                + index * 9973
            ),
        )

        if session:
            sessions.append(
                session
            )

    return sessions


# ============================================================
# CREAR PLAYLIST
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
                "Creada automáticamente por Spotify Auto-Mix DJ. "
                "Sesión musical con bloques, variedad y transiciones."
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
        track.get(
            "uri"
        )
        for track
        in tracks
        if track.get(
            "uri"
        )
    ]

    uris = list(
        dict.fromkeys(
            uris
        )
    )

    if not uris:
        raise RuntimeError(
            "La sesión no contiene canciones válidas."
        )

    # Spotify permite añadir elementos en lote.
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
        "id": playlist_id,
        "name": name,
        "tracks": len(uris),
        "url": playlist.get(
            "external_urls",
            {},
        ).get(
            "spotify"
        ),
    }


# ============================================================
# INICIALIZAR ESTADO
# ============================================================

if TOKEN_KEY not in st.session_state:
    st.session_state[
        TOKEN_KEY
    ] = None


# ============================================================
# CALLBACK
# ============================================================

if not st.session_state.get(
    TOKEN_KEY
):

    if (
        st.query_params.get(
            "code"
        )
        or st.query_params.get(
            "error"
        )
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
        "con cambios de ambiente y mezcla de géneros."
    )

    st.info(
        "Las playlists se crean directamente en tu cuenta de Spotify."
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
        clear_session()
        st.rerun()

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
        "No se pudo cargar tu perfil de Spotify."
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
    "Tu biblioteca se transforma automáticamente en "
    "sesiones cortas y diferentes."
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.subheader(
    "⚙️ Configuración"
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
        "Modo DJ",
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
    f"Duración aproximada: "
    f"{estimated_minutes:.0f} minutos por sesión."
)


# ============================================================
# BIBLIOTECA
# ============================================================

st.divider()

st.subheader(
    "❤️ Mis Me gusta"
)

refresh = st.button(
    "🔄 Actualizar biblioteca"
)

try:

    liked_tracks = load_liked_tracks(
        token,
        force_reload=refresh,
    )

    # Si actualizamos la biblioteca,
    # el enriquecimiento anterior ya no coincide.
    if refresh:
        st.session_state.pop(
            ENRICHED_KEY,
            None
        )

except SpotifyRateLimit as exc:

    st.error(
        f"Spotify está limitando temporalmente las peticiones. "
        f"Espera aproximadamente {exc.retry_after} segundos "
        f"y vuelve a intentarlo."
    )

    st.stop()

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


artist_count = len(
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


metric1, metric2 = st.columns(
    2
)

with metric1:
    st.metric(
        "Canciones",
        len(liked_tracks),
    )

with metric2:
    st.metric(
        "Artistas",
        artist_count,
    )


# ============================================================
# CACHÉ DE GÉNEROS
# ============================================================

artist_cache = get_artist_cache()

cached_artists = len(
    artist_cache
)

if cached_artists:

    st.caption(
        f"Información musical guardada de "
        f"{cached_artists} artistas. "
        "La aplicación no vuelve a consultarlos."
    )


# ============================================================
# CREAR AUTO MIX
# ============================================================

st.divider()

st.subheader(
    "🔥 Crear Auto-Mix"
)

st.write(
    "La primera ejecución analiza una pequeña cantidad de artistas "
    "y guarda los resultados. Las siguientes sesiones aprovechan "
    "ese caché para evitar bombardear la API."
)


create_mix = st.button(
    "🔥 GENERAR Y CREAR PLAYLISTS EN SPOTIFY",
    type="primary",
    use_container_width=True,
)


if create_mix:

    try:

        # ----------------------------------------------------
        # 1. Analizar solamente artistas nuevos limitados.
        # ----------------------------------------------------

        with st.spinner(
            "Preparando los géneros de tu biblioteca..."
        ):

            enriched_tracks = enrich_tracks(
                liked_tracks,
                token,
            )


        # ----------------------------------------------------
        # 2. Mostrar distribución.
        # ----------------------------------------------------

        genre_counts = Counter(
            track.get(
                "genre",
                "Latin",
            )
            for track
            in enriched_tracks
        )

        st.subheader(
            "🎼 Distribución detectada"
        )

        distribution = " • ".join(
            f"{genre}: {count}"
            for genre, count
            in genre_counts.most_common()
        )

        st.write(
            distribution
        )


        # ----------------------------------------------------
        # 3. Construir sesiones.
        # ----------------------------------------------------

        with st.spinner(
            "Construyendo tus sesiones como DJ..."
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
        # 4. Crear playlists.
        # ----------------------------------------------------

        prefix = SESSION_MODES.get(
            mode,
            SESSION_MODES[
                "DJ Profesional"
            ],
        )["prefix"]

        created = []

        progress = st.progress(0)
        status = st.empty()

        for index, session in enumerate(
            sessions,
            start=1,
        ):

            status.write(
                f"Creando playlist "
                f"{index}/{len(sessions)}..."
            )

            playlist = create_playlist(
                token=token,
                name=(
                    f"{prefix} #{index:02d}"
                ),
                tracks=session,
                public=public_playlists,
            )

            created.append(
                playlist
            )

            progress.progress(
                index / len(sessions)
            )

            # Pequeña separación entre creación de playlists.
            time.sleep(0.5)

        progress.empty()
        status.empty()

        st.session_state[
            CREATED_KEY
        ] = created

        # ----------------------------------------------------
        # 5. Resultado.
        # ----------------------------------------------------

        st.divider()

        st.success(
            f"✅ Se crearon "
            f"{len(created)} playlists directamente "
            f"en Spotify."
        )

        for playlist in created:

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


    except SpotifyRateLimit as exc:

        st.error(
            f"Spotify volvió a limitar las peticiones. "
            f"Espera aproximadamente {exc.retry_after} segundos "
            f"y vuelve a ejecutar la creación."
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
        "🎶 Playlists creadas"
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
# INFORMACIÓN
# ============================================================

st.divider()

st.caption(
    "Spotify Auto-Mix DJ • Las canciones pueden reutilizarse "
    "entre sesiones diferentes, pero no se repiten dentro "
    "de una misma sesión."
)
