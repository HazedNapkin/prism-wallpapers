#!/usr/bin/env python3
"""
backdrop_T2_flat.py
Mixed portrait + landscape grid wallpaper with perspective warp and depth of field.
"""

import io
import math
import os
import sys
import time
import random
import argparse
import re
from pathlib import Path
from datetime import datetime

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# ╔═══════════════════════════════════════════════════════════════════╗
# ║                        CONFIGURATION                             ║
# ╚═══════════════════════════════════════════════════════════════════╝

# -- API Keys
TMDB_API_KEY = ""           # Your TMDB API key
FANART_API_KEY = ""         # Your Fanart.tv API key (Optional)
MDBLIST_API_KEY = ""        # Your MDBList API key (Optional)

# -- Defaults (Can be overwritten via CLI)
TMDB_ID = None      # Default TMDB ID to process if CLI arg is omitted
ID_TYPE = None      # Default ID type ("network", "provider", "company", "genre")
MDBLIST_URL = None  # Default MDBList URL or "username/list-slug"
OUTPUT_DIR = "."    # Directory to save the final wallpapers

# -- Processing Options
FETCH_COUNT = 60    # Maximum number of titles to retrieve
ACCENT_COLOR = None # Tuple (R, G, B) or None for auto accent color extraction

# Focus point — best titles cluster around this region.
FOCUS_X      = 0.5     # Fixed to top right quadrant for precise placement     |       # 0.5 Recommaned if FLAT
FOCUS_Y      = 0.0                                                                     # 0.0 Recommaned if FLAT
FOCUS_RADIUS = 0.30     # How wide the focal bubble is

# -- Layout Geometry (at 1080p — scales ×2 for 4K)
# Pattern determining column orientation: "P" = portrait (2:3), "L" = landscape (16:9)
COL_PATTERN = ["L", "P", "L", "P", "L", "P", "L", "P", "L"]

LANDSCAPE_W = 300   # Base landscape tile width (px)
PORTRAIT_W = 200    # Base portrait tile width (px)
GAP = 8             # Spacing between tiles (px)
CARD_RADIUS = 8     # Corner rounding radius of individual tiles (px)

COL_STAGGER = 0.35  # Fraction of height to shift odd-numbered columns down

# -- Image Spacing & Transitions
FADE_LEFT = 0.30    # Left side opacity (dim)
FADE_RIGHT = 1.00   # Right side opacity (bright)

# Random chance for a tile to ignore its default column aspect ratio (0.0 to 1.0)
RANDOM_ASPECT_CHANCE = 0.35

# -- Warp & Viewpoint (Point Of View) Settings
# Range: -1.0 to 1.0. Sets horizontal camera position. (1.0 = right edge is closest/flat)
POV_X = 0
# Range: -1.0 to 1.0. Sets vertical camera position. (-1.0 = top edge is closest/flat)
POV_Y = 0
# Intensity of perspective distortion (0.0 = no warp, 0.3 to 0.5 = natural perspective)
WARP_STRENGTH = 0.37

# ── Flat Mode Tiling & Positioning Settings ──────────────────────────────────
# (Applies only when POV_X = 0.0 and POV_Y = 0.0)
TILT_DEG = -10       # Clockwise rotation in degrees
OFFSET_X = 335        # Shift left/right in pixels (at 1080p, auto-scales for 4K)
OFFSET_Y = 100       # Shift up/down in pixels (at 1080p, auto-scales for 4K)

# -- Depth of Field Blur Settings
DOF_BLUR_MAX = 10.0 # Max blur radius. 0 disables the effect entirely.
DOF_FOCUS_X = 0.75  # Horizontal position of focus point (0.0 to 1.0)
DOF_FOCUS_Y = 0.25  # Vertical position of focus point (0.0 to 1.0)
DOF_FALLOFF = 1.5   # Decay rate of visual clarity away from the focal point

# -- Distribution Rules
PRIORITY_ZONE = 0.55 # Fraction of columns from the right getting high-quality titles

