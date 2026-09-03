import json
import math
import os
import random
import time
from collections import Counter, defaultdict
from datetime import datetime
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

# Nuevas claves de session_state (motor / IA / historial / config)
SELECTED_TRACKS_KEY = "selected_tracks"
ENRICHED_KEY = "enriched_tracks_cache"
ENRICHED_SIGNATURE_KEY = "enriched_tracks_signature"
DJ_CONFIG_KEY = "dj_config"
HISTORY_KEY = "automix_history"
LAST_SESSIONS_KEY = "last_dj_sessions"
LAST_RUN_META_KEY = "last_run_meta"

HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "automix_history.json",
)


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
    "Reggaeton": ["Latin", "Cumbia", "Dance", "Hip Hop", "Salsa"],
    "Latin": ["Cumbia", "Salsa", "Reggaeton", "Romantic", "Norteño", "Bolero"],
    "Pop Rock": ["Rock", "Latin", "Hip Hop", "Romantic", "Dance"],
    "Cumbia": ["Latin", "Salsa", "Norteño", "Reggaeton", "Romantic"],
    "Hip Hop": ["Reggaeton", "Dance", "Pop Rock", "Rock", "Latin"],
    "Romantic": ["Bolero", "Latin", "Relaxing", "Pop Rock", "Cumbia"],
    "Salsa": ["Latin", "Cumbia", "Reggaeton", "Dance", "Romantic"],
    "Dance": ["Pump Up", "Reggaeton", "Hip Hop", "Pop Rock", "Latin"],
    "Rock": ["Pop Rock", "Latin", "Hip Hop", "Relaxing", "Reggaeton"],
    "Norteño": ["Cumbia", "Latin", "Romantic", "Bolero"],
    "Bolero": ["Romantic", "Latin", "Relaxing", "Cumbia"],
    "Relaxing": ["Romantic", "Bolero", "Pop Rock", "Latin", "Reggae spooky"],
    "Pump Up": ["Dance", "Reggaeton", "Hip Hop", "Rock", "Cumbia"],
    "Reggae spooky": ["Relaxing", "Rock", "Latin", "Reggaeton", "Hip Hop"],
}


# ============================================================
# HEURÍSTICA DE IDIOMA (aproximada, basada en familia)
#
# Spotify no entrega idioma por canción. Esto es solo una
# señal aproximada derivada de la familia musical, usada
# únicamente como un pequeño bonus de compatibilidad, nunca
# como un dato garantizado.
# ============================================================

SPANISH_LEANING_FAMILIES = {
    "Latino",
    "Tropical",
    "Regional",
    "Romantico",
}


def approx_language(family):
    if family in SPANISH_LEANING_FAMILIES:
        return "es"
    return "unknown"


# ============================================================
# CONFIGURACIÓN DE SESIONES (bloques por modo)
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

VARIETY_LEVELS = ["Bajo", "Medio", "Alto"]
INTENSITY_LEVELS = ["Suave", "Moderado", "Atrevido"]

# Cuántas de las mejores candidatas se barajan al elegir canción.
VARIETY_POOL_SIZE = {
    "Bajo": 3,
    "Medio": 6,
    "Alto": 10,
}

# Cuántos géneros "frescos" se consideran al elegir el siguiente bloque.
VARIETY_GENRE_POOL = {
    "Bajo": 2,
    "Medio": 4,
    "Alto": 7,
}

# Ajuste de tamaño de bloque según intensidad de cambio.
INTENSITY_BLOCK_ADJUST = {
    "Suave": 2,
    "Moderado": 0,
    "Atrevido": -1,
}

# Probabilidad de aceptar un salto grande de familia sin puente.
INTENSITY_JUMP_TOLERANCE = {
    "Suave": 0.10,
    "Moderado": 0.30,
    "Atrevido": 0.55,
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
# MOTOR DE TRANSICIÓN — CONSTANTES DE SCORING
#
# Todos los valores son ajustables fácilmente aquí.
# ============================================================

SCORE_WEIGHTS = {
    "same_genre": 10,
    "same_family": 8,
    "different_artist": 5,
    "duration_compatible": 2,
    "language_compatible": 2,
    "known_transition": 8,
    "bridge_track": 10,
    "recent_repeat_artist": -10,
    "same_artist_consecutive": -20,
    "extreme_change_no_bridge": -15,
    "random_jitter": 1.5,
}

# Tamaño de la ventana de "artistas recientes" para penalizar repetición.
RECENT_ARTIST_WINDOW = 4
# Mínimo de estilos distintos detectados en un track para considerarlo puente.
BRIDGE_MIN_GENRES = 2


# ============================================================
# EXCEPCIÓN 429
# ============================================================

class SpotifyRateLimit(Exception):
    def __init__(self, seconds):
        self.seconds = seconds
        super().__init__("Spotify está limitando las peticiones.")


# ============================================================
# OAUTH  (sin cambios respecto al proyecto original)
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
        st.error("No se pudieron cargar los Secrets de Spotify.")
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
            raise ValueError("La URL OAuth no utiliza HTTPS.")

        if parsed.netloc != "accounts.spotify.com":
            raise ValueError("La URL no pertenece a Spotify.")

        return url

    except Exception as exc:
        st.error("No se pudo generar el enlace de Spotify.")
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

        if not token_info:
            raise ValueError("Spotify no devolvió un token.")

        if not token_info.get("access_token"):
            raise ValueError("Spotify no devolvió access_token.")

        st.session_state[TOKEN_KEY] = token_info

        st.query_params.clear()
        st.rerun()

    except Exception as exc:
        st.error("No se pudo completar el inicio de sesión.")
        st.exception(exc)


# ============================================================
# TOKEN  (sin cambios)
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
                clear_session()
                return None

            token_info = oauth.refresh_access_token(refresh_token)

            st.session_state[TOKEN_KEY] = token_info

        return token_info.get("access_token")

    except Exception as exc:
        st.error("La sesión de Spotify no pudo renovarse.")
        st.exception(exc)

        clear_session()
        return None


# ============================================================
# API  (sin cambios)
# ============================================================

def spotify_request(method, endpoint, token, params=None, json_data=None):
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
        raise RuntimeError("Spotify tardó demasiado en responder.")

    except requests.RequestException as exc:
        raise RuntimeError(f"Error de conexión con Spotify: {exc}")

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "30")

        try:
            seconds = max(1, int(float(retry_after)))
        except Exception:
            seconds = 30

        raise SpotifyRateLimit(seconds)

    if response.status_code == 401:
        raise RuntimeError("La sesión de Spotify expiró.")

    if response.status_code == 403:
        raise RuntimeError(
            "Spotify no permite esta operación con los permisos actuales."
        )

    if response.status_code >= 500:
        raise RuntimeError(f"Spotify devolvió el error {response.status_code}.")

    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text

        raise RuntimeError(f"Spotify API {response.status_code}: {detail}")

    if not response.content:
        return {}

    try:
        return response.json()
    except Exception:
        return {}


