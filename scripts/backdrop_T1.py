#!/usr/bin/env python3
"""
backdrops_type02_landscape.py
Landscape-only grid wallpaper with half-step alignment, smart focal placement,
and higher fetch variety to completely minimize tile duplicates.
"""

import io
import math
import os
import sys
import time
import random
import re
from datetime import datetime
from pathlib import Path

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# ╔═══════════════════════════════════════════════════════════════════╗
# ║                        CONFIGURATION                             ║
# ╚═══════════════════════════════════════════════════════════════════╝

import os
from dotenv import load_dotenv

# Load keys from the .env file in the project root
env_path = Path(__file__).resolve().parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).resolve().parent.parent / ".env"

load_dotenv(dotenv_path=env_path)

# Retrieve keys safely from environment variables
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
FANART_API_KEY = os.getenv("FANART_API_KEY")
MDBLIST_API_KEY = os.getenv("MDBLIST_API_KEY")

TMDB_ID         = None
ID_TYPE         = None
MDBLIST_URL     = None
OUTPUT_DIR      = "."

# Increased fetch count to drastically increase image variety and prevent duplicates
FETCH_COUNT     = 60        

ACCENT_COLOR    = None     # (R,G,B) or None = auto

# "row" = stagger alternate rows horizontally.
# "column" = stagger alternate columns vertically.
STAGGER_AXIS = "row"

# Set POV_X = 0.0 and POV_Y = 0.0 to flatten the 3D perspective
TILT_DEG = -10  # Clockwise rotation in degrees (e.g., 10 to 15 degrees)

# Pan/Drag the canvas (Middle mouse button drag style)
# Negative shifts left/up, positive shifts right/down.
OFFSET_X = 170  # Shift left/right in pixels (at 1080p, auto-scales for 4K)
OFFSET_Y = -80    # Shift up/down in pixels (at 1080p, auto-scales for 4K)

# ── Layout geometry (at 1080p — scales ×2 for 4K) ───────────────────────────
LANDSCAPE_W     = 400      # landscape tile width at 1080p (px)
GAP             = 8        # single gap value — applies everywhere (px)
CARD_RADIUS     = 8        # rounded corner radius at 1080p

# Opacity fades left (dim) → right (bright).
FADE_LEFT       = 0.30
FADE_RIGHT      = 1.00

# ── Perspective warp ───────────   # MAKE EVERY THING = 0 IF YOU WANT A FLAT LAYOUT, 
                                    # REMEBER TO CHANGE THE NAME OUTPUT, SEARCH out_dir / "t1_ (near the bottom)

PERSPECTIVE_V   = 0.5          # recommanded : 0.5
PERSPECTIVE_H   = -0.25          # recommanded : -0.25 

POV_X           = 1.0           # recommanded : 1.0
POV_Y           = -1.0          # recommanded : -1.0
WARP_STRENGTH   = 0.37          # recommanded : 0.37

# ── Depth-of-field blur ───────────────────────────────────────────────────────
DOF_BLUR_MAX    = 10.0
DOF_FOCUS_X     = 0.75
DOF_FOCUS_Y     = 0.25
DOF_FALLOFF     = 1.5

# Priority zone — fraction of columns (from right) that get the best tiles
PRIORITY_ZONE   = 0.55

# Gradient overlay accent colour
_DEFAULT_ACCENT = (20, 60, 80)
_ACCENT_MAP     = {}

# Focus point — best titles cluster around this region of the visible screen.
FOCUS_X      = 0.7     # 0.75 targets the right side (0.0 = Left, 1.0 = Right)
FOCUS_Y      = 0.2     # 0.25 targets the top side (0.0 = Top, 1.0 = Bottom)
FOCUS_RADIUS = 0.35     # How wide the focal bubble is (0.35 covers the quadrant perfectly)

# ╔═══════════════════════════════════════════════════════════════════╗
# ║                       INTERNAL CODE                              ║
# ╚═══════════════════════════════════════════════════════════════════╝

TMDB_BASE       = "https://api.themoviedb.org/3"
TMDB_IMG_BASE   = "https://image.tmdb.org/t/p"
BACKDROP_SIZE   = "w1280"
POSTER_SIZE     = "w780"
FANART_BASE     = "https://webservice.fanart.tv/v3"


# ── TMDB helpers ─────────────────────────────────────────────────────────────

BLOCKED_KEYWORDS = [
    "hentai", "porn", "pornography", "erotica", "xxx",
    "av girl", "jav", "milf", "fetish", "bondage",
    "bdsm", "ecchi", "yaoi", "yuri",
    "uncensored", "creampie", "bukkake"
]


BLOCKED_IDS = {
    1241752,
    95897,
}
def _normalize_text(text):
    text = text.lower()

    # Replace common separators
    text = re.sub(r"[_\-.]", " ", text)

    # Remove duplicate spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()

