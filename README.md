# Prism Wallpapers

An advanced automation suite for creating luxury media backdrops and logo cards. Designed to construct perfectly balanced, visually high-end brand assets using custom visual math, dynamic perspective warping, and spatial gradient mesh engines.

![Nuvio Media Backdrop](https://github.com/bramst0ne/prism-wallpapers/blob/main/collections/networks/213-netflix/backdrops/t2_flat_4k.jpg)

---

## 🚀 Beginner Installation Guide

Welcome! This guide will help you get the required tools installed on your computer so you can run the scripts.

---

### Step 1: Install Python (and add it to your system PATH)

Python is the programming language used to run our wallpaper automation tools.

#### 🪟 On Windows:
1. Go to the official [Python Downloads page](https://www.python.org/downloads/) and download it.
2. Open the downloaded installer file.
   **CRITICAL STEP:** At the bottom of the installer window, check the box that says **"Add python.exe to PATH"** before clicking "Install Now". 
   *(If you miss this step, your computer won't recognize Python commands).*

#### 🍏 macOS & 🐧 Linux:
1. Open your Terminal.
2. Type the following command to install Python:
   * **On Mac:** `xcode-select --install`
   * **On Ubuntu/Debian Linux:** `sudo apt update && sudo apt install python3 python3-pip`

---

### Step 2: Verify Your Installation

Let's make sure everything was installed correctly.

1. Open your terminal
2. Type the following command and hit Enter:
   ```bash
   python --version
   ```
   *Note: If you are on Windows or Mac/Linux and that doesn't work, try typing `python3 --version` instead.*

If you see something like `Python 3.11.x` (or a higher number), you are good to go!

---

### Step 3: Download this Project

To get all the scripts onto your computer:
1. Scroll to the top of this GitHub page.
2. Click **Code** button, and **Download ZIP**
3. Extract the ZIP file anywhere on your computer (for example, your Desktop or Documents folder).

---

### Step 4: Open Terminal inside the Project Folder

You need to tell your command prompt to look directly inside the project directory:

1. Open your terminal (Command Prompt on Windows / Terminal on Mac/Linux).
2. Type `cd` followed by a space.
3. Drag and drop the folder you extracted in **Step 3** directly into the terminal window. It will paste the path automatically.
4. Hit Enter. It should look something like this:
   ```bash
   cd /path/to/prism-wallpapers
   ```

---

### Step 5: Install Python Tools (Pip & NumPy)

Python uses a tool called `pip` to download extras like **NumPy** and **Pillow** which are required to run the scripts. We have put all the requirements into a single file for you.

Run this command in your terminal and press Enter:

```bash
pip install -r requirements.txt
```
*(If you used `python3` earlier, you may need to use `pip3 install -r requirements.txt` instead).*

Once the installation finishes, your setup is complete! You are ready to generate your first wallpaper.

---
![Nuvio Media Backdrop](https://github.com/bramst0ne/prism-wallpapers/blob/main/collections/networks/2552-apple-tv/backdrops/t2_1080p.jpg)
---
## Project Structure

```text
prism-wallpapers/
├── .gitignore
├── README.md
├── requirements.txt
└── scripts/
    ├── backdrop_T1.py
    ├── backdrop_T1_flat.py
    ├── backdrop_T2.py
    ├── backdrop_T2_flat.py
    ├── logo_cards.py
    └── logo_pull.py
```

---

## 🔑 Setting Up Your API Keys (.env file)

This project connects to **TMDb**, **Fanart.tv**, and **Mdblist** to pull high-quality logos and media assets.

---

#### Add your API keys
Open your newly created `.env` from `.env.example` file in any text editor (like Notepad or VS Code) and paste your actual keys after the `=` signs:

```text
TMDB_API_KEY=your_actual_tmdb_key_here
FANART_API_KEY=your_actual_fanart_key_here
MDBLIST_API_KEY=your_actual_mdblist_key_here
```

#### Step 3: Save the file
Save and close the file. You're done! 

Now when you run the scripts or use the `generate.sh` pipeline, your computer will automatically load these keys into memory.

---

## 🎨 Tool 1: logo_cards.py

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
# 1. Solid Color
```Bash
python3 logo_cards.py --source both --bg "0d0d11"
```
# 2. Linear Gradient (with Rotation)

Format: linear:HEX1:HEX2[:ANGLE]

Example:
```Bash
python3 logo_cards.py --source both --bg "linear:151515:282828:45"
```
# 3. Radial Gradient (with Custom Center)

Center coordinates are expressed as decimal percentages (0.0 to 1.0).

Format: radial:HEX_CORE:HEX_OUTER[:CX:CY]

  
Example:
```Bash
python3 logo_cards.py --source both --bg "radial:24242c:0f0f13:0.35:0.35"
```
# 4. Dual Radial Pseudo-Mesh (Luxury Double Pool)

Renders two overlapping radial color cores blending perfectly into a common outer background.

Format: dual:HEX_CORE1:HEX_CORE2:HEX_OUTER:CX1:CY1:CX2:CY2

Example:
```Bash
python3 logo_cards.py --source both --bg "dual:2d1d2d:231a3a:0e0914:0.3:0.5:0.7:0.5"
```
---

## 🖼️ Tool 2: backdrop_T2.py
Lets use backdrop_T2.py for example, you can use any of the 4 provided scripts.
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
Example:
```Bash
python3 backdrop_T2.py --id 213 --type network          # This for Netflix

python3 backdrop_T2.py --id 49 8304 --type network      # two IDs for multiples, This will mix HBO with HBO max

python3 backdrop_T2.py --id 41077 --type company        # this one is for a A24, a company/production studio, the --type must be company

python3 backdrop_T2.py --id 28 --type genre             # the type here is genre, so the ID has to be genre specific 
```

You'll find more IDs in the tmdb_reference_ids.txt file


## MDBList Sorting Options

When pulling items from MDBList, you can customize the output sort order using the `--sort` parameter. 

### Usage
```bash
python3 backdrop_T2.py --url "[https://mdblist.com/lists/user/slug](https://mdblist.com/lists/user/slug)" --sort <option>
```
or you can also use the Shortened URL Format
```bash
python3 backdrops_T2.py --url "publicusername/top-rated-movies"

```
# Supported Sort Parameters
```
score.desc / score.asc  | MDBList overall combined score (Default)
imdbrating.desc / imdbrating.asc    | Sort by IMDb user ratings
imdbvotes.desc / imdbvotes.asc  | Sort by the total number of IMDb votes
tmdbpopular.desc / tmdbpopular.asc  | Sort by TMDb's internal popularity metric
released.desc / released.asc    | Sort by original theatrical release date
```

---

## 🛠️ Automated Generation (`generate.sh`)

To save you from typing multiple commands for every single ID, you can use the `generate.sh` automation script. It automatically pulls the logos, optimizes them, and generates both Type 1 and Type 2 backdrops in one go.

---

### 💻 How to Run It on Your System

#### 🪟 On Windows (Using Git Bash)
Windows Command Prompt cannot run `.sh` files natively. The easiest way to run it is using **Git Bash**, which was installed automatically when you installed Git.

1. Go to your project folder where `generate.sh` is located.
2. Right-click an empty space in the folder and select **Git Bash Here**.
3. Type the following command and press Enter:
   ```bash
   ./generate.sh network 213
   ```

#### 🍏 macOS & 🐧 Linux
1. Open your Terminal and navigate to the project folder (`cd /path/to/prism-wallpapers`).
2. Before running it the first time, give the script permission to run by typing:
   ```bash
   chmod +x generate.sh
   ```
3. Run the script:
   ```bash
   ./generate.sh network 213
   ```

---

### 📖 Usage Examples

The script is incredibly flexible and accepts arguments in different ways:

* **Standard Order (Type then IDs):**
  ```bash
  ./generate.sh network 213
  ```
* **Reversed Order (IDs then Type):**
  ```bash
  ./generate.sh 213 network
  ```
* **Multiple IDs at Once:**
  ```bash
  ./generate.sh network 213 49 1024
  ```

*Supported types are: `network`, `company`, `genre`, and `provider`.*


## Curated Collections (Direct TMDb Lists)

You can generate dynamic backdrops using TMDb's global lists by setting the `--type` to `curated`. This skips logos and fetches the top trending, popular, top-rated, or upcoming titles.

### Supported Curated Types

| Type Keyword | Description |
| :--- | :--- |
| `trending` | Daily trending movies and TV shows |
| `popular` | Current most popular titles on TMDb |
| `top_rated` | All-time top rated movies and TV shows |
| `upcoming` | Anticipated/Upcoming theatrical & digital releases |

### Usage Examples

```bash
# Generate daily trending backdrops
./generate.sh trending curated

# Generate upcoming movie/TV backdrops
./generate.sh upcoming curated
```

## Skipping Logo Downloads & Mixing IDs

To save time or prevent overwriting existing downloaded logos, you can use the `--skip-logos` flag. This will bypass the `logo_pull.py` script entirely and jump straight to generating backdrops.

### Usage Example
```bash
# Update existing backdrops without re-fetching any logos
./generate.sh 6100 network --skip-logos

# Mix IDs while skipping the logo download step
./generate.sh 6100-2076 network --skip-logos
```

Note: The --skip-logos flag is applied automatically when using --type curated, as these lists do not require individual brand logo downloads.
---

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