# ============================================================
# SESIÓN  (sin cambios en lo esencial)
# ============================================================

def clear_session():
    for key in [
        TOKEN_KEY,
        PROFILE_KEY,
        LIKED_KEY,
        PLAYLISTS_KEY,
        CREATED_KEY,
        SELECTED_TRACKS_KEY,
        ENRICHED_KEY,
        ENRICHED_SIGNATURE_KEY,
        LAST_SESSIONS_KEY,
        LAST_RUN_META_KEY,
    ]:
        st.session_state.pop(key, None)


def logout():
    clear_session()
    st.query_params.clear()
    st.rerun()


# ============================================================
# PERFIL  (sin cambios)
# ============================================================

def load_profile(token):
    if PROFILE_KEY in st.session_state:
        return st.session_state[PROFILE_KEY]

    profile = spotify_request("GET", "/me", token)

    st.session_state[PROFILE_KEY] = profile

    return profile


# ============================================================
# CARGAR ME GUSTA  (sin cambios)
# ============================================================

def load_liked_tracks(token, force=False):
    if LIKED_KEY in st.session_state and not force:
        return st.session_state[LIKED_KEY]

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
                params={"limit": limit, "offset": offset},
            )

            items = response.get("items", [])

            for saved in items:
                track = saved.get("track")

                if not track:
                    continue

                if track.get("type") != "track":
                    continue

                if not track.get("id"):
                    continue

                artists = track.get("artists", [])

                tracks.append(
                    {
                        "id": track["id"],
                        "uri": track.get("uri"),
                        "name": track.get("name", "Sin nombre"),
                        "artist_ids": [
                            artist.get("id")
                            for artist in artists
                            if artist.get("id")
                        ],
                        "artists": [
                            artist.get("name", "Desconocido")
                            for artist in artists
                        ],
                        "album": track.get("album", {}).get(
                            "name", "Sin álbum"
                        ),
                        "duration_ms": track.get("duration_ms", 0),
                    }
                )

            total = response.get("total", len(tracks))

            progress.progress(min(len(tracks) / max(total, 1), 1.0))

            status.write(f"Cargando canciones: {len(tracks)} / {total}")

            if not response.get("next"):
                break

            offset += limit

            time.sleep(0.1)

    finally:
        progress.empty()
        status.empty()

    unique = {}

    for track in tracks:
        unique[track["id"]] = track

    result = list(unique.values())

    st.session_state[LIKED_KEY] = result

    return result


# ============================================================
# PLAYLISTS  (sin cambios)
# ============================================================

def load_playlists(token, force=False):
    if PLAYLISTS_KEY in st.session_state and not force:
        return st.session_state[PLAYLISTS_KEY]

    playlists = []

    offset = 0
    limit = 50

    while True:
        response = spotify_request(
            "GET",
            "/me/playlists",
            token,
            params={"limit": limit, "offset": offset},
        )

        items = response.get("items", [])

        playlists.extend(items)

        if not response.get("next"):
            break

        offset += limit

        time.sleep(0.1)

    st.session_state[PLAYLISTS_KEY] = playlists

    return playlists


def load_playlist_tracks(token, playlist_id):
    tracks = []

    offset = 0
    limit = 100

    while True:
        response = spotify_request(
            "GET",
            f"/playlists/{playlist_id}/items",
            token,
            params={"limit": limit, "offset": offset},
        )

        for item in response.get("items", []):
            track = item.get("item")

            if not track:
                continue

            if track.get("type") != "track":
                continue

            if not track.get("id"):
                continue

            artists = track.get("artists", [])

            tracks.append(
                {
                    "id": track["id"],
                    "uri": track.get("uri"),
                    "name": track.get("name", "Sin nombre"),
                    "artist_ids": [
                        artist.get("id")
                        for artist in artists
                        if artist.get("id")
                    ],
                    "artists": [
                        artist.get("name", "Desconocido") for artist in artists
                    ],
                    "album": track.get("album", {}).get("name", "Sin álbum"),
                    "duration_ms": track.get("duration_ms", 0),
                }
            )

        if not response.get("next"):
            break

        offset += limit

        time.sleep(0.1)

    unique = {}

    for track in tracks:
        unique[track["id"]] = track

    return list(unique.values())


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
    text = normalize_text(value)

    if text in GENRE_ALIASES:
        return GENRE_ALIASES[text]

    for alias, canonical in GENRE_ALIASES.items():
        if alias in text:
            return canonical

    return None


def fallback_genre(track):
    text = normalize_text(
        track.get("name", "") + " " + " ".join(track.get("artists", []))
    )

    rules = [
        (["reggaeton", "reggaetón", "perreo", "urbano"], "Reggaeton"),
        (["cumbia"], "Cumbia"),
        (["salsa"], "Salsa"),
        (["bolero"], "Bolero"),
        (["norteno", "norteño", "regional mexicano"], "Norteño"),
        (["rock"], "Rock"),
        (["rap", "hip hop", "hip-hop", "trap"], "Hip Hop"),
        (["dance", "edm", "electronic"], "Dance"),
        (["reggae"], "Reggae spooky"),
        (["balada", "romantic", "romantica", "romántica"], "Romantic"),
        (["relax", "chill", "ambient"], "Relaxing"),
    ]

    for keywords, genre in rules:
        if any(keyword in text for keyword in keywords):
            return genre

    fallback = ["Latin", "Pop Rock", "Romantic", "Rock", "Cumbia"]

    value = sum(ord(char) for char in track.get("id", ""))

    return fallback[value % len(fallback)]


# ============================================================
# GÉNEROS DE ARTISTAS
# ============================================================

def get_artist_genres(token, artist_id):
    cache = st.session_state.setdefault(CACHE_KEY, {})

    if artist_id in cache:
        return cache[artist_id]

    try:
        artist = spotify_request("GET", f"/artists/{artist_id}", token)

        genres = artist.get("genres", []) or []

        cache[artist_id] = genres

        return genres

    except Exception:
        cache[artist_id] = []

        return []


