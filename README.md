# Prism Wallpapers

An advanced automation suite for creating luxury media backdrops and logo cards. Designed to construct perfectly balanced, visually high-end brand assets using custom visual math, dynamic perspective warping, and spatial gradient mesh engines.

---

## 📁 Repository Structure

prism-wallpapers/
├── collections/
│   ├── networks/          # Network brand assets (logos, cards, backdrops)
│   └── companies/         # Company brand assets
├── scripts/
│   ├── backdrop_T2.py     # Advanced perspective-warped backdrops
│   └── logo_cards.py      # Precision logo card and gradient mesh generator
└── README.md


---

## 🛠️ Installation & Requirements

Ensure you have Python 3.8+ installed along with the required imaging libraries:

```bash
pip install pillow numpy requests
```

🎨 Tool 1: logo_cards.py

This script places cropped, maximum-scale logos onto background cards. It features an integrated Design Hotfix Registry for precise positional nudges and scale corrections, alongside advanced linear, radial, and multi-point mesh gradient generators.
⚙️ Designer Customizations (Code Tweaks)

To customize the core layout math without changing any command line logic, open logo_cards.py and adjust the configuration parameters at the top:
```Python
# Standard margin around the logo (Higher value = smaller logo / more breathing room)
MARGIN_MIN = 240  

# Visual Mass Centering (Slack)
# 0.0 = Pure Bounding Box Center
# 1.0 = Optical Center (Balances heavy elements like asymmetric text or swooshes)
SLACK_X = 0.5
SLACK_Y = 0.5

# Visual Mass Density Rules
DENSITY_THRESHOLD = 0.23  # Cutoff for sparse vs. bold logos
DENSITY_BOOST = 1.18      # Size increase modifier for thin/sparse logos
```
🚀 Usage Syntax
```Bash
python3 logo_cards.py --source <networks|companies|both> --bg "<background-spec>"
```
📋 Background Configuration Options (--bg)
1. Solid Color
```Bash
python3 logo_cards.py --source both --bg "0d0d11"
```
2. Linear Gradient (with Rotation)

Format: linear:HEX1:HEX2[:ANGLE]

Example:
```Bash
python3 logo_cards.py --source both --bg "linear:151515:282828:45"
```
3. Radial Gradient (with Custom Center)

Center coordinates are expressed as decimal percentages (0.0 to 1.0).

Format: radial:HEX_CORE:HEX_OUTER[:CX:CY]

  
Example:
```Bash
python3 logo_cards.py --source both --bg "radial:24242c:0f0f13:0.35:0.35"
```
4. Dual Radial Pseudo-Mesh (Luxury Double Pool)

Renders two overlapping radial color cores blending perfectly into a common outer background.

Format: dual:HEX_CORE1:HEX_CORE2:HEX_OUTER:CX1:CY1:CX2:CY2

Example:
```Bash
python3 logo_cards.py --source both --bg "dual:2d1d2d:231a3a:0e0914:0.3:0.5:0.7:0.5"
```
🖼️ Tool 2: backdrop_T2.py

Creates mixed portrait and landscape grid wallpapers complete with custom perspective warping, depth of field effects, and thematic overlay gradients.
⚙️ Advanced Layout & Perspective Customization

Open backdrop_T2.py in your code editor to fine-tune the master 3D space, tilt transformations, and optical depth effects.
```Python

# --- 3D CAMERA & PERSPECTIVE CONTROL ---
TILT_DEG = 12        # Clockwise rotation angle for the grid plane
WARP_FACTOR = 0.0008 # Controls the intensity of the perspective/vanishing point
DEPTH_SCALE = 1.15   # Z-axis intensity (compression of distant grid items)

# --- GRID GEOMETRY & SPACING ---
GRID_ROWS = 4        # Total horizontal tiers in the layout
GRID_COLS = 7        # Total columns per tier
X_SPACING = 32       # Horizontal gap between portrait/landscape thumbnails
Y_SPACING = 24       # Vertical gap between thumbnails

# --- DEPTH OF FIELD (DOF) BLUR ENGINE ---
BLUR_MIN = 0         # Focus point blur intensity (0 = crystal clear)
BLUR_MAX = 8         # Maximum blur applied to items at the edge of the field
BLUR_FALLOFF = 1.4   # Exponential rate of blur increase from focus center
```
🚀 Usage Syntax
```Bash
python3 backdrop_T2.py --id <TMDB_ID> --type <network|provider|company|genre>
```
🔧 Overriding Specific Logos (Design Hotfixes)

If a specific logo needs manual tuning due to an outlier shape, edit the DESIGN_HOTFIXES registry in logo_cards.py:
```Python
DESIGN_HOTFIXES = {
    "card_6219_": {
        "nudge_x": -35,   # Move 35px to the left
        "nudge_y": 0,     # Keep vertical center
        "scale_mod": 1.0  # Maintain baseline scale
    },
    "card_1112_": {
        "nudge_x": 0,
        "nudge_y": 0,
        "scale_mod": 1.15 # 15% size boost
    }
}
```