# Gradient Overlay
_DEFAULT_ACCENT = (20, 60, 80) # Default fallback glow color (Teal)
_ACCENT_MAP = {}               # Custom accent map mapping TMDB ID -> RGB tuple


# ╔═══════════════════════════════════════════════════════════════════╗
# ║                       INTERNAL CODE                              ║
# ╚═══════════════════════════════════════════════════════════════════╝

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG_BASE = "https://image.tmdb.org/t/p"
BACKDROP_SIZE = "w1280"
POSTER_SIZE = "w780"
FANART_BASE = "https://webservice.fanart.tv/v3"


# -- TMDB Helpers

def _tmdb(endpoint, params=None):
    p = dict(params or {})
    p["api_key"] = TMDB_API_KEY
    r = requests.get(f"{TMDB_BASE}{endpoint}", params=p, timeout=15)
    r.raise_for_status()
    return r.json()


def _pull_tv(extra, count):
    items = []
    for page in range(1, 6):
        data = _tmdb("/discover/tv", {"sort_by": "popularity.desc",
                                      "page": page, "language": "en-US", **extra})
        for item in data.get("results", []):
            if item.get("backdrop_path") or item.get("poster_path"):
                items.append(("tv", item))
        if len(items) >= count:
            break
    return items[:count]


def _pull_movies(extra, count):
    items = []
    for page in range(1, 6):
        data = _tmdb("/discover/movie", {"sort_by": "popularity.desc",
                                         "page": page, "language": "en-US", **extra})
        for item in data.get("results", []):
            if item.get("backdrop_path") or item.get("poster_path"):
                items.append(("movie", item))
        if len(items) >= count:
            break
    return items[:count]


def _calculate_focal_score(item):
    """Scores titles based on popularity and release date recency."""
    pop = float(item.get("popularity", 0))
    date_str = item.get("release_date") or item.get("first_air_date") or ""
    
    if not date_str:
        return pop
        
    try:
        release_year = datetime.strptime(date_str, "%Y-%m-%d").year
        current_year = datetime.now().year
        age = max(1, current_year - release_year)
        recency_multiplier = 1.0 / (age ** 0.5)
        return pop * recency_multiplier
        
    except ValueError:
        return pop


def fetch_titles(tmdb_id, id_type, count):
    items = []
    if id_type == "network":
        items = _pull_tv({"with_networks": tmdb_id}, count)
    elif id_type == "company":
        tv = _pull_tv({"with_companies": tmdb_id}, count)
        movies = _pull_movies({"with_companies": tmdb_id}, count)
        combined = sorted(tv + movies, key=lambda kt: kt[1].get("popularity", 0), reverse=True)
        seen = set()
        for k, item in combined:
            if item["id"] not in seen:
                seen.add(item["id"])
                items.append((k, item))
            if len(items) >= count:
                break
    elif id_type == "provider":
        tv = _pull_tv({"with_watch_providers": tmdb_id, "watch_region": "US"}, count)
        movies = _pull_movies({"with_watch_providers": tmdb_id, "watch_region": "US"}, count)
        combined = sorted(tv + movies, key=lambda kt: kt[1].get("popularity", 0), reverse=True)
        seen = set()
        for k, item in combined:
            if item["id"] not in seen:
                seen.add(item["id"])
                items.append((k, item))
            if len(items) >= count:
                break
    elif id_type == "genre":
        movies = _pull_movies({"with_genres": tmdb_id}, count)
        tv = _pull_tv({"with_genres": tmdb_id}, count)
        combined = sorted(movies + tv, key=lambda kt: kt[1].get("popularity", 0), reverse=True)
        seen = set()
        for k, item in combined:
            if item["id"] not in seen:
                seen.add(item["id"])
                items.append((k, item))
            if len(items) >= count:
                break
    else:
        print(f"  Unknown --type '{id_type}'.")
        sys.exit(1)

    seen, unique = set(), []
    for k, item in items:
        key = (item.get("media_type", k), item["id"])
        if key not in seen:
            seen.add(key)
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