# ============================================================
# ENRIQUECER
#
# Se conserva la lógica original (genre / family por track) y
# se añade:
#   - possible_genres: TODOS los estilos canónicos detectados
#     entre los tags de los artistas (no solo el mayoritario),
#     usados por el motor de puentes.
#   - language: heurística aproximada basada en familia.
# ============================================================

def enrich_tracks(tracks, token, max_new_artists=10):
    cache = st.session_state.setdefault(CACHE_KEY, {})

    new_artists = []
    seen = set()

    for track in tracks:
        for artist_id in track.get("artist_ids", []):
            if artist_id and artist_id not in cache and artist_id not in seen:
                seen.add(artist_id)
                new_artists.append(artist_id)

    new_artists = new_artists[:max_new_artists]

    if new_artists:
        progress = st.progress(0)
        status = st.empty()

        for index, artist_id in enumerate(new_artists, start=1):
            status.write(f"Analizando artista {index}/{len(new_artists)}")

            try:
                cache[artist_id] = get_artist_genres(token, artist_id)
            except SpotifyRateLimit:
                break

            time.sleep(1.0)

            progress.progress(index / len(new_artists))

        progress.empty()
        status.empty()

    enriched = []

    for track in tracks:
        all_genres = []

        for artist_id in track.get("artist_ids", []):
            all_genres.extend(cache.get(artist_id, []))

        normalized = [normalize_genre(genre) for genre in all_genres]
        normalized = [genre for genre in normalized if genre]

        possible_genres = sorted(set(normalized))

        if normalized:
            counts = Counter(normalized)
            genre = counts.most_common(1)[0][0]
        else:
            genre = fallback_genre(track)
            possible_genres = [genre]

        family = GENRE_FAMILIES.get(genre, "Latino")

        item = dict(track)
        item["genre"] = genre
        item["family"] = family
        item["possible_genres"] = possible_genres
        item["is_bridge_candidate"] = len(possible_genres) >= BRIDGE_MIN_GENRES
        item["language"] = approx_language(family)

        enriched.append(item)

    return enriched


def get_enriched_tracks(tracks, token):
    """Cachea el enriquecimiento en session_state para evitar
    volver a golpear la API de Spotify en cada rerun / cada página."""

    signature = (len(tracks), tracks[0]["id"] if tracks else None,
                 tracks[-1]["id"] if tracks else None)

    if (
        st.session_state.get(ENRICHED_SIGNATURE_KEY) == signature
        and ENRICHED_KEY in st.session_state
    ):
        return st.session_state[ENRICHED_KEY]

    enriched = enrich_tracks(tracks, token, max_new_artists=10)

    st.session_state[ENRICHED_KEY] = enriched
    st.session_state[ENRICHED_SIGNATURE_KEY] = signature

    return enriched


# ============================================================
# AGRUPAR
# ============================================================

def group_by_genre(tracks):
    groups = defaultdict(list)

    for track in tracks:
        groups[track.get("genre", "Latin")].append(track)

    return groups


# ============================================================
# PERFIL MUSICAL (music_profile)
# ============================================================

def build_music_profile(enriched_tracks):
    total_tracks = len(enriched_tracks)

    genre_counts = Counter(t.get("genre", "Latin") for t in enriched_tracks)

    artist_counts = Counter()
    for track in enriched_tracks:
        for artist in track.get("artists", []):
            artist_counts[artist] += 1

    total_artists = len(artist_counts)

    if total_tracks > 0:
        unique_ratio = total_artists / total_tracks
    else:
        unique_ratio = 0.0

    # Diversidad por entropía normalizada de géneros (0 = monótono, 1 = muy diverso).
    diversity = 0.0
    if total_tracks > 0 and len(genre_counts) > 1:
        entropy = 0.0
        for count in genre_counts.values():
            p = count / total_tracks
            entropy -= p * math.log(p, 2)
        max_entropy = math.log(len(genre_counts), 2)
        diversity = entropy / max_entropy if max_entropy > 0 else 0.0

    predominant = [g for g, _ in genre_counts.most_common(3)]
    secondary = [g for g, _ in genre_counts.most_common(8)[3:8]]

    available_genres = set(genre_counts.keys())

    relations = {}
    for genre in available_genres:
        compatible = [
            g for g in TRANSITIONS.get(genre, []) if g in available_genres
        ]
        if compatible:
            relations[genre] = compatible

    bridge_tracks = sorted(
        (t for t in enriched_tracks if t.get("is_bridge_candidate")),
        key=lambda t: len(t.get("possible_genres", [])),
        reverse=True,
    )[:15]

    return {
        "total_tracks": total_tracks,
        "total_artists": total_artists,
        "genre_counts": genre_counts,
        "artist_counts": artist_counts,
        "unique_artist_ratio": unique_ratio,
        "diversity": diversity,
        "predominant_styles": predominant,
        "secondary_styles": secondary,
        "genre_relations": relations,
        "bridge_tracks": bridge_tracks,
        "available_genres": sorted(available_genres),
    }


# ============================================================
# MOTOR DE TRANSICIÓN (transition_engine)
# ============================================================

def is_known_transition(previous_genre, candidate_genre, possible_genres=None):
    if candidate_genre in TRANSITIONS.get(previous_genre, []):
        return True

    if possible_genres:
        for genre in possible_genres:
            if genre in TRANSITIONS.get(previous_genre, []):
                return True

    return False


