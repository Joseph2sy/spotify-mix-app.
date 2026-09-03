import random
import time
from collections import Counter, defaultdict
from urllib.parse import urlparse

import requests
import streamlit as st
from spotipy.oauth2 import SpotifyOAuth


# ============================================================
# STREAMLIT
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
LIKED_KEY = "liked_tracks"
PLAYLISTS_KEY = "user_playlists"
CACHE_KEY = "artist_genre_cache"
CREATED_KEY = "created_playlists"


# ============================================================
# GÉNEROS DE REFERENCIA
# ============================================================

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
# FAMILIAS MUSICALES
#
# No son playlists separadas.
# Sirven para saber cuándo tiene sentido cambiar
# de ambiente.
# ============================================================

GENRE_FAMILIES = {
    "Reggaeton": "Urbano",
    "Hip Hop": "Urbano",
    "Dance": "Electronica",
    "Pump Up": "Electronica",
    "Rock": "Rock",
    "Pop Rock": "Rock",
    "Latin": "Latino",
    "Cumbia": "Tropical",
    "Salsa": "Tropical",
    "Norteño": "Regional",
    "Bolero": "Romantico",
    "Romantic": "Romantico",
    "Relaxing": "Calma",
    "Reggae spooky": "Alternativo",
}


# ============================================================
# TRANSICIONES
#
# Se usan como preferencias, no como una ruta obligatoria.
# ============================================================

TRANSITIONS = {
    "Reggaeton": [
        "Latin",
        "Cumbia",
        "Dance",
        "Hip Hop",
        "Salsa",
    ],
    "Latin": [
        "Cumbia",
        "Salsa",
        "Reggaeton",
        "Romantic",
        "Norteño",
        "Bolero",
    ],
    "Pop Rock": [
        "Rock",
        "Latin",
        "Hip Hop",
        "Romantic",
        "Dance",
    ],
    "Cumbia": [
        "Latin",
        "Salsa",
        "Norteño",
        "Reggaeton",
        "Romantic",
    ],
    "Hip Hop": [
        "Reggaeton",
        "Dance",
        "Pop Rock",
        "Rock",
        "Latin",
    ],
    "Romantic": [
        "Bolero",
        "Latin",
        "Relaxing",
        "Pop Rock",
        "Cumbia",
    ],
    "Salsa": [
        "Latin",
        "Cumbia",
        "Reggaeton",
        "Dance",
        "Romantic",
    ],
    "Dance": [
        "Pump Up",
        "Reggaeton",
        "Hip Hop",
        "Pop Rock",
        "Latin",
    ],
    "Rock": [
        "Pop Rock",
        "Latin",
        "Hip Hop",
        "Relaxing",
        "Reggaeton",
    ],
    "Norteño": [
        "Cumbia",
        "Latin",
        "Romantic",
        "Bolero",
    ],
    "Bolero": [
        "Romantic",
        "Latin",
        "Relaxing",
        "Cumbia",
    ],
    "Relaxing": [
        "Romantic",
        "Bolero",
        "Pop Rock",
        "Latin",
        "Reggae spooky",
    ],
    "Pump Up": [
        "Dance",
        "Reggaeton",
        "Hip Hop",
        "Rock",
        "Cumbia",
    ],
    "Reggae spooky": [
        "Relaxing",
        "Rock",
        "Latin",
        "Reggaeton",
        "Hip Hop",
    ],
}


# ============================================================
# CONFIGURACIÓN DE SESIONES
# ============================================================

MODES = {
    "DJ Profesional": {
        "min_block": 4,
        "max_block": 7,
        "prefix": "Auto-Mix DJ",
    },
    "Manejo": {
        "min_block": 5,
        "max_block": 8,
        "prefix": "Auto-Mix Manejo",
    },
    "Tarde": {
        "min_block": 5,
        "max_block": 8,
        "prefix": "Auto-Mix Tarde",
    },
    "Fiesta": {
        "min_block": 4,
        "max_block": 6,
        "prefix": "Auto-Mix Fiesta",
    },
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
    "latin pop": "Latin",
    "latin music": "Latin",
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

    "pump up": "Pump Up",
    "workout": "Pump Up",
    "gym": "Pump Up",
    "fitness": "Pump Up",

    "reggae": "Reggae spooky",
    "reggae spooky": "Reggae spooky",
}