# -- MDBList Helpers

def _parse_mdblist_url(url):
    url = url.strip().rstrip("/")
    m = re.search(r"mdblist\.com/lists/([^/]+)/([^/]+)$", url)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^([^/\s]+)/([^/\s]+)$", url)
    if m and "." not in url and ":" not in url:
        return m.group(1), m.group(2)
    raise ValueError(f"Could not parse MDBList URL: {url!r}")


def fetch_mdblist_items(url, count, sort=None):
    username, slug = _parse_mdblist_url(url)
    label = re.sub(r"[^\w]+", "_", slug.strip().lower()).strip("_") or f"{username}_{slug}"
    key = {"apikey": MDBLIST_API_KEY}
    sort_params = {}
    if sort:
        parts = sort.lower().split(".")
        sort_params["sort"] = parts[0]
        sort_params["order"] = parts[1] if len(parts) > 1 else "desc"

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
    try:
        r = requests.get(f"https://api.mdblist.com/lists/{list_id}/items",
                         params={**key, **sort_params}, timeout=20)
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


# -- Fanart.tv Helpers

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
    if not data:
        return None
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


# -- Image Retrieval

def resolve_image(kind, item, prefer_poster=False):
    tmdb_id = item["id"]
    url = None

    if prefer_poster:
        pp = item.get("poster_path")
        if pp:
            url = f"{TMDB_IMG_BASE}/{POSTER_SIZE}{pp}"
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
            if bp:
                url = f"{TMDB_IMG_BASE}/{BACKDROP_SIZE}{bp}"
        if not url:
            pp = item.get("poster_path")
            if pp:
                url = f"{TMDB_IMG_BASE}/{POSTER_SIZE}{pp}"

    if not url:
        return None

    for attempt in range(3):
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except Exception:
            if attempt == 2:
                return None
            time.sleep(1)


# -- Tile Rendering

def _rounded_mask(w, h, radius):
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w-1, h-1], radius=radius, fill=255)
    return mask


def _make_tile(img, tw, th, opacity=1.0):
    iw, ih = img.size
    tr = tw / th
    sr = iw / ih
    if sr > tr:
        nw = int(ih * tr)
        img = img.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    else:
        nh = int(iw / tr)
        img = img.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
    img = img.resize((tw, th), Image.LANCZOS)
    r = max(2, int(CARD_RADIUS * tw / max(LANDSCAPE_W, 1)))
    out = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    out.paste(img, mask=_rounded_mask(tw, th, r))
    if opacity < 1.0:
        rc, gc, bc, ac = out.split()
        ac = ac.point(lambda v: int(v * opacity))
        out = Image.merge("RGBA", (rc, gc, bc, ac))
    return out


# -- Wallpaper Layout & Perspective Assembly