def compute_transition_score(previous, candidate, context):
    """context: dict con recent_artists (set), recent_genres (list),
    needs_bridge (bool), rng (random.Random)."""

    weights = context.get("weights", SCORE_WEIGHTS)
    rng = context.get("rng", random)

    if previous is None:
        return rng.uniform(0, weights["random_jitter"])

    score = 0.0

    previous_genre = previous.get("genre", "Latin")
    candidate_genre = candidate.get("genre", "Latin")

    previous_family = previous.get("family", "Latino")
    candidate_family = candidate.get("family", "Latino")

    # Continuidad de bloque.
    if previous_genre == candidate_genre:
        score += weights["same_genre"]

    if previous_family == candidate_family:
        score += weights["same_family"]

    # Transición de género "conocida" (incluye estilos secundarios del track).
    if is_known_transition(
        previous_genre, candidate_genre, candidate.get("possible_genres")
    ):
        score += weights["known_transition"]

    # Bonus si la candidata puede actuar como puente entre ambos mundos.
    if candidate.get("is_bridge_candidate"):
        possible = set(candidate.get("possible_genres", []))
        if previous_genre in possible or candidate_genre in possible:
            score += weights["bridge_track"]

    # Diferente artista.
    previous_artists = {normalize_text(a) for a in previous.get("artists", [])}
    current_artists = {normalize_text(a) for a in candidate.get("artists", [])}

    if previous_artists & current_artists:
        score += weights["same_artist_consecutive"]
    else:
        score += weights["different_artist"]

    recent_artists = context.get("recent_artists", set())
    if current_artists & recent_artists:
        score += weights["recent_repeat_artist"]

    # Duraciones semejantes.
    previous_duration = previous.get("duration_ms", 0) or 0
    current_duration = candidate.get("duration_ms", 0) or 0

    if previous_duration and current_duration:
        difference = abs(previous_duration - current_duration) / 1000

        if difference <= 30:
            score += weights["duration_compatible"]
        elif difference <= 75:
            score += weights["duration_compatible"] / 2

    # Idioma aproximado.
    previous_lang = previous.get("language", "unknown")
    candidate_lang = candidate.get("language", "unknown")

    if (
        previous_lang != "unknown"
        and candidate_lang != "unknown"
        and previous_lang == candidate_lang
    ):
        score += weights["language_compatible"]

    # Cambio extremo de familia sin puente disponible en esta transición.
    if (
        previous_family != candidate_family
        and not is_known_transition(
            previous_genre, candidate_genre, candidate.get("possible_genres")
        )
        and not candidate.get("is_bridge_candidate")
    ):
        score += weights["extreme_change_no_bridge"]

    # Pequeña aleatoriedad para que cada sesión sea distinta.
    score += rng.uniform(-weights["random_jitter"], weights["random_jitter"])

    return score


def choose_best_track(candidates, previous, context):
    if not candidates:
        return None

    rng = context.get("rng", random)

    ranked = [
        (compute_transition_score(previous, candidate, context), candidate)
        for candidate in candidates
    ]

    ranked.sort(key=lambda value: value[0], reverse=True)

    pool_size = context.get("pool_size", 6)
    top = ranked[: min(pool_size, len(ranked))]

    return rng.choice(top)[1]


# ============================================================
# MOTOR DE SIGUIENTE GÉNERO (bloques)
# ============================================================

def choose_next_genre(current_genre, available_genres, recent_genres, context):
    if not available_genres:
        return None

    rng = context.get("rng", random)
    genre_pool_size = context.get("genre_pool_size", 4)

    preferred = TRANSITIONS.get(current_genre, [])

    candidates = []

    for genre in preferred:
        if (
            genre in available_genres
            and genre != current_genre
            and genre not in recent_genres
        ):
            candidates.append(genre)

    for genre in available_genres:
        if (
            genre != current_genre
            and genre not in recent_genres
            and genre not in candidates
        ):
            candidates.append(genre)

    for genre in available_genres:
        if genre != current_genre and genre not in candidates:
            candidates.append(genre)

    if not candidates:
        return None

    top = candidates[: min(genre_pool_size, len(candidates))]

    return rng.choice(top)


# ============================================================
# MOTOR DE PUENTES (bridge_engine)
# ============================================================

def find_bridge_track(groups, used_ids, from_genre, to_genre, recent_artists, rng):
    """Busca una canción, aún no usada, cuyos estilos detectados
    conecten from_genre y to_genre (o al menos toque uno de los dos
    de forma que suavice el salto)."""

    both = []
    partial = []

    for genre_key, tracks in groups.items():
        for track in tracks:
            if track.get("id") in used_ids:
                continue

            if not track.get("is_bridge_candidate"):
                continue

            possible = set(track.get("possible_genres", []))
            artists = {normalize_text(a) for a in track.get("artists", [])}

            if artists & recent_artists:
                continue

            if from_genre in possible and to_genre in possible:
                both.append(track)
            elif from_genre in possible or to_genre in possible:
                partial.append(track)

    if both:
        return rng.choice(both)

    if partial:
        return rng.choice(partial)

    return None


# ============================================================
# CAPA IA OPCIONAL (ai_engine)
#
# Totalmente opcional. Si no hay OPENAI_API_KEY en st.secrets,
# la aplicación sigue funcionando con el motor local, sin
# ningún error visible al usuario.
# ============================================================

def get_openai_key():
    try:
        return st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return None


def ai_suggest_genre_order(available_genres, genre_counts, mode, variety, intensity):
    """Le pide a un modelo externo (opcional) un orden sugerido de
    bloques de género para la sesión, basado ÚNICAMENTE en metadatos
    agregados (nombres de género y conteos). Nunca se envían datos
    de usuario, tokens ni claves de Spotify.

    Devuelve una lista de géneros válidos, o None si no hay IA
    disponible o la respuesta no es utilizable."""

    api_key = get_openai_key()

    if not api_key:
        return None

    try:
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres un DJ experto en mezclar géneros latinos y "
                        "urbanos. Respondes ÚNICAMENTE con JSON: una lista "
                        "de strings con un orden sugerido de géneros para "
                        "una sesión, usando solo géneros de la lista dada."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "generos_disponibles": available_genres,
                            "conteo_por_genero": genre_counts,
                            "modo": mode,
                            "variedad": variety,
                            "intensidad_de_cambio": intensity,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.7,
            "max_tokens": 300,
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )

        if response.status_code != 200:
            return None

        data = response.json()

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        content = content.strip()

        if content.startswith("```"):
            content = content.strip("`")
            content = content.replace("json", "", 1).strip()

        suggested = json.loads(content)

        if not isinstance(suggested, list):
            return None

        valid = [g for g in suggested if g in available_genres]

        return valid or None

    except Exception:
        # La IA es una capa adicional opcional: cualquier fallo
        # cae de vuelta al motor local sin romper la aplicación.
        return None


# ============================================================
# DJ SESSION ENGINE
# ============================================================

def get_block_size(mode, intensity, rng):
    config = MODES[mode]
    adjust = INTENSITY_BLOCK_ADJUST.get(intensity, 0)

    min_block = max(2, config["min_block"] + adjust)
    max_block = max(min_block, config["max_block"] + adjust)

    return rng.randint(min_block, max_block)