def _is_adult_content(item):
    # 1. Manual hard blacklist
    if item.get("id") in BLOCKED_IDS:
        return True

    # 2. TMDB internal adult flag
    if item.get("adult") is True:
        return True

    # 3. Low-Quality Heuristic
    # Filter out obscure content with very low engagement
    if (
        item.get("vote_count", 0) < 15 and
        item.get("popularity", 0) < 5
    ):
        return True

    # Check ALL title fields
    texts = [
        item.get("title", ""),
        item.get("name", ""),
        item.get("original_title", ""),
        item.get("original_name", ""),
        item.get("overview", "")
    ]

    for text in texts:
        text = _normalize_text(text)

        for word in BLOCKED_KEYWORDS:

            # Title fields = partial match
            if word in text:
                return True

            # Whole-word regex
            pattern = r"\b" + re.escape(word) + r"\b"

            if re.search(pattern, text):
                return True

    # Detect JAV style codes
    combined = " ".join(texts).lower()

    suspicious_patterns = [
        r"\b[a-z]{2,5}-\d{2,5}\b",  # ABP-123
        r"\bfc2\b",
        r"\b\d{6,}\b"
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, combined):
            return True

    return False

def _tmdb(endpoint, params=None):
    if not TMDB_API_KEY:
        print("  ❌ CRITICAL: No API Key loaded.")
        return {}
    p = dict(params or {})
    p["api_key"] = TMDB_API_KEY
    p["include_adult"] = False  # Apply to all endpoints including trending

    url = f"{TMDB_BASE}{endpoint}"
    try:
        r = requests.get(url, params=p, timeout=15)
        if r.status_code != 200:
            return {}

        data = r.json()

        if "results" in data:
            clean_results = []
            for item in data["results"]:
                
                # 1. DEBUG: Always print ID and Title first
                print(
                    f"DEBUG: {item.get('id')} | "
                    f"{item.get('title') or item.get('name')}"
                )

                # 2. Run the filter check
                if _is_adult_content(item):
                    print(f"  🚫 Filtered: {item.get('title') or item.get('name')}")
                    continue

                clean_results.append(item)

            data["results"] = clean_results
        return data
    except Exception:
        return {}


def _pull_tv(extra, count):
    items = []
    for page in range(1, 6):
        data = _tmdb("/discover/tv", {
            "sort_by": "popularity.desc",
            "page": page, 
            "language": "en-US", 
            "include_adult": False,  # Add this line
            **extra
        })
        for item in data.get("results", []):
            if item.get("backdrop_path") or item.get("poster_path"):
                items.append(("tv", item))
        if len(items) >= count: break
    return items[:count]


def _pull_movies(extra, count):
    items = []
    for page in range(1, 6):
        data = _tmdb("/discover/movie", {
            "sort_by": "popularity.desc",
            "page": page, 
            "language": "en-US", 
            "include_adult": False,  # Add this line
            **extra
        })
        for item in data.get("results", []):
            if item.get("backdrop_path") or item.get("poster_path"):
                items.append(("movie", item))
        if len(items) >= count: break
    return items[:count]


def _calculate_focal_score(item):
    pop = float(item.get("popularity", 0))
    date_str = item.get("release_date") or item.get("first_air_date") or ""
    
    if not date_str:
        return pop
        
    try:
        release_date = datetime.strptime(date_str, "%Y-%m-%d")
        # Days since the title was released
        age_days = max(1, (datetime.now() - release_date).days)
        
        # Smoothly boost anything released recently
        # A title released last month gets a ~10x multiplier boost.
        # A title released 5 years ago gets a 1x multiplier (pure popularity).
        recency_bonus = 1.0 + (1200.0 / (age_days + 100))
        
        return pop * recency_bonus
        
    except ValueError:
        return pop