def _build_layout(portrait_imgs, landscape_imgs, canvas_w, canvas_h, scale):
    lw = int(LANDSCAPE_W * scale)
    lh = int(round(lw * 9 / 16))
    pw = int(PORTRAIT_W * scale)
    ph = int(round(pw * 3 / 2))
    gap = int(GAP * scale)

    rng = random.Random(42)

    bleed_x = (lw + gap) * 3
    bleed_y = max(ph, lh) * 2 + gap * 4

    columns = []
    x = -bleed_x
    pi = 0
    center_x = canvas_w / 2

    while x < canvas_w + bleed_x:
        ct = COL_PATTERN[pi % len(COL_PATTERN)]
        base_w = lw if ct == "L" else pw
        
        col_center_x = x + base_w * 0.5
        if POV_X != 0:
            norm_dist = (col_center_x - center_x) / (canvas_w / 2)
            scale_factor = 1.0 - (POV_X * norm_dist * 0.15)
            cw = int(base_w * max(0.5, min(1.5, scale_factor)))
        else:
            cw = base_w

        columns.append({"x": x, "w": cw, "type": ct})
        x += cw + gap
        pi += 1

    over_w = canvas_w + bleed_x * 2
    over_h = canvas_h + bleed_y * 2
    ox = bleed_x
    oy = bleed_y
    canvas = Image.new("RGBA", (over_w, over_h), (10, 12, 16, 255))

    p_cutoff = max(1, int(len(portrait_imgs) * 0.35))
    l_cutoff = max(1, int(len(landscape_imgs) * 0.35))
    
    pri_portraits = portrait_imgs[:p_cutoff]
    rest_portraits = portrait_imgs[p_cutoff:]
    
    pri_landscapes = landscape_imgs[:l_cutoff]
    rest_landscapes = landscape_imgs[l_cutoff:]

    tiles_to_place = []

    for col_i, col in enumerate(columns):
        col_x = col["x"] + ox
        col_type = col["type"]
        col_w = col["w"]

        screen_x = col["x"] + (col_w * 0.5)
        norm_x = screen_x / canvas_w
        depth = max(0.0, min(1.0, norm_x))
        opacity = FADE_LEFT + (FADE_RIGHT - FADE_LEFT) * depth

        stagger_y = int(ph * COL_STAGGER) if col_i % 2 == 1 else 0
        y = -bleed_y + stagger_y + oy

        while y < over_h:
            flip = rng.random() < RANDOM_ASPECT_CHANCE
            tile_type = ("P" if col_type == "L" else "L") if flip else col_type

            tw = col_w
            th = max(4, int(tw * 3 / 2)) if tile_type == "P" else max(4, int(tw * 9 / 16))

            screen_y = y - oy + (th * 0.5)
            norm_y = screen_y / canvas_h

            dist_to_focus = math.hypot(norm_x - FOCUS_X, norm_y - FOCUS_Y)
            is_focal_area = dist_to_focus <= FOCUS_RADIUS
            is_on_screen = (0.0 <= norm_x <= 1.0) and (0.0 <= norm_y <= 1.0)

            tiles_to_place.append({
                "x": col_x, "y": y, "w": tw, "h": th, "type": tile_type,
                "is_focal": is_focal_area, "is_on_screen": is_on_screen, "opacity": opacity
            })
            y += th + gap

    # Process focal and onscreen tiles first
    tiles_to_place.sort(key=lambda t: (not t["is_on_screen"], not t["is_focal"]))

    # A set to guarantee a title is never reused for a different mode
    placed_ids = set()

    def pick_next(src_list, fallback_list, placed_set, repeat_idx):
        """Picks the best available title that hasn't been placed yet."""
        # Search for the first unique item that hasn't been used on the canvas
        for i, item in enumerate(src_list):
            if item["id"] not in placed_set:
                placed_set.add(item["id"])
                return src_list.pop(i), repeat_idx

        # If everything in uniques has been placed, pick from the looping backup list
        if fallback_list:
            item = fallback_list[repeat_idx % len(fallback_list)]
            placed_set.add(item["id"])
            return item, repeat_idx + 1
        return None, repeat_idx

    pri_port_idx, rest_port_idx = 0, 0
    pri_land_idx, rest_land_idx = 0, 0

    for t in tiles_to_place:
        src = None
        if t["type"] == "L":
            if t["is_focal"]:
                src, pri_land_idx = pick_next(pri_landscapes, pri_landscapes, placed_ids, pri_land_idx)
            else:
                src, rest_land_idx = pick_next(rest_landscapes, rest_landscapes, placed_ids, rest_land_idx)
        else:
            if t["is_focal"]:
                src, pri_port_idx = pick_next(pri_portraits, pri_portraits, placed_ids, pri_port_idx)
            else:
                src, rest_port_idx = pick_next(rest_portraits, rest_portraits, placed_ids, rest_port_idx)

        if src:
            tile = _make_tile(src["img"], t["w"], t["h"], opacity=t["opacity"])
            canvas.paste(tile, (int(t["x"]), int(t["y"])), tile)

    return canvas, ox, oy


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