def create_dj_session(
    tracks,
    songs_per_session,
    mode,
    variety,
    intensity,
    seed,
    global_used_ids,
    respect_global_used,
    ai_genre_order=None,
):
    if not tracks:
        return []

    rng = random.Random(seed)

    groups = group_by_genre(tracks)

    available_genres = [g for g, songs in groups.items() if songs]

    if not available_genres:
        return []

    context = {
        "rng": rng,
        "weights": SCORE_WEIGHTS,
        "pool_size": VARIETY_POOL_SIZE.get(variety, 6),
        "genre_pool_size": VARIETY_GENRE_POOL.get(variety, 4),
    }

    jump_tolerance = INTENSITY_JUMP_TOLERANCE.get(intensity, 0.3)

    def is_used(track_id):
        if track_id in used_ids:
            return True
        if respect_global_used and track_id in global_used_ids:
            return True
        return False

    # Punto de partida: preferimos un género con material suficiente.
    possible_starts = [g for g in available_genres if len(groups[g]) >= 3]
    if not possible_starts:
        possible_starts = available_genres

    if ai_genre_order:
        starts_from_ai = [g for g in ai_genre_order if g in possible_starts]
        current_genre = starts_from_ai[0] if starts_from_ai else rng.choice(possible_starts)
        ai_queue = [g for g in ai_genre_order if g != current_genre]
    else:
        current_genre = rng.choice(possible_starts)
        ai_queue = []

    session = []
    session_roles = []  # "regular" | "puente", paralelo a session
    used_ids = set()
    previous = None
    recent_genres = []
    recent_artists_window = []

    while len(session) < songs_per_session:

        remaining_in_genre = [
            t for t in groups.get(current_genre, []) if not is_used(t.get("id"))
        ]

        if not remaining_in_genre:
            remaining_genres = [
                g
                for g in available_genres
                if any(not is_used(t.get("id")) for t in groups.get(g, []))
            ]

            if not remaining_genres:
                break

            current_genre = rng.choice(remaining_genres)

        block_size = get_block_size(mode, intensity, rng)

        for _ in range(block_size):
            if len(session) >= songs_per_session:
                break

            candidates = [
                t for t in groups.get(current_genre, []) if not is_used(t.get("id"))
            ]

            if not candidates:
                break

            context["recent_artists"] = set(recent_artists_window[-RECENT_ARTIST_WINDOW:])

            selected = choose_best_track(candidates, previous, context)

            if selected is None:
                break

            session.append(selected)
            session_roles.append("regular")
            used_ids.add(selected["id"])

            for artist in selected.get("artists", []):
                recent_artists_window.append(normalize_text(artist))

            previous = selected

        if len(session) >= songs_per_session:
            break

        # --------------------------------------------------------
        # Elegir el siguiente género (bloque).
        # --------------------------------------------------------

        next_genre = None

        if ai_queue:
            for candidate_genre in list(ai_queue):
                if (
                    candidate_genre in available_genres
                    and candidate_genre != current_genre
                    and any(
                        not is_used(t.get("id"))
                        for t in groups.get(candidate_genre, [])
                    )
                ):
                    next_genre = candidate_genre
                    ai_queue.remove(candidate_genre)
                    break

        if next_genre is None:
            next_genre = choose_next_genre(
                current_genre, available_genres, recent_genres[-3:], context
            )

        if next_genre is None:
            break

        # --------------------------------------------------------
        # ¿Hace falta una canción puente?
        # --------------------------------------------------------

        previous_family = GENRE_FAMILIES.get(current_genre, "Latino")
        next_family = GENRE_FAMILIES.get(next_genre, "Latino")

        big_jump = (
            previous_family != next_family
            and next_genre not in TRANSITIONS.get(current_genre, [])
        )

        if big_jump and len(session) < songs_per_session:
            use_bridge = rng.random() > jump_tolerance

            if use_bridge:
                recent_artist_set = set(
                    recent_artists_window[-RECENT_ARTIST_WINDOW:]
                )

                bridge = find_bridge_track(
                    groups,
                    used_ids | (global_used_ids if respect_global_used else set()),
                    current_genre,
                    next_genre,
                    recent_artist_set,
                    rng,
                )

                if bridge is not None:
                    session.append(bridge)
                    session_roles.append("puente")
                    used_ids.add(bridge["id"])

                    for artist in bridge.get("artists", []):
                        recent_artists_window.append(normalize_text(artist))

                    previous = bridge

        recent_genres.append(current_genre)
        if len(recent_genres) > 5:
            recent_genres.pop(0)

        current_genre = next_genre

    # --------------------------------------------------------
    # Completar si falta (nunca dejar la sesión corta si hay material).
    # --------------------------------------------------------

    if len(session) < songs_per_session:
        remaining = [
            t for t in tracks if not is_used(t.get("id"))
        ]

        rng.shuffle(remaining)

        for track in remaining:
            if len(session) >= songs_per_session:
                break

            session.append(track)
            session_roles.append("regular")
            used_ids.add(track["id"])

    for track in session:
        global_used_ids.add(track["id"])

    for track, role in zip(session, session_roles):
        track["_role"] = role

    return session[:songs_per_session]


def build_sessions(
    tracks,
    number,
    songs_per_session,
    mode,
    variety,
    intensity,
    allow_repeat_between_sessions,
    ai_genre_order=None,
):
    sessions = []

    base_seed = int(time.time())

    global_used_ids = set()

    for index in range(number):
        session = create_dj_session(
            tracks=tracks,
            songs_per_session=songs_per_session,
            mode=mode,
            variety=variety,
            intensity=intensity,
            seed=base_seed + index * 12721,
            global_used_ids=global_used_ids,
            respect_global_used=not allow_repeat_between_sessions,
            ai_genre_order=ai_genre_order,
        )

        if session:
            sessions.append(session)

    return sessions


def session_sequence_labels(session):
    sequence = []

    for track in session:
        genre = track.get("genre", "Latin")
        role = track.get("_role", "regular")

        label = f"🔗 {genre}" if role == "puente" else genre

        if not sequence or sequence[-1] != label:
            sequence.append(label)

    return sequence


# ============================================================
# CREAR PLAYLIST  (sin cambios en la llamada a la API)
# ============================================================

def create_playlist(token, name, tracks, public):
    playlist = spotify_request(
        "POST",
        "/me/playlists",
        token,
        json_data={
            "name": name,
            "description": (
                "Spotify Auto-Mix DJ - "
                "sesión organizada por bloques, puentes y transiciones."
            ),
            "public": public,
            "collaborative": False,
        },
    )

    playlist_id = playlist.get("id")

    if not playlist_id:
        raise RuntimeError("Spotify no devolvió el ID de la playlist.")

    uris = [track["uri"] for track in tracks if track.get("uri")]

    for start in range(0, len(uris), 100):
        spotify_request(
            "POST",
            f"/playlists/{playlist_id}/items",
            token,
            json_data={"uris": uris[start:start + 100]},
        )

    return {
        "name": name,
        "id": playlist_id,
        "tracks": len(uris),
        "url": playlist.get("external_urls", {}).get("spotify"),
    }


