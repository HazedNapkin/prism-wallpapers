#!/usr/bin/env python3
"""
logo_cards.py — Luxury backdrop creation with advanced gradient engines.
Supports standard layouts, dynamic hotfixes, and advanced color mesh engines.
"""

import argparse
import sys
import math
from pathlib import Path
from PIL import Image

# Core directory configurations
BASE_DIR = Path(__file__).resolve().parent.parent / "collections"
CARD_W = 1920
CARD_H = 1080
MARGIN_MIN = 240  # Visual safety margin

# --- Hotfix override configurations
DESIGN_HOTFIXES = {
    "card_6_": {"nudge_x": -15, "nudge_y": -12, "scale_mod": 1.0},
    "card_6219_": {"nudge_x": -35, "nudge_y": 0, "scale_mod": 1.0},
    "card_2552_": {"nudge_x": 0, "nudge_y": 0, "scale_mod": 1.15},
    "card_2739_": {"nudge_x": 0, "nudge_y": 0, "scale_mod": 1.15},
    "card_1112_": {"nudge_x": 0, "nudge_y": 0, "scale_mod": 1.15},
}

def parse_color(hex_str):
    h = hex_str.lstrip("#")
    return int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def parse_bg_spec(spec):
    """
    Parses a wide range of solid and gradient types into high quality backdrops.
    """
    if not spec or spec.lower() == "transparent":
        return None
    
    parts = spec.split(":")
    
    # 1. Solid background
    if len(parts) == 1:
        hex_val = parts[0].lstrip("#")
        return Image.new("RGBA", (CARD_W, CARD_H), f"#{hex_val}")
    
    # 2. Linear Gradient (with optional angle)
    # Format: linear:HEX1:HEX2[:ANGLE]
    if parts[0].lower() == "linear" and len(parts) >= 3:
        c1, c2 = parts[1], parts[2]
        angle = float(parts[3]) if len(parts) >= 4 else 0.0
        
        rad = math.radians(angle)
        dx, dy = math.cos(rad), math.sin(rad)
        
        corners = [
            (-CARD_W/2, -CARD_H/2), (CARD_W/2, -CARD_H/2),
            (-CARD_W/2, CARD_H/2), (CARD_W/2, CARD_H/2)
        ]
        projections = [cx * dx + cy * dy for cx, cy in corners]
        min_p, max_p = min(projections), max(projections)
        dist = max_p - min_p
        
        rgb1, rgb2 = parse_color(c1), parse_color(c2)
        img = Image.new("RGBA", (CARD_W, CARD_H))
        pixels = img.load()
        
        for x in range(CARD_W):
            for y in range(CARD_H):
                proj = (x - CARD_W/2) * dx + (y - CARD_H/2) * dy
                t = (proj - min_p) / dist if dist != 0 else 0
                t = max(0.0, min(1.0, t))
                
                r = int(rgb1[0] * (1 - t) + rgb2[0] * t)
                g = int(rgb1[1] * (1 - t) + rgb2[1] * t)
                b = int(rgb1[2] * (1 - t) + rgb2[2] * t)
                pixels[x, y] = (r, g, b, 255)
        return img

    # 3. Radial Gradient (with custom center coordinates)
    # Format: radial:HEX_CORE:HEX_OUTER[:CX:CY]
    if parts[0].lower() == "radial" and len(parts) >= 3:
        c1, c2 = parts[1], parts[2]
        cx = float(parts[3]) if len(parts) >= 5 else 0.5
        cy = float(parts[4]) if len(parts) >= 5 else 0.5
        
        px, py = cx * CARD_W, cy * CARD_H
        max_d = math.sqrt(max(px, CARD_W - px)**2 + math.sqrt(max(py, CARD_H - py)**2))
        
        rgb1, rgb2 = parse_color(c1), parse_color(c2)
        img = Image.new("RGBA", (CARD_W, CARD_H))
        pixels = img.load()
        
        for x in range(CARD_W):
            for y in range(CARD_H):
                d = math.sqrt((x - px)**2 + (y - py)**2)
                t = min(1.0, d / max_d)
                
                r = int(rgb1[0] * (1 - t) + rgb2[0] * t)
                g = int(rgb1[1] * (1 - t) + rgb2[1] * t)
                b = int(rgb1[2] * (1 - t) + rgb2[2] * t)
                pixels[x, y] = (r, g, b, 255)
        return img

    # 4. Dual-Center Radial Pseudo-Mesh
    # Format: dual:HEX_CORE1:HEX_CORE2:HEX_OUTER:CX1:CY1:CX2:CY2
    if parts[0].lower() == "dual" and len(parts) >= 8:
        c_core1, c_core2, c_outer = parts[1], parts[2], parts[3]
        cx1, cy1 = float(parts[4]), float(parts[5])
        cx2, cy2 = float(parts[6]), float(parts[7])
        
        rgb1, rgb2, rgb_out = parse_color(c_core1), parse_color(c_core2), parse_color(c_outer)
        px1, py1 = cx1 * CARD_W, cy1 * CARD_H
        px2, py2 = cx2 * CARD_W, cy2 * CARD_H
        
        # Smooth falloff radius (takes up roughly 45% of visual layout)
        max_d1 = math.sqrt(CARD_W**2 + CARD_H**2) * 0.45
        max_d2 = math.sqrt(CARD_W**2 + CARD_H**2) * 0.45
        
        img = Image.new("RGBA", (CARD_W, CARD_H))
        pixels = img.load()
        
        for x in range(CARD_W):
            for y in range(CARD_H):
                d1 = math.sqrt((x - px1)**2 + (y - py1)**2)
                d2 = math.sqrt((x - px2)**2 + (y - py2)**2)
                
                op1 = max(0.0, 1.0 - (d1 / max_d1))
                op2 = max(0.0, 1.0 - (d2 / max_d2))
                
                # Normalize overlaps to prevent clipping
                tot = op1 + op2
                if tot > 1.0:
                    op1 /= tot
                    op2 /= tot
                    
                op_out = max(0.0, 1.0 - (op1 + op2))
                
                r = int(rgb1[0] * op1 + rgb2[0] * op2 + rgb_out[0] * op_out)
                g = int(rgb1[1] * op1 + rgb2[1] * op2 + rgb_out[1] * op_out)
                b = int(rgb1[2] * op1 + rgb2[2] * op2 + rgb_out[2] * op_out)
                pixels[x, y] = (r, g, b, 255)
        return img

    # Standard two-color gradient fallback
    if len(parts) >= 2:
        c1, c2 = parts[0], parts[1]
        rgb1, rgb2 = parse_color(c1), parse_color(c2)
        img = Image.new("RGBA", (CARD_W, CARD_H))
        pixels = img.load()
        for y in range(CARD_H):
            t = y / float(CARD_H - 1)
            r = int(rgb1[0] * (1 - t) + rgb2[0] * t)
            g = int(rgb1[1] * (1 - t) + rgb2[1] * t)
            b = int(rgb1[2] * (1 - t) + rgb2[2] * t)
            row = Image.new("RGBA", (CARD_W, 1), (r, g, b, 255))
            img.paste(row, (0, y))
        return img
    
    return None