def _apply_dof(image, scale=1.0):
    if DOF_BLUR_MAX <= 0:
        return image

    w, h = image.size
    fx = DOF_FOCUS_X * w
    fy = DOF_FOCUS_Y * h
    diag = math.hypot(w, h)

    xs = np.linspace(0, w - 1, w, dtype=np.float32)
    ys = np.linspace(0, h - 1, h, dtype=np.float32)
    xg, yg = np.meshgrid(xs, ys)
    dist_map = np.sqrt((xg - fx)**2 + (yg - fy)**2) / diag
    blur_map = np.clip(dist_map ** DOF_FALLOFF, 0.0, 1.0)

    N = 5
    max_r = DOF_BLUR_MAX * scale
    layers = [image if (i / N) * max_r < 0.5 else
              image.filter(ImageFilter.GaussianBlur(radius=(i / N) * max_r))
              for i in range(N + 1)]

    arrs = [np.array(l, dtype=np.float32) for l in layers]
    out = np.zeros_like(arrs[0])

    for i in range(N):
        lo = i / N
        hi = (i + 1) / N
        in_ = (blur_map >= lo) & (blur_map < hi)
        t = ((blur_map - lo) / (hi - lo + 1e-9))[in_]
        out[in_] = arrs[i][in_] * (1 - t[:, None]) + arrs[i+1][in_] * t[:, None]

    out[blur_map >= (N - 1) / N] = arrs[N][blur_map >= (N - 1) / N]

    return Image.fromarray(out.clip(0, 255).astype(np.uint8), image.mode)


def _apply_gradient(canvas, accent, show_gradient=True):
    if not show_gradient:
        return canvas
    w, h = canvas.size
    ar, ag, ab = accent

    def grad_left(gw, gh):
        """Fade from left edge."""
        img = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
        px = img.load()
        for x in range(int(gw * 0.65)):
            t = 1.0 - x / (gw * 0.65)
            a = int(240 * (t ** 1.4))
            if a:
                for y in range(gh):
                    px[x, y] = (6, 8, 12, a)
        return img

    def grad_bottom(gw, gh):
        """Fade from bottom edge."""
        img = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
        px = img.load()
        for y in range(gh):
            t = max(0.0, (y - gh * 0.55) / (gh * 0.45))
            a = int(215 * (t ** 1.3))
            if a:
                for x in range(gw):
                    px[x, y] = (6, 8, 12, a)
        return img

    def accent_glow(gw, gh):
        """Top-right accent glow."""
        img = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
        dw = ImageDraw.Draw(img)
        for i in range(18):
            t = i / 18
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