# ============================================================
# HISTORIAL (history) — almacenamiento local, sin tokens
# ============================================================

def load_history():
    if HISTORY_KEY in st.session_state:
        return st.session_state[HISTORY_KEY]

    history = []

    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as handle:
                history = json.load(handle)
    except Exception:
        history = []

    st.session_state[HISTORY_KEY] = history

    return history


def save_history_entry(entry):
    history = load_history()
    history.append(entry)
    history = history[-50:]  # no crecer indefinidamente

    st.session_state[HISTORY_KEY] = history

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as handle:
            json.dump(history, handle, ensure_ascii=False, indent=2)
    except Exception:
        pass  # el historial en session_state sigue disponible igualmente


# ============================================================
# CONFIGURACIÓN DJ — helpers
# ============================================================

def get_dj_config():
    if DJ_CONFIG_KEY not in st.session_state:
        st.session_state[DJ_CONFIG_KEY] = {
            "variety": "Medio",
            "intensity": "Moderado",
            "allow_repeat_between_sessions": True,
            "use_ai": True,
        }

    return st.session_state[DJ_CONFIG_KEY]


# ============================================================
# CALLBACK  (sin cambios)
# ============================================================

if not st.session_state.get(TOKEN_KEY):
    if st.query_params.get("code") or st.query_params.get("error"):
        process_callback()


# ============================================================
# LOGIN  (sin cambios)
# ============================================================

if not st.session_state.get(TOKEN_KEY):

    st.title("🎧 Spotify Auto-Mix DJ")

    st.write(
        "Prepara sesiones musicales para que el orden "
        "funcione mejor con la reproducción y mezcla de Spotify."
    )

    st.info("Puedes usar ❤️ Mis Me gusta o cualquier playlist de tu cuenta.")

    auth_url = get_authorize_url()

    if auth_url:
        st.link_button(
            "🎵 Iniciar sesión con Spotify",
            auth_url,
            use_container_width=True,
        )

    st.stop()


# ============================================================
# TOKEN  (sin cambios)
# ============================================================

token = get_token()

if not token:
    st.error("La sesión de Spotify ya no está disponible.")

    if st.button("Volver a iniciar sesión", type="primary"):
        clear_session()
        st.rerun()

    st.stop()


# ============================================================
# PERFIL  (sin cambios)
# ============================================================

try:
    profile = load_profile(token)
except Exception as exc:
    st.error("No se pudo cargar el perfil.")
    st.exception(exc)
    st.stop()


display_name = profile.get("display_name") or profile.get("id") or "Usuario"


# ============================================================
# SIDEBAR — navegación
# ============================================================

PAGES = [
    "🔥 Generar Auto-Mix",
    "🤖 Mi IA Musical",
    "📊 Mi Perfil Musical",
    "🕘 Historial de Auto-Mix",
    "⚙️ Configuración DJ",
]

with st.sidebar:
    st.title("🎧 Auto-Mix DJ")

    st.write(f"👤 **{display_name}**")

    st.divider()

    page = st.radio("Navegación", PAGES, label_visibility="collapsed")

    st.divider()

    if st.button("Cerrar sesión", use_container_width=True):
        logout()


# ============================================================
# FUENTE — compartida entre páginas
# ============================================================

def render_source_selector(token):
    """Conserva exactamente el comportamiento original de selección
    de fuente (Me gusta / Playlist) y lo deja disponible para
    cualquier página a través de session_state."""

    st.subheader("🎵 Fuente")

    source = st.radio(
        "Selecciona de dónde saldrán las canciones:",
        ["❤️ Mis Me gusta", "📁 Una playlist"],
        horizontal=True,
    )

    source_tracks = []

    if source == "❤️ Mis Me gusta":
        try:
            source_tracks = load_liked_tracks(token)
            st.session_state[SELECTED_TRACKS_KEY] = source_tracks

        except SpotifyRateLimit as exc:
            st.error(
                f"Spotify está limitando temporalmente las peticiones. "
                f"Espera aproximadamente {exc.seconds} segundos."
            )
            st.stop()

        except Exception as exc:
            st.error("No se pudieron cargar tus Me gusta.")
            st.exception(exc)
            st.stop()

    else:
        try:
            playlists = load_playlists(token)

        except SpotifyRateLimit as exc:
            st.error(
                f"Spotify está limitando temporalmente las peticiones. "
                f"Espera aproximadamente {exc.seconds} segundos."
            )
            st.stop()

        except Exception as exc:
            st.error("No se pudieron cargar tus playlists.")
            st.exception(exc)
            st.stop()

        if not playlists:
            st.warning("No se encontraron playlists.")
            st.stop()

        options = {}

        for playlist in playlists:
            playlist_id = playlist.get("id")

            if not playlist_id:
                continue

            name = playlist.get("name", "Sin nombre")
            options[name] = playlist

        selected_name = st.selectbox("Selecciona una playlist", list(options.keys()))

        selected_playlist = options[selected_name]

        if st.button("📥 Cargar playlist", type="primary", use_container_width=True):
            try:
                with st.spinner("Cargando canciones..."):
                    source_tracks = load_playlist_tracks(
                        token, selected_playlist["id"]
                    )

                st.session_state[SELECTED_TRACKS_KEY] = source_tracks

            except SpotifyRateLimit as exc:
                st.error(
                    f"Spotify está limitando temporalmente las peticiones. "
                    f"Espera aproximadamente {exc.seconds} segundos."
                )

            except Exception as exc:
                st.error("No se pudo cargar la playlist.")
                st.exception(exc)

        else:
            source_tracks = st.session_state.get(SELECTED_TRACKS_KEY, [])

    return source_tracks


# ============================================================
# PÁGINA: 🔥 Generar Auto-Mix
# ============================================================