def fetch_titles(tmdb_id, id_type, count):
    items = []
    # 1. Determine the media filter based on the ID suffix
    target_id = str(tmdb_id).lower().strip()
    only_movies = "-movies" in target_id
    only_tv = "-tv" in target_id
    
    # Clean the ID for the actual API call (e.g., "123-movies" -> "123")
    clean_id = target_id.replace("-movies", "").replace("-tv", "")

    # 2. Curated Logic
    if id_type == "curated":
        print(f"  -> Pulling curated TMDb list: {target_id}")
        combined = []
        
        # 1. Initialize data containers to avoid "Variable not defined" errors
        m_data = {"results": []}
        t_data = {"results": []}
        
        # 2. Determine the base category (trending, popular, etc.)
        base = clean_id.split("-")[0]
        
        # 3. Fetch Data based on Media Type
        if base == "trending":
            if not only_tv: m_data = _tmdb("/trending/movie/day")
            if not only_movies: t_data = _tmdb("/trending/tv/day")
        elif base == "popular":
            if not only_tv: m_data = _tmdb("/movie/popular")
            if not only_movies: t_data = _tmdb("/tv/popular")
        elif base == "top_rated":
            if not only_tv: m_data = _tmdb("/movie/top_rated")
            if not only_movies: t_data = _tmdb("/tv/top_rated")
        elif base == "upcoming":
            # TV doesn't have a specific 'upcoming' endpoint on TMDB
            if not only_tv: m_data = _tmdb("/movie/upcoming")
        else:
            print(f"  Unknown curated type: '{base}'.")
            sys.exit(1)
        
        # 4. Assemble the combined list
        combined = [("movie", i) for i in m_data.get("results", [])] + \
                   [("tv", i) for i in t_data.get("results", [])]

    # 3. Network / Company / Provider / Genre Logic
    elif id_type == "network":
        # Networks are TV-centric by nature
        items = _pull_tv({"with_networks": clean_id}, count)
        
    elif id_type == "company":
        tv = [] if only_movies else _pull_tv({"with_companies": clean_id}, count)
        movies = [] if only_tv else _pull_movies({"with_companies": clean_id}, count)
        combined = tv + movies
        
    elif id_type == "provider":
        tv = [] if only_movies else _pull_tv({"with_watch_providers": clean_id, "watch_region": "US"}, count)
        movies = [] if only_tv else _pull_movies({"with_watch_providers": clean_id, "watch_region": "US"}, count)
        combined = tv + movies
        
    elif id_type == "genre":
        movies = [] if only_tv else _pull_movies({"with_genres": clean_id}, count)
        tv = [] if only_movies else _pull_tv({"with_genres": clean_id}, count)
        combined = movies + tv
        
    else:
        print(f"  Unknown --type '{id_type}'.")
        sys.exit(1)

    # 4. Processing results for non-curated/non-network types
    # This block now captures EVERYTHING processed into 'combined'
    if 'combined' in locals() and combined:
        combined_sorted = sorted(combined, key=lambda kt: kt[1].get("popularity", 0), reverse=True)
        seen = set()
        for k, item in combined_sorted:
            if item["id"] not in seen:
                seen.add(item["id"])
                items.append((k, item))
            if len(items) >= count:
                break

    # Final deduplication pass
    seen_unique, unique = set(), []
    for k, item in items:
        # Check if item is a dict (TMDb) or something else
        item_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
        if not item_id: continue
        
        key = (item.get("media_type", k), item_id)
        if key not in seen_unique:
            seen_unique.add(key)
            unique.append((k, item))
            
    return unique[:count]


def _fetch_label(tmdb_id, id_type):
    try:
        if id_type == "network":
            name = _tmdb(f"/network/{tmdb_id}").get("name", "")
        elif id_type == "company":
            name = _tmdb(f"/company/{tmdb_id}").get("name", "")
        elif id_type == "provider":
            name = ""
            for ep in ("/watch/providers/tv", "/watch/providers/movie"):
                match = next((p for p in _tmdb(ep, {"watch_region": "US"}).get("results", [])
                               if p.get("provider_id") == tmdb_id), None)
                if match: 
                    name = match.get("provider_name", "")
                    break
        elif id_type == "genre":
            all_g = (_tmdb("/genre/movie/list", {"language": "en-US"}).get("genres", []) +
                     _tmdb("/genre/tv/list",    {"language": "en-US"}).get("genres", []))
            name = next((g["name"] for g in all_g if g["id"] == tmdb_id), "")
        else:
            name = ""
    except Exception:
        name = ""
    if not name:
        return f"{id_type}_{tmdb_id}"
    safe = re.sub(r"[^\w]+", "_", name.strip().lower()).strip("_")
    return safe or f"{id_type}_{tmdb_id}"


# ── MDBList ───────────────────────────────────────────────────────────────────

def _parse_mdblist_url(url):
    url = url.strip().rstrip("/")
    m = re.search(r"mdblist\.com/lists/([^/]+)/([^/]+)$", url)
    if m: return m.group(1), m.group(2)
    m = re.match(r"^([^/\s]+)/([^/\s]+)$", url)
    if m and "." not in url and ":" not in url: return m.group(1), m.group(2)
    raise ValueError(f"Could not parse MDBList URL: {url!r}")