def main():
    parser = argparse.ArgumentParser(description="Generate a mixed portrait/landscape grid wallpaper.")
    parser.add_argument("--id", type=int, nargs="+", default=None)
    parser.add_argument("--type", default=None, help="network | provider | company | genre")
    parser.add_argument("--url", default=None, help="MDBList URL or 'username/list-slug'")
    parser.add_argument("--sort", default=None, help="MDBList sort, e.g. imdbrating.desc")
    parser.add_argument("--output", default=None)
    parser.add_argument("--no-gradient", action="store_true")
    args = parser.parse_args()

    tmdb_ids = args.id if args.id is not None else ([TMDB_ID] if TMDB_ID else None)
    id_type = args.type if args.type is not None else ID_TYPE
    mdblist_url = args.url if args.url is not None else MDBLIST_URL
    out_dir = args.output if args.output is not None else OUTPUT_DIR
    use_mdblist = bool(mdblist_url)

    if not use_mdblist and (not tmdb_ids or not id_type):
        print("\n  ✗  Provide --url OR --id + --type\n")
        sys.exit(1)
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
        file_4k = f"type02_mdblist_{label}_4k.jpg"
        file_1080p = f"type02_mdblist_{label}_1080p.jpg"
        print(f"  Mode   : MDBList\n  URL    : {mdblist_url}\n")
    else:
        labels = [_fetch_label(tid, id_type) for tid in tmdb_ids]
        label = "_".join(labels)
        file_4k = f"type02_{id_type}_{label}_4k.jpg"
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
    portrait_imgs, landscape_imgs = [], []
    fail_n = 0

    for i, (kind, item) in enumerate(titles):
        name = item.get("name") or item.get("title") or str(item["id"])
        sys.stdout.write(f"  [{i+1:02d}/{len(titles)}]  {name[:52]:<52}\r")
        sys.stdout.flush()
        
        land = resolve_image(kind, item, prefer_poster=False)
        port = resolve_image(kind, item, prefer_poster=True)
        
        # Store both image and TMDB ID to prevent cross-mode duplicates
        if land:
            landscape_imgs.append({"id": item["id"], "img": land})
        if port:
            portrait_imgs.append({"id": item["id"], "img": port})
        if not land and not port:
            fail_n += 1

    print(f"\n  {len(landscape_imgs)} landscape,  {len(portrait_imgs)} portrait,  {fail_n} failed\n")

    if not landscape_imgs and not portrait_imgs:
        print("  No images downloaded.")
        sys.exit(1)

    if not portrait_imgs:
        portrait_imgs = landscape_imgs[:]
    if not landscape_imgs:
        landscape_imgs = portrait_imgs[:]

    def _spatial_priority_sort(imgs):
        priority_cutoff = max(1, int(len(imgs) * 0.35))
        pri = imgs[:priority_cutoff]
        rest = imgs[priority_cutoff:]
        random.shuffle(rest)
        return pri + rest

    portrait_imgs = _spatial_priority_sort(portrait_imgs)
    landscape_imgs = _spatial_priority_sort(landscape_imgs)

    show_grad = not args.no_gradient

    # ── Render ────────────────────────────────────────────────────────────────
    show_grad = not args.no_gradient

    print("Compositing 4K (3840×2160)…")
    over4k, ox4k, oy4k = _build_layout(portrait_imgs, landscape_imgs, 3840, 2160, scale=2.0)
    warped4k = _perspective_warp(over4k, ox4k, oy4k, 3840, 2160, POV_X, POV_Y)
    
    # Restored: Apply the depth of field blur
    dof4k = _apply_dof(warped4k, scale=2.0)

    # ── Adaptive Output Paths ─────────────────────────────────────────────────
    BASE_DIR = Path(__file__).resolve().parent.parent / "collections"
    
    single_id = args.id[0] if args.id else None

    if args.type == "network":
        subfolder = "networks"
        api_type = "network"
    elif args.type in ("company", "production_company"):
        subfolder = "companies"
        api_type = "company"
    else:
        subfolder = "genres"
        api_type = "genre"

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
    
    out_dir = BASE_DIR / subfolder / f"{single_id}-{slug}" / "backdrops"
    out_dir.mkdir(parents=True, exist_ok=True)

    file_4k = out_dir / "t2_flat_4k.jpg"
    file_1080p = out_dir / "t2_falt_1080p.jpg"

    # Save using the blurred dof4k image
    _save(_apply_gradient(dof4k, accent, show_grad), file_4k)

    print("Compositing 1080p (1920×1080)…")
    over1080, ox1080, oy1080 = _build_layout(portrait_imgs, landscape_imgs, 1920, 1080, scale=1.0)
    warped1080 = _perspective_warp(over1080, ox1080, oy1080, 1920, 1080, POV_X, POV_Y)
    
    # Restored here too: Apply the depth of field blur
    dof1080 = _apply_dof(warped1080, scale=1.0)
    
    # Save using the blurred dof1080 image
    _save(_apply_gradient(dof1080, accent, show_grad), file_1080p)

    print(f"\n  ✓ T2 Backdrops saved to: {out_dir.relative_to(BASE_DIR.parent)}")


if __name__ == "__main__":
    main()