def render_generate_page(token):
    st.title("🎧 Spotify Auto-Mix DJ")

    st.write(
        "Construye sesiones con bloques musicales, canciones puente "
        "y transiciones inteligentes — como un DJ humano."
    )

    source_tracks = render_source_selector(token)

    if not source_tracks:
        st.info("Carga una fuente de canciones para comenzar.")
        st.stop()

    st.success(f"{len(source_tracks)} canciones disponibles.")

    st.divider()
    st.subheader("🎛️ Sesión DJ")

    col1, col2, col3 = st.columns(3)

    with col1:
        songs_per_session = st.slider("Canciones por sesión", 15, 25, 20)

    with col2:
        session_count = st.slider("Número de sesiones", 2, 10, 5)

    with col3:
        mode = st.selectbox("Estilo de sesión", list(MODES.keys()))

    public = st.checkbox("Crear playlists públicas", value=False)

    dj_config = get_dj_config()

    st.caption(
        f"Variedad: **{dj_config['variety']}** · "
        f"Intensidad de cambio: **{dj_config['intensity']}** · "
        f"Repetición entre sesiones: "
        f"**{'Activada' if dj_config['allow_repeat_between_sessions'] else 'Desactivada'}** "
        f"— ajustable en ⚙️ Configuración DJ."
    )

    st.divider()
    st.subheader("🔥 Crear Auto-Mix")

    st.caption(
        "El motor arma bloques por estilo, usa canciones puente en "
        "los saltos grandes y evita repeticiones de artista."
    )

    generate = st.button(
        "🔥 GENERAR Y CREAR EN SPOTIFY",
        type="primary",
        use_container_width=True,
    )

    if generate:
        with st.spinner("Preparando tu biblioteca musical..."):
            enriched = get_enriched_tracks(source_tracks, token)

        counts = Counter(t.get("genre", "Latin") for t in enriched)

        st.subheader("🎼 Estilos detectados")
        st.write(
            " • ".join(f"{genre}: {count}" for genre, count in counts.most_common())
        )

        ai_genre_order = None
        if dj_config.get("use_ai", True):
            available_genres = sorted(counts.keys())
            ai_genre_order = ai_suggest_genre_order(
                available_genres,
                dict(counts),
                mode,
                dj_config["variety"],
                dj_config["intensity"],
            )

            if ai_genre_order:
                st.caption("🤖 Sugerencia de IA externa aplicada al orden de bloques.")

        with st.spinner("Construyendo las sesiones DJ..."):
            sessions = build_sessions(
                tracks=enriched,
                number=session_count,
                songs_per_session=songs_per_session,
                mode=mode,
                variety=dj_config["variety"],
                intensity=dj_config["intensity"],
                allow_repeat_between_sessions=dj_config[
                    "allow_repeat_between_sessions"
                ],
                ai_genre_order=ai_genre_order,
            )

        if not sessions:
            st.error("No se pudieron generar las sesiones.")
            st.stop()

        st.subheader("🎧 Recorrido musical")

        for index, session in enumerate(sessions, start=1):
            sequence = session_sequence_labels(session)
            st.write(f"**DJ {index:02d}:** " + " → ".join(sequence))

        created = []
        prefix = MODES[mode]["prefix"]

        progress = st.progress(0)

        try:
            for index, session in enumerate(sessions, start=1):
                playlist = create_playlist(
                    token=token,
                    name=f"{prefix} #{index:02d}",
                    tracks=session,
                    public=public,
                )

                created.append(playlist)

                progress.progress(index / len(sessions))

                time.sleep(1)

        except SpotifyRateLimit as exc:
            st.error(
                f"Spotify limitó temporalmente la creación. "
                f"Espera aproximadamente {exc.seconds} segundos."
            )

        except Exception as exc:
            st.error("Ocurrió un error al crear las playlists.")
            st.exception(exc)

        progress.empty()

        if created:
            st.session_state[CREATED_KEY] = created
            st.session_state[LAST_SESSIONS_KEY] = sessions

            st.success(
                f"✅ Se crearon {len(created)} playlists directamente en Spotify."
            )

            for playlist in created:
                url = playlist.get("url")

                if url:
                    st.link_button(
                        f"🎧 {playlist['name']} — {playlist['tracks']} canciones",
                        url,
                        use_container_width=True,
                    )
                else:
                    st.write(f"✅ {playlist['name']}")

            genres_used = sorted(
                {t.get("genre", "Latin") for s in sessions for t in s}
            )

            save_history_entry(
                {
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "modo": mode,
                    "canciones_por_sesion": songs_per_session,
                    "num_sesiones": len(created),
                    "playlists": [
                        {"nombre": p["name"], "url": p.get("url")} for p in created
                    ],
                    "generos_utilizados": genres_used,
                }
            )

    created_playlists = st.session_state.get(CREATED_KEY, [])

    if created_playlists:
        st.divider()
        st.subheader("🎶 Playlists creadas")

        for playlist in created_playlists:
            url = playlist.get("url")

            if url:
                st.link_button(playlist["name"], url, use_container_width=True)

    st.divider()
    st.caption(
        "El Auto-Mix prepara el orden de las canciones; la mezcla/fundido "
        "propio de Spotify se realiza dentro del reproductor de Spotify "
        "cuando esa función está disponible para tu cuenta y dispositivo."
    )


# ============================================================
# PÁGINA: 🤖 Mi IA Musical
# ============================================================

def render_ai_musical_page(token):
    st.title("🤖 Mi IA Musical")

    st.write(
        "Análisis de tu biblioteca musical: estilos, artistas, "
        "relaciones entre géneros y canciones que funcionan como puente."
    )

    source_tracks = st.session_state.get(SELECTED_TRACKS_KEY) or st.session_state.get(
        LIKED_KEY
    )

    if not source_tracks:
        st.info(
            "Primero carga una fuente de canciones en "
            "🔥 Generar Auto-Mix (Mis Me gusta o una playlist)."
        )
        return

    with st.spinner("Analizando tu biblioteca..."):
        enriched = get_enriched_tracks(source_tracks, token)
        profile = build_music_profile(enriched)

    col1, col2, col3 = st.columns(3)

    col1.metric("Canciones analizadas", profile["total_tracks"])
    col2.metric("Artistas distintos", profile["total_artists"])
    col3.metric("Diversidad musical", f"{profile['diversity']*100:.0f}%")

    st.divider()

    st.subheader("🎼 Géneros detectados")
    st.bar_chart(profile["genre_counts"])

    st.subheader("⭐ Estilos predominantes")
    st.write(", ".join(profile["predominant_styles"]) or "—")

    st.subheader("🎵 Estilos secundarios")
    st.write(", ".join(profile["secondary_styles"]) or "—")

    st.divider()

    st.subheader("👤 Artistas más frecuentes")
    top_artists = profile["artist_counts"].most_common(10)

    if top_artists:
        for artist, count in top_artists:
            st.write(f"- **{artist}** — {count} canciones")
    else:
        st.write("Sin datos suficientes.")

    st.divider()

    st.subheader("🔀 Posibles relaciones entre géneros")
    st.caption(
        "Basado en las transiciones musicales conocidas, filtradas a lo "
        "que realmente tienes disponible en tu biblioteca."
    )

    if profile["genre_relations"]:
        for genre, compatible in profile["genre_relations"].items():
            st.write(f"**{genre}** → {', '.join(compatible)}")
    else:
        st.write("No hay suficientes géneros distintos para mostrar relaciones.")

    st.divider()

    st.subheader("🌉 Canciones frecuentes como puente")
    st.caption(
        "Canciones cuyos artistas aparecen asociados a más de un estilo, "
        "y que el motor puede usar para suavizar transiciones grandes."
    )

    if profile["bridge_tracks"]:
        for track in profile["bridge_tracks"]:
            artistas = ", ".join(track.get("artists", []))
            estilos = ", ".join(track.get("possible_genres", []))
            st.write(f"- **{track.get('name')}** ({artistas}) — estilos: {estilos}")
    else:
        st.write(
            "No se detectaron canciones puente claras con la información "
            "disponible actualmente."
        )