def fetch_mdblist_items(url, count, sort=None):
    username, slug = _parse_mdblist_url(url)
    label = re.sub(r"[^\w]+", "_", slug.strip().lower()).strip("_") or f"{username}_{slug}"
    key = {"apikey": MDBLIST_API_KEY}

    print(f"  Fetching MDBList: {username}/{slug} …")
    try:
        r = requests.get(f"https://api.mdblist.com/lists/user/{username}", params=key, timeout=20)
        r.raise_for_status()
        user_lists = r.json()
    except Exception as e:
        print(f"  ✗  {e}")
        sys.exit(1)

    matched = next((l for l in user_lists if l.get("slug", "").lower() == slug.lower()), None)
    if not matched:
        print(f"  ✗  List '{slug}' not found.")
        sys.exit(1)

    list_id = matched["id"]
    print(f"  Found: '{matched.get('name', slug)}' (id={list_id})")

    # Correct Query Generation for Sorting MDBList items
    params = {**key}
    if sort:
        parts = sort.lower().split(".")
        params["sort"] = parts[0]
        params["order"] = parts[1] if len(parts) > 1 else "desc"

    try:
        r = requests.get(f"https://api.mdblist.com/lists/{list_id}/items",
                         params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  ✗  {e}")
        sys.exit(1)

    raw_items = data if isinstance(data, list) else data.get("movies", []) + data.get("shows", [])
    print(f"  Found {len(raw_items)} items.\n")

    results = []
    for entry in raw_items[:count * 2]:
        imdb_id = entry.get("imdb_id") or entry.get("imdb")
        mediatype = entry.get("mediatype", "")
        if not imdb_id:
            continue
        kind = "tv" if mediatype == "show" else "movie"
        try:
            find = _tmdb(f"/find/{imdb_id}", {"external_source": "imdb_id"})
            hits = find.get("tv_results" if kind == "tv" else "movie_results", [])
            if not hits:
                continue
            tmdb_item = hits[0]
        except Exception:
            continue
        if not (tmdb_item.get("backdrop_path") or tmdb_item.get("poster_path")):
            continue
        results.append((kind, tmdb_item))
        if len(results) >= count:
            break

    return label, results


# ── Fanart ────────────────────────────────────────────────────────────────────

def _fanart_tv(tvdb_id):
    try:
        r = requests.get(f"{FANART_BASE}/tv/{tvdb_id}",
                         params={"api_key": FANART_API_KEY}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception: 
        return None


def _fanart_movie(tmdb_id):
    try:
        r = requests.get(f"{FANART_BASE}/movies/{tmdb_id}",
                         params={"api_key": FANART_API_KEY}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception: 
        return None


def _best_fanart_url(data, kind):
    if not data: return None
    keys = ["tvthumb", "showbackground"] if kind == "tv" else ["moviethumb", "moviebackground"]
    for key in keys:
        en = [c for c in data.get(key, []) if c.get("lang") == "en"]
        if en:
            return sorted(en, key=lambda c: int(c.get("likes", 0)), reverse=True)[0]["url"]
    return None


def _get_external_ids(kind, tmdb_id):
    try: 
        return _tmdb(f"/{kind}/{tmdb_id}/external_ids")
    except Exception: 
        return {}


# ── Image fetching ────────────────────────────────────────────────────────────

def resolve_image(kind, item, prefer_poster=False):
    tmdb_id = item["id"]
    url     = None

    if prefer_poster:
        pp = item.get("poster_path")
        if pp: url = f"{TMDB_IMG_BASE}/{POSTER_SIZE}{pp}"
    else:
        if FANART_API_KEY:
            if kind == "tv":
                ext = _get_external_ids("tv", tmdb_id)
                tvdb_id = ext.get("tvdb_id")
                if tvdb_id:
                    url = _best_fanart_url(_fanart_tv(tvdb_id), "tv")
            else:
                url = _best_fanart_url(_fanart_movie(tmdb_id), "movie")
        if not url:
            bp = item.get("backdrop_path")
            if bp: url = f"{TMDB_IMG_BASE}/{BACKDROP_SIZE}{bp}"
        if not url:
            pp = item.get("poster_path")
            if pp: url = f"{TMDB_IMG_BASE}/{POSTER_SIZE}{pp}"

    if not url: return None

    for attempt in range(3):
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except Exception:
            if attempt == 2: return None
            time.sleep(1)


# ── Tile rendering ────────────────────────────────────────────────────────────

def _rounded_mask(w, h, radius):
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w-1, h-1], radius=radius, fill=255)
    return mask


def _make_tile(img, tw, th, opacity=1.0):
    iw, ih = img.size
    tr     = tw / th
    sr     = iw / ih
    if sr > tr:
        nw  = int(ih * tr)
        img = img.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    else:
        nh  = int(iw / tr)
        img = img.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
    img = img.resize((tw, th), Image.LANCZOS)
    r   = max(2, int(CARD_RADIUS * tw / max(LANDSCAPE_W, 1)))
    out = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    out.paste(img, mask=_rounded_mask(tw, th, r))
    if opacity < 1.0:
        rc, gc, bc, ac = out.split()
        ac = ac.point(lambda v: int(v * opacity))
        out = Image.merge("RGBA", (rc, gc, bc, ac))
    return out


# ── Layout engine ─────────────────────────────────────────────────────────────

def _build_layout(landscape_imgs, canvas_w, canvas_h, scale):
    lw  = int(LANDSCAPE_W * scale)
    lh  = int(round(lw * 9 / 16))
    gap = int(GAP * scale)

    # Use enough overflow boundaries to guarantee edge-to-edge content
    bleed_x = (lw + gap) * 3
    bleed_y = lh * 2 + gap * 4
    stagger_x = (lw + gap) // 2
    stagger_y = (lh + gap) // 2

    # Calculate oversized canvas dimensions
    over_w = canvas_w + bleed_x * 2
    over_h = canvas_h + bleed_y * 2
    ox     = bleed_x
    oy     = bleed_y
    canvas = Image.new("RGBA", (over_w, over_h), (10, 12, 16, 255))

    # Calculate zone thresholds
    l_cutoff = max(1, int(len(landscape_imgs) * 0.35))
    pri_landscapes  = landscape_imgs[:l_cutoff]
    rest_landscapes = landscape_imgs[l_cutoff:]

    rng = random.Random(42)

    # Gather a list of all tile placement coordinates
    tiles_to_place = []

    if globals().get("STAGGER_AXIS", "row") == "row":
        # Build by Row (horizontal rows aligned, alternate rows shifted horizontally)
        y = -bleed_y + oy
        row_idx = 0
        while y < over_h:
            row_shift = stagger_x if (row_idx % 2 == 1) else 0
            x = -bleed_x + row_shift + ox

            while x < over_w:
                # Corrected: Subtract the bleed offset (ox, oy) to get true screen center
                screen_x = x - ox + (lw * 0.5)
                screen_y = y - oy + (lh * 0.5)
                
                # Normalize relative to the visible screen width & height
                norm_x = screen_x / canvas_w
                norm_y = screen_y / canvas_h

                depth   = max(0.0, min(1.0, norm_x))
                opacity = FADE_LEFT + (FADE_RIGHT - FADE_LEFT) * depth

                dist_to_focus = math.hypot(norm_x - FOCUS_X, norm_y - FOCUS_Y)
                is_focal_area = dist_to_focus <= FOCUS_RADIUS

                # Accurate on-screen bounding box test
                is_on_screen = (0.0 <= norm_x <= 1.0) and (0.0 <= norm_y <= 1.0)

                tiles_to_place.append({
                    "x": x, "y": y, "w": lw, "h": lh, "opacity": opacity,
                    "is_focal": is_focal_area, "is_on_screen": is_on_screen
                })
                x += lw + gap

            y += lh + gap
            row_idx += 1
    else:
        # Original Column-based layout with vertical shift
        columns = []
        x = -bleed_x
        col_idx = 0
        while x < canvas_w + bleed_x:
            columns.append({"x": x, "w": lw, "stagger": col_idx % 2 == 1})
            x += lw + gap
            col_idx += 1

        for col in columns:
            col_x = col["x"] + ox
            col_w = col["w"]

            shift = stagger_y if col["stagger"] else 0
            y = -bleed_y + shift + oy

            while y < over_h:
                th = max(4, int(col_w * 9 / 16))
                
                # Corrected: Subtract bleed to get true screen center
                screen_x = col_x - ox + (col_w * 0.5)
                screen_y = y - oy + (th * 0.5)
                
                norm_x = screen_x / canvas_w
                norm_y = screen_y / canvas_h

                depth   = max(0.0, min(1.0, norm_x))
                opacity = FADE_LEFT + (FADE_RIGHT - FADE_LEFT) * depth

                dist_to_focus = math.hypot(norm_x - FOCUS_X, norm_y - FOCUS_Y)
                is_focal_area = dist_to_focus <= FOCUS_RADIUS

                is_on_screen = (0.0 <= norm_x <= 1.0) and (0.0 <= norm_y <= 1.0)

                tiles_to_place.append({
                    "x": col_x, "y": y, "w": col_w, "h": th, "opacity": opacity,
                    "is_focal": is_focal_area, "is_on_screen": is_on_screen
                })
                y += th + gap

    # Sort tiles to process the visible screen first, then bleed areas
    tiles_to_place.sort(key=lambda t: (not t["is_on_screen"], not t["is_focal"]))

    # Do NOT shuffle uniques to preserve true trending sorting
    # We use reversed() because .pop() pulls from the end of the list.
    unique_pri = list(reversed(pri_landscapes))
    unique_rest = list(reversed(rest_landscapes))

    # Backup repeating pools if uniques are exhausted
    repeat_pri = list(pri_landscapes)
    repeat_rest = list(rest_landscapes)
    rng.shuffle(repeat_pri)
    rng.shuffle(repeat_rest)

    pri_repeat_idx = 0
    rest_repeat_idx = 0

    # Fill tiles using the prioritized sort
    for t in tiles_to_place:
        if t["is_focal"]:
            if unique_pri:
                src = unique_pri.pop()
            else:
                src = repeat_pri[pri_repeat_idx % len(repeat_pri)]
                pri_repeat_idx += 1
        else:
            if unique_rest:
                src = unique_rest.pop()
            else:
                src = repeat_rest[rest_repeat_idx % len(repeat_rest)]
                rest_repeat_idx += 1

        tile = _make_tile(src, t["w"], t["h"], opacity=t["opacity"])
        canvas.paste(tile, (int(t["x"]), int(t["y"])), tile)

    return canvas, ox, oy


# ── Perspective warp ──────────────────────────────────────────────────────────

def _perspective_warp(oversized, ox, oy, out_w, out_h, pov_x=0.0, pov_y=0.0):
    if pov_x == 0.0 and pov_y == 0.0:
        # Scale offsets to match 1080p vs 4K
        scale = out_w / 1920.0
        off_x = int(globals().get("OFFSET_X", 0) * scale)
        off_y = int(globals().get("OFFSET_Y", 0) * scale)

        # Apply shift by panning the crop region in the opposite direction
        shifted_ox = ox - off_x
        shifted_oy = oy - off_y

        if "TILT_DEG" in globals() and TILT_DEG != 0:
            # Rotate about the newly panned crop center so the tilt stays anchored perfectly
            center_x = shifted_ox + out_w / 2
            center_y = shifted_oy + out_h / 2
            rotated = oversized.rotate(-TILT_DEG, resample=Image.BICUBIC, center=(center_x, center_y))
            return rotated.crop((shifted_ox, shifted_oy, shifted_ox + out_w, shifted_oy + out_h))
        else:
            return oversized.crop((shifted_ox, shifted_oy, shifted_ox + out_w, shifted_oy + out_h))

    tl_x, tl_y = 0.0, 0.0
    tr_x, tr_y = float(out_w), 0.0
    br_x, br_y = float(out_w), float(out_h)
    bl_x, bl_y = 0.0, float(out_h)

    if pov_x > 0:
        inset_y = (out_h * WARP_STRENGTH * abs(pov_x)) / 2
        tl_y += inset_y
        bl_y -= inset_y
    elif pov_x < 0:
        inset_y = (out_h * WARP_STRENGTH * abs(pov_x)) / 2
        tr_y += inset_y
        br_y -= inset_y

    if pov_y > 0:
        inset_x = (out_w * WARP_STRENGTH * abs(pov_y)) / 2
        tl_x += inset_x
        tr_x -= inset_x
    elif pov_y < 0:
        inset_x = (out_w * WARP_STRENGTH * abs(pov_y)) / 2
        bl_x += inset_x
        br_x -= inset_x

    src = [
        (ox, oy),                  
        (ox + out_w, oy),          
        (ox + out_w, oy + out_h),  
        (ox, oy + out_h)           
    ]

    dst = [
        (tl_x, tl_y),
        (tr_x, tr_y),
        (br_x, br_y),
        (bl_x, bl_y)
    ]

    A, b = [], []
    for (sx, sy), (dx, dy) in zip(src, dst):
        A.append([dx, dy, 1, 0,  0,  0, -sx*dx, -sx*dy])
        b.append(sx)
        A.append([0,  0,  0, dx, dy, 1, -sy*dx, -sy*dy])
        b.append(sy)

    try:
        coeffs = np.linalg.solve(np.array(A, dtype=np.float64), np.array(b, dtype=np.float64))
        return oversized.transform(
            (out_w, out_h), Image.PERSPECTIVE, tuple(coeffs), resample=Image.BICUBIC
        )
    except Exception:
        return oversized.crop((ox, oy, ox + out_w, oy + out_h))


# ── Depth-of-field blur ───────────────────────────────────────────────────────

def _apply_dof(image, scale=1.0):
    if DOF_BLUR_MAX <= 0:
        return image

    w, h  = image.size
    fx    = DOF_FOCUS_X * w
    fy    = DOF_FOCUS_Y * h
    diag  = math.hypot(w, h)

    xs = np.linspace(0, w - 1, w, dtype=np.float32)
    ys = np.linspace(0, h - 1, h, dtype=np.float32)
    xg, yg   = np.meshgrid(xs, ys)
    dist_map = np.sqrt((xg - fx)**2 + (yg - fy)**2) / diag
    blur_map = np.clip(dist_map ** DOF_FALLOFF, 0.0, 1.0)

    N      = 5
    max_r  = DOF_BLUR_MAX * scale
    layers = [image if (i / N) * max_r < 0.5 else
              image.filter(ImageFilter.GaussianBlur(radius=(i / N) * max_r))
              for i in range(N + 1)]

    arrs = [np.array(l, dtype=np.float32) for l in layers]
    out  = np.zeros_like(arrs[0])

    for i in range(N):
        lo  = i / N
        hi  = (i + 1) / N
        in_ = (blur_map >= lo) & (blur_map < hi)
        t   = ((blur_map - lo) / (hi - lo + 1e-9))[in_]
        out[in_] = arrs[i][in_] * (1 - t[:, None]) + arrs[i+1][in_] * t[:, None]

    out[blur_map >= (N - 1) / N] = arrs[N][blur_map >= (N - 1) / N]

    return Image.fromarray(out.clip(0, 255).astype(np.uint8), image.mode)


# ── Gradient overlay ──────────────────────────────────────────────────────────

def _apply_gradient(canvas, accent, show_gradient=True):
    if not show_gradient:
        return canvas
    w, h = canvas.size
    ar, ag, ab = accent

    def grad_left(gw, gh):
        img = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
        px  = img.load()
        for x in range(int(gw * 0.65)):
            t = 1.0 - x / (gw * 0.65)
            a = int(240 * (t ** 1.4))
            if a:
                for y in range(gh):
                    px[x, y] = (6, 8, 12, a)
        return img

    def grad_bottom(gw, gh):
        img = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
        px  = img.load()
        for y in range(gh):
            t = max(0.0, (y - gh * 0.55) / (gh * 0.45))
            a = int(215 * (t ** 1.3))
            if a:
                for x in range(gw):
                    px[x, y] = (6, 8, 12, a)
        return img

    def accent_glow(gw, gh):
        img = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
        dw  = ImageDraw.Draw(img)
        for i in range(18):
            t  = i / 18
            rr = int(math.hypot(gw, gh) * (0.05 + 0.38 * t))
            aa = int(14 * (1 - t) ** 2.2)
            if aa:
                dw.ellipse([gw - rr, -rr, gw + rr, rr], fill=(ar, ag, ab, aa))
        return img

    left_side = grad_left(w // 4, h // 4).resize((w, h), Image.BILINEAR)
    bottom_side = grad_bottom(w // 4, h // 4).resize((w, h), Image.BILINEAR)
    
    result = Image.alpha_composite(canvas, left_side)
    result = Image.alpha_composite(result, bottom_side)
    result = Image.alpha_composite(result, accent_glow(w, h))
    return result


def _save(canvas, path):
    final = canvas.convert("RGB")
    final.save(path, "JPEG", quality=95, optimize=True)
    mb = os.path.getsize(path) / 1_048_576
    print(f"  ✓  {path}  ({final.size[0]}×{final.size[1]},  {mb:.1f} MB)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate a mixed portrait/landscape grid wallpaper.")
    parser.add_argument("--id", nargs="+", default=None)
    parser.add_argument("--type", default=None, help="network | provider | company | genre | curated")
    parser.add_argument("--url",         default=None,
                        help="MDBList URL or 'username/list-slug'")
    parser.add_argument("--sort", default="score.desc", help="MDBList sort, e.g. imdbrating.desc or score.desc")
    parser.add_argument("--output",      default=None)
    parser.add_argument("--no-gradient", action="store_true")
    args = parser.parse_args()

    tmdb_ids    = args.id     if args.id     is not None else ([TMDB_ID] if TMDB_ID else None)
    id_type     = args.type   if args.type   is not None else ID_TYPE
    mdblist_url = args.url    if args.url    is not None else MDBLIST_URL
    out_dir     = args.output if args.output is not None else OUTPUT_DIR
    use_mdblist = bool(mdblist_url)

    if not use_mdblist and (not tmdb_ids or not id_type):
        print("\n  ✗  Provide --url OR --id + --type\n")
        sys.exit(1)
    if args.type == "curated" and args.id:
        tmdb_ids = [str(args.id[0])]
    if not TMDB_API_KEY:
        print("\n  ✗  TMDB_API_KEY is empty.\n")
        sys.exit(1)
    if use_mdblist and not MDBLIST_API_KEY:
        print("\n  ✗  MDBLIST_API_KEY is empty.\n")
        sys.exit(1)

    accent = (ACCENT_COLOR if ACCENT_COLOR is not None
              else _ACCENT_MAP.get(tmdb_ids[0] if tmdb_ids else 0, _DEFAULT_ACCENT))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if use_mdblist:
        label, titles = fetch_mdblist_items(mdblist_url, FETCH_COUNT, sort=args.sort)
        file_4k    = f"type02_mdblist_{label}_4k.jpg"
        file_1080p = f"type02_mdblist_{label}_1080p.jpg"
        print(f"  Mode   : MDBList\n  URL    : {mdblist_url}\n")
    else:
        labels     = [_fetch_label(tid, id_type) for tid in tmdb_ids]
        label      = "_".join(labels)
        file_4k    = f"type02_{id_type}_{label}_4k.jpg"
        file_1080p = f"type02_{id_type}_{label}_1080p.jpg"
        print(f"\n  IDs    : {tmdb_ids}  ({id_type})")
        print(f"  Label  : {label}")
        print(f"  Output : {out.resolve()}\n")

        print("Fetching titles…")
        combined, seen_keys = [], set()
        for tid in tmdb_ids:
            for k, item in fetch_titles(tid, id_type, FETCH_COUNT):
                key = (k, item["id"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    combined.append((k, item))
        titles = sorted(combined, key=lambda ki: _calculate_focal_score(ki[1]), reverse=True)[:FETCH_COUNT]
        if not titles:
            print("  No titles found.")
            sys.exit(1)
        print(f"  Found {len(titles)} titles.\n")

    print("Downloading images…")
    landscape_imgs = []
    fail_n = 0

    for i, (kind, item) in enumerate(titles):
        name = item.get("name") or item.get("title") or str(item["id"])
        sys.stdout.write(f"  [{i+1:02d}/{len(titles)}]  {name[:52]:<52}\r")
        sys.stdout.flush()
        land = resolve_image(kind, item, prefer_poster=False)
        if land: 
            landscape_imgs.append(land)
        else: 
            fail_n += 1

    print(f"\n  {len(landscape_imgs)} landscape images fetched,  {fail_n} failed\n")

    if not landscape_imgs:
        print("  No images downloaded.")
        sys.exit(1)

    show_grad = not args.no_gradient

    # ── Render ────────────────────────────────────────────────────────────────
    show_grad = not args.no_gradient

    print("Compositing 4K (3840×2160)…")
    over4k, ox4k, oy4k = _build_layout(landscape_imgs, 3840, 2160, scale=2.0)
    warped4k = _perspective_warp(over4k, ox4k, oy4k, 3840, 2160, POV_X, POV_Y)
    
    # Restored: Apply the depth of field blur
    dof4k = _apply_dof(warped4k, scale=2.0)

    # ── Adaptive Output Paths ─────────────────────────────────────────────────
    BASE_DIR = Path(__file__).resolve().parent.parent / "collections"
    
    single_id = args.id[0] if args.id else None

    if args.type == "curated":
        subfolder = "curated"
        # Curated types just use the keyword directly (e.g., trending, top-rated)
        brand_name = str(tmdb_ids[0]).lower().replace("_", "-")
        out_dir = BASE_DIR / subfolder / brand_name / "backdrops"
    else:
        if args.type == "network":
            subfolder = "networks"
            api_type = "network"
        elif args.type in ("company", "production_company"):
            subfolder = "companies"
            api_type = "company"
        elif args.type == "provider":
            subfolder = "providers"
            api_type = "provider"
        else:
            subfolder = "genres"
            api_type = "genre"

        if api_type == "provider":
            brand_name = f"unknown-{single_id}"
            try:
                for endpoint in ("/watch/providers/tv", "/watch/providers/movie"):
                    r = requests.get(f"https://api.themoviedb.org/3{endpoint}", params={"api_key": TMDB_API_KEY, "watch_region": "US"}, timeout=10)
                    if r.status_code == 200:
                        providers = r.json().get("results", [])
                        match = next((p for p in providers if p.get("provider_id") == single_id), None)
                        if match:
                            brand_name = match.get("provider_name")
                            break
            except Exception:
                pass
        else:
            url = f"https://api.themoviedb.org/3/{api_type}/{single_id}"
            params = {"api_key": TMDB_API_KEY}
            try:
                r = requests.get(url, params=params, timeout=10)
                r.raise_for_status()
                data = r.json()
                brand_name = data.get("name") or data.get("title") or f"unknown-{single_id}"
            except Exception:
                brand_name = f"unknown-{single_id}"

        slug = re.sub(r'[^a-z0-9]+', '-', brand_name.lower()).strip('-')
        
        # This is the ONLY place this specific format should be used
        out_dir = BASE_DIR / subfolder / f"{single_id}-{slug}" / "backdrops"

    # ── Folder Creation & Saving (Now runs after BOTH branches are correctly determined) ──
    out_dir.mkdir(parents=True, exist_ok=True)

    file_4k = out_dir / "t1_4k.jpg"
    file_1080p = out_dir / "t1_1080p.jpg"

    # Save using the blurred dof4k image
    _save(_apply_gradient(dof4k, accent, show_grad), file_4k)

    print("Compositing 1080p (1920×1080)…")
    over1080, ox1080, oy1080 = _build_layout(landscape_imgs, 1920, 1080, scale=1.0)
    warped1080 = _perspective_warp(over1080, ox1080, oy1080, 1920, 1080, POV_X, POV_Y)
    
    # Restored here too: Apply the depth of field blur
    dof1080 = _apply_dof(warped1080, scale=1.0)
    
    # Save using the blurred dof1080 image
    _save(_apply_gradient(dof1080, accent, show_grad), file_1080p)

    print(f"\n  ✓ T1 Backdrops saved to: {out_dir.relative_to(BASE_DIR.parent)}")


if __name__ == "__main__":
    main()