def process_brand_folder(brand_path, bg_spec, bg_name):
    """Process a single brand directory to create logo cards."""
    logos_color_dir = brand_path / "logos" / "color"
    logos_white_dir = brand_path / "logos" / "white"
    
    if not logos_color_dir.exists() and not logos_white_dir.exists():
        return

    # Translate background spec name safely for directories
    clean_bg_name = bg_name.replace(":", "_").replace("#", "")
    out_dir = brand_path / "cards" / clean_bg_name
    out_dir.mkdir(parents=True, exist_ok=True)

    for variant, folder in [("color", logos_color_dir), ("white", logos_white_dir)]:
        if not folder.exists():
            continue
            
        for logo_file in folder.glob("*.png"):
            try:
                logo_img = Image.open(logo_file).convert("RGBA")
            except Exception as e:
                print(f"  ✗ Failed loading {logo_file.name}: {e}")
                continue

            # Auto-crop transparent boundaries
            bbox = logo_img.getbbox()
            if bbox:
                logo_img = logo_img.crop(bbox)

            canvas = bg_spec.copy() if bg_spec else Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))

            lw, lh = logo_img.size

            # Match exact design hotfix based on name pattern
            hotfix = None
            for key, config in DESIGN_HOTFIXES.items():
                if key in logo_file.name:
                    hotfix = config
                    break

            # Core geometric scale
            scale = min((CARD_W - 2 * MARGIN_MIN) / lw, (CARD_H - 2 * MARGIN_MIN) / lh)

            # Apply scale override if registered
            if hotfix and "scale_mod" in hotfix:
                scale *= hotfix["scale_mod"]

            nw, nh = int(lw * scale), int(lh * scale)

            # Ensure image stays safely within physical boundaries
            nw = min(nw, CARD_W - 80)
            nh = min(nh, CARD_H - 80)

            logo_resized = logo_img.resize((nw, nh), Image.Resampling.LANCZOS)

            # Center positioning coordinates
            ox = (CARD_W - nw) // 2
            oy = (CARD_H - nh) // 2

            # Apply nudges if registered
            if hotfix:
                ox += hotfix.get("nudge_x", 0)
                oy += hotfix.get("nudge_y", 0)

            canvas.paste(logo_resized, (ox, oy), logo_resized)

            # Save the final card output
            card_filename = f"card_{logo_file.stem}.png"
            canvas.save(out_dir / card_filename, "PNG")
            
            status_msg = f"  ✓ Created card: {clean_bg_name}/{card_filename}"
            if hotfix:
                status_msg += " [Hotfix Applied]"
            print(status_msg)

def run_logo_cards(source, bg_spec_str):
    bg_name = bg_spec_str if bg_spec_str else "transparent"
    bg_spec = parse_bg_spec(bg_spec_str)

    categories = []
    if source in ("networks", "both"): categories.append(BASE_DIR / "networks")
    if source in ("companies", "both"): categories.append(BASE_DIR / "companies")

    for cat in categories:
        if not cat.exists():
            continue
        for brand_folder in cat.iterdir():
            if brand_folder.is_dir():
                process_brand_folder(brand_folder, bg_spec, bg_name)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["networks", "companies", "both"], default="both")
    ap.add_argument("--bg", default=None, help="E.g., 'linear:151515:2a2a2a:45' or 'radial:2c2c2c:0f0f0f:0.3:0.4' or 'dual:323232:262626:111111:0.3:0.5:0.7:0.5'")
    args = ap.parse_args()
    
    run_logo_cards(args.source, args.bg)