# ============================================================
# EXCEPCIÓN 429
# ============================================================

class SpotifyRateLimit(Exception):
    def __init__(self, seconds):
        self.seconds = seconds
        super().__init__(
            "Spotify está limitando las peticiones."
        )


# ============================================================
# OAUTH
# ============================================================

def create_oauth():
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

    except Exception as exc:
        st.error(
            "No se pudieron cargar los Secrets de Spotify."
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
                "La URL OAuth no utiliza HTTPS."
            )

        if parsed.netloc != "accounts.spotify.com":
            raise ValueError(
                "La URL no pertenece a Spotify."
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

        if not token_info.get(
            "access_token"
        ):
            raise ValueError(
                "Spotify no devolvió access_token."
            )

        st.session_state[
            TOKEN_KEY
        ] = token_info

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
            "La sesión de Spotify no pudo renovarse."
        )
        st.exception(exc)

        clear_session()
        return None


# ============================================================
# API
# ============================================================

def spotify_request(
    method,
    endpoint,
    token,
    params=None,
    json_data=None,
):
    try:
        response = requests.request(
            method,
            f"{SPOTIFY_API}{endpoint}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            params=params,
            json=json_data,
            timeout=30,
        )

    except requests.Timeout:
        raise RuntimeError(
            "Spotify tardó demasiado en responder."
        )

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Error de conexión con Spotify: {exc}"
        )

    if response.status_code == 429:
        retry_after = response.headers.get(
            "Retry-After",
            "30",
        )

        try:
            seconds = max(
                1,
                int(float(retry_after)),
            )
        except Exception:
            seconds = 30

        raise SpotifyRateLimit(
            seconds
        )

    if response.status_code == 401:
        raise RuntimeError(
            "La sesión de Spotify expiró."
        )

    if response.status_code == 403:
        raise RuntimeError(
            "Spotify no permite esta operación "
            "con los permisos actuales."
        )

    if response.status_code >= 500:
        raise RuntimeError(
            f"Spotify devolvió el error "
            f"{response.status_code}."
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
    except Exception:
        return {}


# ============================================================
# SESIÓN
# ============================================================

def clear_session():
    for key in [
        TOKEN_KEY,
        PROFILE_KEY,
        LIKED_KEY,
        PLAYLISTS_KEY,
        CREATED_KEY,
    ]:
        st.session_state.pop(
            key,
            None,
        )


def logout():
    clear_session()
    st.query_params.clear()
    st.rerun()


# ============================================================
# PERFIL
# ============================================================

def load_profile(token):
    if PROFILE_KEY in st.session_state:
        return st.session_state[
            PROFILE_KEY
        ]

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
# CARGAR ME GUSTA
# ============================================================

def load_liked_tracks(
    token,
    force=False,
):
    if (
        LIKED_KEY in st.session_state
        and not force
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

            for saved in items:

                track = saved.get(
                    "track"
                )

                if not track:
                    continue

                if track.get(
                    "type"
                ) != "track":
                    continue

                if not track.get(
                    "id"
                ):
                    continue

                artists = track.get(
                    "artists",
                    [],
                )

                tracks.append(
                    {
                        "id": track["id"],
                        "uri": track.get(
                            "uri"
                        ),
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
                f"Cargando canciones: "
                f"{len(tracks)} / {total}"
            )

            if not response.get(
                "next"
            ):
                break

            offset += limit

            time.sleep(0.1)

    finally:
        progress.empty()
        status.empty()

    unique = {}

    for track in tracks:
        unique[
            track["id"]
        ] = track

    result = list(
        unique.values()
    )

    st.session_state[
        LIKED_KEY
    ] = result

    return result


# ============================================================
# PLAYLISTS
# ============================================================

def load_playlists(
    token,
    force=False,
):
    if (
        PLAYLISTS_KEY in st.session_state
        and not force
    ):
        return st.session_state[
            PLAYLISTS_KEY
        ]

    playlists = []

    offset = 0
    limit = 50

    while True:

        response = spotify_request(
            "GET",
            "/me/playlists",
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

        playlists.extend(
            items
        )

        if not response.get(
            "next"
        ):
            break

        offset += limit

        time.sleep(0.1)

    st.session_state[
        PLAYLISTS_KEY
    ] = playlists

    return playlists


def load_playlist_tracks(
    token,
    playlist_id,
):
    tracks = []

    offset = 0
    limit = 100

    while True:

        response = spotify_request(
            "GET",
            f"/playlists/{playlist_id}/items",
            token,
            params={
                "limit": limit,
                "offset": offset,
            },
        )

        for item in response.get(
            "items",
            [],
        ):

            track = item.get(
                "item"
            )

            if not track:
                continue

            if track.get(
                "type"
            ) != "track":
                continue

            if not track.get(
                "id"
            ):
                continue

            artists = track.get(
                "artists",
                [],
            )

            tracks.append(
                {
                    "id": track["id"],
                    "uri": track.get(
                        "uri"
                    ),
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
                }
            )

        if not response.get(
            "next"
        ):
            break

        offset += limit

        time.sleep(0.1)

    unique = {}

    for track in tracks:
        unique[
            track["id"]
        ] = track

    return list(
        unique.values()
    )


# ============================================================
# TEXTO / GÉNERO
# ============================================================

def normalize_text(value):
    return (
        str(value)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def normalize_genre(value):
    text = normalize_text(
        value
    )

    if text in GENRE_ALIASES:
        return GENRE_ALIASES[
            text
        ]

    for alias, canonical in GENRE_ALIASES.items():

        if alias in text:
            return canonical

    return None


def fallback_genre(track):
    text = normalize_text(
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
            ["cumbia"],
            "Cumbia",
        ),
        (
            ["salsa"],
            "Salsa",
        ),
        (
            ["bolero"],
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
                "balada",
                "romantic",
                "romantica",
                "romántica",
            ],
            "Romantic",
        ),
        (
            [
                "relax",
                "chill",
                "ambient",
            ],
            "Relaxing",
        ),
    ]

    for keywords, genre in rules:

        if any(
            keyword in text
            for keyword in keywords
        ):
            return genre

    # Fallback distribuido.
    fallback = [
        "Latin",
        "Pop Rock",
        "Romantic",
        "Rock",
        "Cumbia",
    ]

    value = sum(
        ord(char)
        for char in track.get(
            "id",
            "",
        )
    )

    return fallback[
        value % len(
            fallback
        )
    ]


# ============================================================
# GÉNEROS DE ARTISTAS
# ============================================================

def get_artist_genres(
    token,
    artist_id,
):
    cache = st.session_state.setdefault(
        CACHE_KEY,
        {},
    )

    if artist_id in cache:
        return cache[
            artist_id
        ]

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

        return genres

    except Exception:
        cache[
            artist_id
        ] = []

        return []


# ============================================================
# ENRIQUECER
# ============================================================

def enrich_tracks(
    tracks,
    token,
    max_new_artists=10,
):
    cache = st.session_state.setdefault(
        CACHE_KEY,
        {},
    )

    # Solamente artistas que todavía no conocemos.
    new_artists = []

    seen = set()

    for track in tracks:

        for artist_id in track.get(
            "artist_ids",
            [],
        ):

            if (
                artist_id
                and artist_id not in cache
                and artist_id not in seen
            ):
                seen.add(
                    artist_id
                )

                new_artists.append(
                    artist_id
                )

    # Límite bajo de propósito.
    new_artists = new_artists[
        :max_new_artists
    ]

    if new_artists:

        progress = st.progress(0)
        status = st.empty()

        for index, artist_id in enumerate(
            new_artists,
            start=1,
        ):

            status.write(
                f"Analizando artista "
                f"{index}/{len(new_artists)}"
            )

            try:
                cache[
                    artist_id
                ] = get_artist_genres(
                    token,
                    artist_id,
                )

            except SpotifyRateLimit:
                break

            # Evita una ráfaga.
            time.sleep(1.0)

            progress.progress(
                index
                / len(
                    new_artists
                )
            )

        progress.empty()
        status.empty()

    enriched = []

    for track in tracks:

        all_genres = []

        for artist_id in track.get(
            "artist_ids",
            [],
        ):

            all_genres.extend(
                cache.get(
                    artist_id,
                    [],
                )
            )

        normalized = [
            normalize_genre(
                genre
            )
            for genre
            in all_genres
        ]

        normalized = [
            genre
            for genre
            in normalized
            if genre
        ]

        if normalized:

            counts = Counter(
                normalized
            )

            genre = counts.most_common(
                1
            )[0][0]

        else:

            genre = fallback_genre(
                track
            )

        item = dict(
            track
        )

        item[
            "genre"
        ] = genre

        item[
            "family"
        ] = GENRE_FAMILIES.get(
            genre,
            "Latino",
        )

        enriched.append(
            item
        )

    return enriched


# ============================================================
# AGRUPAR
# ============================================================

def group_by_genre(
    tracks
):
    groups = defaultdict(list)

    for track in tracks:

        groups[
            track.get(
                "genre",
                "Latin",
            )
        ].append(
            track
        )

    return groups


# ============================================================
# SCORE DE TRACK
# ============================================================

def score_track(
    previous,
    candidate,
):
    if previous is None:
        return 0.0

    score = 0.0

    previous_genre = previous.get(
        "genre",
        "Latin",
    )

    candidate_genre = candidate.get(
        "genre",
        "Latin",
    )

    previous_family = previous.get(
        "family",
        "Latino",
    )

    candidate_family = candidate.get(
        "family",
        "Latino",
    )

    # --------------------------------------------------------
    # Mantener el bloque.
    # --------------------------------------------------------

    if (
        previous_genre
        == candidate_genre
    ):
        score += 9

    if (
        previous_family
        == candidate_family
    ):
        score += 4

    # --------------------------------------------------------
    # Cambio de género preparado.
    # --------------------------------------------------------

    transition_list = TRANSITIONS.get(
        previous_genre,
        [],
    )

    if candidate_genre in transition_list:
        score += 7

    # --------------------------------------------------------
    # Evitar mismo artista.
    # --------------------------------------------------------

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
        score -= 10
    else:
        score += 2

    # --------------------------------------------------------
    # Duraciones semejantes.
    # --------------------------------------------------------

    previous_duration = (
        previous.get(
            "duration_ms",
            0,
        )
        or 0
    )

    current_duration = (
        candidate.get(
            "duration_ms",
            0,
        )
        or 0
    )

    if previous_duration and current_duration:

        difference = abs(
            previous_duration
            - current_duration
        ) / 1000

        if difference <= 20:
            score += 3

        elif difference <= 45:
            score += 2

        elif difference <= 90:
            score += 1

        elif difference > 180:
            score -= 2

    # --------------------------------------------------------
    # Variación controlada.
    # --------------------------------------------------------

    score += random.uniform(
        -1.0,
        1.0,
    )

    return score


# ============================================================
# ELEGIR TRACK
# ============================================================

def choose_best_track(
    candidates,
    previous,
):
    if not candidates:
        return None

    ranked = []

    for candidate in candidates:

        score = score_track(
            previous,
            candidate,
        )

        ranked.append(
            (
                score,
                candidate,
            )
        )

    ranked.sort(
        key=lambda value: value[0],
        reverse=True,
    )

    # Elegir entre las mejores para evitar monotonía.
    top = ranked[
        :min(
            6,
            len(ranked),
        )
    ]

    return random.choice(
        top
    )[1]


# ============================================================
# ELEGIR SIGUIENTE BLOQUE
# ============================================================

def choose_next_genre(
    current_genre,
    available_genres,
    recent_genres,
):
    if not available_genres:
        return None

    preferred = TRANSITIONS.get(
        current_genre,
        [],
    )

    candidates = []

    # --------------------------------------------------------
    # Primero transición compatible.
    # --------------------------------------------------------

    for genre in preferred:

        if (
            genre in available_genres
            and genre != current_genre
            and genre not in recent_genres
        ):
            candidates.append(
                genre
            )

    # --------------------------------------------------------
    # Luego géneros frescos.
    # --------------------------------------------------------

    for genre in available_genres:

        if (
            genre != current_genre
            and genre not in recent_genres
            and genre not in candidates
        ):
            candidates.append(
                genre
            )

    # --------------------------------------------------------
    # Último recurso.
    # --------------------------------------------------------

    for genre in available_genres:

        if (
            genre != current_genre
            and genre not in candidates
        ):
            candidates.append(
                genre
            )

    if not candidates:
        return None

    # No queremos saltar aleatoriamente entre todos.
    top = candidates[
        :min(
            5,
            len(candidates),
        )
    ]

    return random.choice(
        top
    )


# ============================================================
# DJ SESSION
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
        for genre, songs
        in groups.items()
        if songs
    ]

    if not available_genres:
        return []

    config = MODES[
        mode
    ]

    # Comenzar por un género con suficiente material.
    possible_starts = [
        genre
        for genre
        in available_genres
        if len(
            groups[genre]
        ) >= 3
    ]

    if not possible_starts:
        possible_starts = available_genres

    current_genre = rng.choice(
        possible_starts
    )

    session = []

    used_ids = set()

    previous = None
    recent_genres = []

    while (
        len(session)
        < songs_per_session
    ):

        candidates = [
            track
            for track
            in groups.get(
                current_genre,
                [],
            )
            if track.get(
                "id"
            ) not in used_ids
        ]

        if not candidates:

            remaining_genres = [
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

            if not remaining_genres:
                break

            current_genre = rng.choice(
                remaining_genres
            )

            candidates = [
                track
                for track
                in groups.get(
                    current_genre,
                    [],
                )
                if track.get(
                    "id"
                ) not in used_ids
            ]

        # ----------------------------------------------------
        # BLOQUE
        # ----------------------------------------------------

        block_size = rng.randint(
            config["min_block"],
            config["max_block"],
        )

        for _ in range(
            block_size
        ):

            if (
                len(session)
                >= songs_per_session
            ):
                break

            candidates = [
                track
                for track
                in groups.get(
                    current_genre,
                    [],
                )
                if track.get(
                    "id"
                ) not in used_ids
            ]

            if not candidates:
                break

            selected = choose_best_track(
                candidates,
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

        # ----------------------------------------------------
        # CAMBIO DE AMBIENTE
        # ----------------------------------------------------

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

    # --------------------------------------------------------
    # Completar
    # --------------------------------------------------------

    if len(session) < songs_per_session:

        remaining = [
            track
            for track
            in tracks
            if track.get(
                "id"
            ) not in used_ids
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
# CREAR SESIONES
# ============================================================

def build_sessions(
    tracks,
    number,
    songs_per_session,
    mode,
):
    sessions = []

    base_seed = int(
        time.time()
    )

    for index in range(
        number
    ):

        session = create_dj_session(
            tracks=tracks,
            songs_per_session=songs_per_session,
            mode=mode,
            seed=(
                base_seed
                + index * 12721
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
    public,
):
    playlist = spotify_request(
        "POST",
        "/me/playlists",
        token,
        json_data={
            "name": name,
            "description": (
                "Spotify Auto-Mix DJ - "
                "sesión organizada por bloques y transiciones."
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
        track["uri"]
        for track in tracks
        if track.get(
            "uri"
        )
    ]

    # Añadir en lotes.
    for start in range(
        0,
        len(uris),
        100,
    ):

        spotify_request(
            "POST",
            f"/playlists/{playlist_id}/items",
            token,
            json_data={
                "uris": uris[
                    start:start + 100
                ]
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
        "Prepara sesiones musicales para que el orden "
        "funcione mejor con la reproducción y mezcla de Spotify."
    )

    st.info(
        "Puedes usar ❤️ Mis Me gusta o cualquier playlist "
        "de tu cuenta."
    )

    auth_url = get_authorize_url()

    if auth_url:
        st.link_button(
            "🎵 Iniciar sesión con Spotify",
            auth_url,
            use_container_width=True,
        )

    st.stop()


# ============================================================
# TOKEN
# ============================================================

token = get_token()

if not token:

    st.error(
        "La sesión de Spotify ya no está disponible."
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
        "No se pudo cargar el perfil."
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
# CABECERA
# ============================================================

st.title(
    "🎧 Spotify Auto-Mix DJ"
)

st.write(
    "Construye sesiones cortas con bloques musicales, "
    "transiciones y variedad de estilos."
)


# ============================================================
# FUENTE
# ============================================================

st.subheader(
    "🎵 Fuente"
)

source = st.radio(
    "Selecciona de dónde saldrán las canciones:",
    [
        "❤️ Mis Me gusta",
        "📁 Una playlist",
    ],
    horizontal=True,
)


source_tracks = []


# ============================================================
# MIS ME GUSTA
# ============================================================

if source == "❤️ Mis Me gusta":

    try:

        source_tracks = load_liked_tracks(
            token
        )

    except SpotifyRateLimit as exc:

        st.error(
            f"Spotify está limitando temporalmente "
            f"las peticiones. Espera aproximadamente "
            f"{exc.seconds} segundos."
        )
        st.stop()

    except Exception as exc:

        st.error(
            "No se pudieron cargar tus Me gusta."
        )
        st.exception(exc)
        st.stop()


# ============================================================
# PLAYLIST
# ============================================================

else:

    try:

        playlists = load_playlists(
            token
        )

    except SpotifyRateLimit as exc:

        st.error(
            f"Spotify está limitando temporalmente "
            f"las peticiones. Espera aproximadamente "
            f"{exc.seconds} segundos."
        )
        st.stop()

    except Exception as exc:

        st.error(
            "No se pudieron cargar tus playlists."
        )
        st.exception(exc)
        st.stop()


    if not playlists:

        st.warning(
            "No se encontraron playlists."
        )
        st.stop()


    options = {}

    for playlist in playlists:

        playlist_id = playlist.get(
            "id"
        )

        if not playlist_id:
            continue

        name = playlist.get(
            "name",
            "Sin nombre",
        )

        options[
            name
        ] = playlist


    selected_name = st.selectbox(
        "Selecciona una playlist",
        list(
            options.keys()
        ),
    )

    selected_playlist = options[
        selected_name
    ]


    if st.button(
        "📥 Cargar playlist",
        type="primary",
        use_container_width=True,
    ):

        try:

            with st.spinner(
                "Cargando canciones..."
            ):

                source_tracks = load_playlist_tracks(
                    token,
                    selected_playlist["id"],
                )

            st.session_state[
                "selected_tracks"
            ] = source_tracks

        except SpotifyRateLimit as exc:

            st.error(
                f"Spotify está limitando temporalmente "
                f"las peticiones. Espera aproximadamente "
                f"{exc.seconds} segundos."
            )

        except Exception as exc:

            st.error(
                "No se pudo cargar la playlist."
            )
            st.exception(exc)

    else:

        source_tracks = st.session_state.get(
            "selected_tracks",
            [],
        )


# ============================================================
# DATOS
# ============================================================

if not source_tracks:

    st.info(
        "Carga una fuente de canciones para comenzar."
    )
    st.stop()


st.success(
    f"{len(source_tracks)} canciones disponibles."
)


# ============================================================
# CONFIGURACIÓN DJ
# ============================================================

st.divider()

st.subheader(
    "🎛️ Sesión DJ"
)

col1, col2, col3 = st.columns(
    3
)

with col1:

    songs_per_session = st.slider(
        "Canciones por sesión",
        15,
        25,
        20,
    )

with col2:

    session_count = st.slider(
        "Número de sesiones",
        2,
        10,
        5,
    )

with col3:

    mode = st.selectbox(
        "Estilo de sesión",
        list(
            MODES.keys()
        ),
    )


public = st.checkbox(
    "Crear playlists públicas",
    value=False,
)


# ============================================================
# GENERAR
# ============================================================

st.divider()

st.subheader(
    "🔥 Crear Auto-Mix"
)

st.caption(
    "El algoritmo mantiene bloques de estilo y hace "
    "los cambios de ambiente de forma menos brusca."
)

generate = st.button(
    "🔥 GENERAR Y CREAR EN SPOTIFY",
    type="primary",
    use_container_width=True,
)


if generate:

    # --------------------------------------------------------
    # Analizar
    # --------------------------------------------------------

    with st.spinner(
        "Preparando tu biblioteca musical..."
    ):

        enriched = enrich_tracks(
            source_tracks,
            token,
            max_new_artists=10,
        )


    # --------------------------------------------------------
    # Distribución
    # --------------------------------------------------------

    counts = Counter(
        track.get(
            "genre",
            "Latin",
        )
        for track
        in enriched
    )


    st.subheader(
        "🎼 Estilos detectados"
    )

    st.write(
        " • ".join(
            f"{genre}: {count}"
            for genre, count
            in counts.most_common()
        )
    )


    # --------------------------------------------------------
    # Crear sesiones
    # --------------------------------------------------------

    with st.spinner(
        "Construyendo las sesiones DJ..."
    ):

        sessions = build_sessions(
            tracks=enriched,
            number=session_count,
            songs_per_session=songs_per_session,
            mode=mode,
        )


    if not sessions:

        st.error(
            "No se pudieron generar las sesiones."
        )
        st.stop()


    # --------------------------------------------------------
    # Vista previa
    # --------------------------------------------------------

    st.subheader(
        "🎧 Recorrido musical"
    )

    for index, session in enumerate(
        sessions,
        start=1,
    ):

        sequence = []

        for track in session:

            genre = track.get(
                "genre",
                "Latin",
            )

            if (
                not sequence
                or sequence[-1] != genre
            ):
                sequence.append(
                    genre
                )

        st.write(
            f"**DJ {index:02d}:** "
            + " → ".join(
                sequence
            )
        )


    # --------------------------------------------------------
    # Crear en Spotify
    # --------------------------------------------------------

    created = []

    prefix = MODES[
        mode
    ][
        "prefix"
    ]

    progress = st.progress(0)

    try:

        for index, session in enumerate(
            sessions,
            start=1,
        ):

            playlist = create_playlist(
                token=token,
                name=f"{prefix} #{index:02d}",
                tracks=session,
                public=public,
            )

            created.append(
                playlist
            )

            progress.progress(
                index / len(sessions)
            )

            time.sleep(1)


    except SpotifyRateLimit as exc:

        st.error(
            f"Spotify limitó temporalmente la creación. "
            f"Espera aproximadamente {exc.seconds} segundos."
        )

    except Exception as exc:

        st.error(
            "Ocurrió un error al crear las playlists."
        )
        st.exception(exc)


    progress.empty()


    # --------------------------------------------------------
    # Resultado
    # --------------------------------------------------------

    if created:

        st.session_state[
            CREATED_KEY
        ] = created

        st.success(
            f"✅ Se crearon {len(created)} playlists "
            f"directamente en Spotify."
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
                    f"✅ {playlist['name']}"
                )


# ============================================================
# ÚLTIMAS PLAYLISTS
# ============================================================

created_playlists = st.session_state.get(
    CREATED_KEY,
    [],
)

if created_playlists:

    st.divider()

    st.subheader(
        "🎶 Playlists creadas"
    )

    for playlist in created_playlists:

        url = playlist.get(
            "url"
        )

        if url:

            st.link_button(
                playlist["name"],
                url,
                use_container_width=True,
            )


# ============================================================
# INFORMACIÓN
# ============================================================

st.divider()

st.caption(
    "El Auto-Mix prepara el orden de las canciones; "
    "la mezcla/fundido propio de Spotify se realiza dentro "
    "del reproductor de Spotify cuando esa función está "
    "disponible para tu cuenta y dispositivo."
)