# ============================================================
# PÁGINA: 📊 Mi Perfil Musical
# ============================================================

def render_music_profile_page(token):
    st.title("📊 Mi Perfil Musical")

    source_tracks = st.session_state.get(SELECTED_TRACKS_KEY) or st.session_state.get(
        LIKED_KEY
    )

    if not source_tracks:
        st.info(
            "Primero carga una fuente de canciones en "
            "🔥 Generar Auto-Mix (Mis Me gusta o una playlist)."
        )
        return

    with st.spinner("Calculando tu perfil musical..."):
        enriched = get_enriched_tracks(source_tracks, token)
        profile = build_music_profile(enriched)

    col1, col2, col3 = st.columns(3)

    col1.metric("Total de canciones", profile["total_tracks"])
    col2.metric("Total de artistas", profile["total_artists"])
    col3.metric(
        "Ratio artista/canción",
        f"{profile['unique_artist_ratio']*100:.0f}%",
    )

    st.divider()

    st.subheader("🎧 Géneros principales")

    if profile["total_tracks"] > 0:
        for genre, count in profile["genre_counts"].most_common():
            pct = (count / profile["total_tracks"]) * 100
            st.write(f"**{genre}** — {count} canciones ({pct:.1f}%)")

    st.divider()

    st.subheader("👥 Artistas frecuentes")

    for artist, count in profile["artist_counts"].most_common(10):
        st.write(f"- {artist} ({count})")

    st.divider()

    st.subheader("📚 Tu biblioteca contiene...")

    bullet_lines = "\n".join(
        f"- {genre}: {count} canciones"
        for genre, count in profile["genre_counts"].most_common()
    )

    st.markdown(bullet_lines or "Sin datos.")


# ============================================================
# PÁGINA: 🕘 Historial de Auto-Mix
# ============================================================

def render_history_page():
    st.title("🕘 Historial de Auto-Mix")

    history = load_history()

    if not history:
        st.info("Todavía no has generado ningún Auto-Mix.")
        return

    for entry in reversed(history):
        with st.expander(
            f"{entry.get('fecha', '—')} · {entry.get('modo', '—')} · "
            f"{entry.get('num_sesiones', 0)} playlists"
        ):
            st.write(f"**Canciones por sesión:** {entry.get('canciones_por_sesion')}")
            st.write(
                f"**Géneros utilizados:** "
                f"{', '.join(entry.get('generos_utilizados', []))}"
            )

            for playlist in entry.get("playlists", []):
                url = playlist.get("url")

                if url:
                    st.link_button(
                        playlist.get("nombre", "Playlist"),
                        url,
                        use_container_width=True,
                    )
                else:
                    st.write(f"- {playlist.get('nombre', 'Playlist')}")


# ============================================================
# PÁGINA: ⚙️ Configuración DJ
# ============================================================

def render_settings_page():
    st.title("⚙️ Configuración DJ")

    st.write(
        "Estos ajustes afectan a cómo se comporta el motor al construir "
        "las sesiones en 🔥 Generar Auto-Mix."
    )

    config = get_dj_config()

    col1, col2 = st.columns(2)

    with col1:
        variety = st.select_slider(
            "Nivel de variedad",
            options=VARIETY_LEVELS,
            value=config["variety"],
        )

        allow_repeat = st.radio(
            "Repetición de canciones entre sesiones distintas",
            ["Activada", "Desactivada"],
            index=0 if config["allow_repeat_between_sessions"] else 1,
            help=(
                "Una canción nunca se repite DENTRO de la misma playlist. "
                "Esto solo controla si puede aparecer en más de una "
                "playlist generada en la misma tanda."
            ),
        )

    with col2:
        intensity = st.select_slider(
            "Cambios de género",
            options=INTENSITY_LEVELS,
            value=config["intensity"],
            help=(
                "Suave: transiciones muy progresivas. "
                "Moderado: equilibrio. "
                "Atrevido: saltos de estilo más frecuentes."
            ),
        )

        use_ai = st.checkbox(
            "Usar IA externa como capa adicional (si hay OPENAI_API_KEY)",
            value=config.get("use_ai", True),
            help=(
                "Si no hay clave configurada en st.secrets, la app sigue "
                "funcionando normalmente con el motor local."
            ),
        )

    st.session_state[DJ_CONFIG_KEY] = {
        "variety": variety,
        "intensity": intensity,
        "allow_repeat_between_sessions": allow_repeat == "Activada",
        "use_ai": use_ai,
    }

    st.divider()

    st.subheader("🎚️ Modos disponibles")

    for mode_name, mode_config in MODES.items():
        st.write(
            f"**{mode_name}** — bloques de "
            f"{mode_config['min_block']} a {mode_config['max_block']} canciones."
        )

    st.caption(
        "El modo de sesión (DJ Profesional / Manejo / Tarde / Fiesta) se "
        "elige directamente en 🔥 Generar Auto-Mix."
    )

    st.divider()

    if get_openai_key():
        st.success("🤖 IA externa configurada (OPENAI_API_KEY detectada).")
    else:
        st.info(
            "🤖 No hay OPENAI_API_KEY configurada — la app funciona "
            "igualmente con el motor local."
        )


# ============================================================
# ENRUTAMIENTO
# ============================================================

if page == "🔥 Generar Auto-Mix":
    render_generate_page(token)

elif page == "🤖 Mi IA Musical":
    render_ai_musical_page(token)

elif page == "📊 Mi Perfil Musical":
    render_music_profile_page(token)

elif page == "🕘 Historial de Auto-Mix":
    render_history_page()

elif page == "⚙️ Configuración DJ":
    render_settings_page()
