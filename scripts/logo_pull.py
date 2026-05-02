#!/usr/bin/env python3
"""
logo_pull.py — Download logos from TMDB and save them maxed out to 1920×1080.
Applies smart color/black detection, contrast-preserving detail extraction,
and visual deduplication to ignore highly similar or duplicate logos.
"""

import argparse
import io
import re
import sys
from pathlib import Path
import requests
from PIL import Image, ImageOps, ImageFilter

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
TMDB_API_KEY = ""
MAX_LOGOS    = 5

# Base collections folder relative to the script location
BASE_DIR = Path(__file__).resolve().parent.parent / "collections"

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def get_brand_name(id_type, tmdb_id):
    url = f"https://api.themoviedb.org/3/{id_type}/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("name") or data.get("title") or f"unknown-{tmdb_id}"
    except Exception:
        return f"unknown-{tmdb_id}"

def are_images_similar(img1, img2, threshold=12.0):
    """
    Compares two images to check if they are visually identical.
    Increased to a 64x64 thumbnail to preserve small details like the Apple TV '+' sign.
    """
    # Create slightly larger thumbnails to capture small but unique logo details
    t1 = img1.convert("RGBA").resize((32, 32), Image.Resampling.BILINEAR)
    t2 = img2.convert("RGBA").resize((32, 32), Image.Resampling.BILINEAR)
    
    p1 = list(t1.getdata())
    p2 = list(t2.getdata())
    
    total_diff = 0
    num_pixels = len(p1)
    
    for i in range(num_pixels):
        r_diff = abs(p1[i][0] - p2[i][0])
        g_diff = abs(p1[i][1] - p2[i][1])
        b_diff = abs(p1[i][2] - p2[i][2])
        a_diff = abs(p1[i][3] - p2[i][3])
        total_diff += (r_diff + g_diff + b_diff + a_diff) / 4.0
        
    avg_diff = total_diff / num_pixels
    return avg_diff < threshold

def process_color_logo(img):
    img = img.convert("RGBA")
    r, g, b, a = img.split()
    
    pixels = img.load()
    width, height = img.size
    
    for y in range(height):
        for x in range(width):
            pr, pg, pb, pa = pixels[x, y]
            if pa == 0:
                continue
            
            brightness = (0.299 * pr + 0.587 * pg + 0.114 * pb)
            color_variance = max(abs(pr - pg), abs(pg - pb), abs(pb - pr))
            
            # If the pixel is dark enough and has no strong color tone, invert to white
            if brightness < 60 and color_variance < 35:
                pixels[x, y] = (255, 255, 255, pa)

    return img

def process_white_logo(img):
    """
    Advanced cutout mask:
    - Pre-scan: Skips conversion if original is monochrome/white.
    - Cutout: Erases white/near-white interiors while protecting yellow and colors.
    - Post-filter: Discards garbage files with tiny fragments or stray pixels.
    """
    img = img.convert("RGBA")
    pixels = img.load()
    width, height = img.size
    
    # ── 1. Pre-scan: Check if there's any vibrant color at all ──
    has_vibrant_color = False
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a > 0:
                color_variance = max(r, g, b) - min(r, g, b)
                brightness = (0.299 * r + 0.587 * g + 0.114 * b)
                
                # Lowered from 30 down to 20 to catch faint/small gradient colors
                if color_variance > 30 and brightness > 40:
                    has_vibrant_color = True
                    break
        if has_vibrant_color:
            break

    if not has_vibrant_color:
        print("  ℹ Logo is already monochrome/white. Skipping extra white file conversion.")
        return None

    # ── 2. Run the cutout processing for true color logos ──
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            
            if a == 0:
                continue
            
            # Protect bright yellow elements
            is_yellow = (r > 180 and g > 180 and b < 140)
            
            # Match white or near-white interior fills
            is_white_or_near_white = (r > 200 and g > 200 and b > 200)
            
            if is_white_or_near_white and not is_yellow:
                pixels[x, y] = (0, 0, 0, 0)
                continue
            
            # Detect colorful/vibrant regions
            color_variance = max(r, g, b) - min(r, g, b)
            
            # Also use lower variance threshold here to preserve faint colors
            if color_variance > 20 or is_yellow:
                pixels[x, y] = (255, 255, 255, a)
            else:
                pixels[x, y] = (0, 0, 0, 0)

    # Gently smooth out edges
    smoothed_img = img.filter(ImageFilter.SMOOTH)
    
    # ── 3. Post-scan: Filter out tiny undesirable fragments ──
    final_pixels = smoothed_img.load()
    visible_count = 0
    total_pixels = width * height
    
    for y in range(height):
        for x in range(width):
            if final_pixels[x, y][3] > 30:
                visible_count += 1
                
    if visible_count < (total_pixels * 0.03):
        print("  ℹ Cutout results in a nearly blank image or stray fragments. Ignoring file.")
        return None

    return smoothed_img

def download_logos(tmdb_id, id_type, max_logos):
    name = get_brand_name(id_type, tmdb_id)
    slug = slugify(name)
    
    subfolder = "networks" if id_type == "network" else "companies"
    brand_folder = BASE_DIR / subfolder / f"{tmdb_id}-{slug}"
    
    color_dir = brand_folder / "logos" / "color"
    white_dir = brand_folder / "logos" / "white"
    
    color_dir.mkdir(parents=True, exist_ok=True)
    white_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Brand: {name} ({tmdb_id})")
    print(f"  Target: {brand_folder.relative_to(BASE_DIR.parent)}")

    url = f"https://api.themoviedb.org/3/{id_type}/{tmdb_id}/images"
    params = {"api_key": TMDB_API_KEY}
    
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        images = r.json().get("logos", [])
    except Exception as e:
        print(f"  ✗ Failed to fetch images from TMDB: {e}")
        return

    if not images:
        print("  ✗ No valid logos found.")
        return

    # Track processed canvas outputs for duplicate matching
    accepted_canvases = []
    
    count = 0
    saved_index = 1
    
    for img_meta in images:
        if count >= max_logos:
            break
            
        file_path = img_meta["file_path"]
        img_url = f"https://image.tmdb.org/t/p/original{file_path}"
        
        try:
            img_res = requests.get(img_url, timeout=15)
            img_res.raise_for_status()
            img = Image.open(io.BytesIO(img_res.content)).convert("RGBA")
        except Exception as e:
            print(f"  ✗ Failed downloading {file_path}: {e}")
            continue

        # Resize to 1920x1080 canvas
        canvas = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        iw, ih = img.size
        scale = min(1920 / iw, 1080 / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img_resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        
        ox, oy = (1920 - nw) // 2, (1080 - nh) // 2
        canvas.paste(img_resized, (ox, oy), img_resized)

        # Check canvas for visual duplicates
        is_dup = False
        for prev_canvas in accepted_canvases:
            if are_images_similar(canvas, prev_canvas):
                print(f"  ℹ Skipping duplicate or highly similar logo: {file_path}")
                is_dup = True
                break
                
        if is_dup:
            continue

        # Validated: Keep this in memory to compare against the next logo
        accepted_canvases.append(canvas)

        # 1. Process and save color logo
        color_out = process_color_logo(canvas)
        out_name = f"{tmdb_id}_color_{saved_index}.png"
        color_out.save(color_dir / out_name, "PNG")

        # 2. Process and save the custom white detailed version
        white_out = process_white_logo(canvas)
        if white_out is not None:
            out_white = f"{tmdb_id}_white_{saved_index}.png"
            white_out.save(white_dir / out_white, "PNG")
            print(f"  ✓ Saved: {out_name} & {out_white}")
        else:
            print(f"  ✓ Saved: {out_name} (Color folder contains the white version)")
            
        count += 1
        saved_index += 1

    print(f"  Successfully pulled {count} unique logos.\n")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, nargs="+", required=True)
    ap.add_argument("--type", choices=["network", "company"], required=True)
    ap.add_argument("--max", type=int, default=MAX_LOGOS)
    args = ap.parse_args()

    for i in args.id:
        download_logos(i, "network" if args.type == "network" else "company", args.max)