import requests
import json
import datetime
import os
import re

# --- CONFIGURATION ---
FEED_URL = "https://motohunt.com/feed/inventory/g2387-426e2dea251a38c7bd9a6d5ea9741933.json"
SPECS_FILE = "specs_database.json"
OUTPUT_FILE = "index.html"

# YOUR SPECIFIC FIREBASE CONFIG (Do not edit)
FIREBASE_CONFIG_JS = """
{
  apiKey: "AIzaSyAfgVJvPdmYAkfjgCzQA0L3GiwcHqp412s",
  authDomain: "anderson-trainer.firebaseapp.com",
  databaseURL: "https://anderson-trainer-default-rtdb.firebaseio.com",
  projectId: "anderson-trainer",
  storageBucket: "anderson-trainer.firebasestorage.app",
  messagingSenderId: "637062348956",
  appId: "1:637062348956:web:0a660a80e31810bb392d59",
  measurementId: "G-THJZ99GDJ7"
}
"""

LOCATION_MAP = {
    "North Lake Havasu": "(1) North Lake Havasu",
    "Bullhead City": "(2) Bullhead City",
    "Bullhead": "(2) Bullhead City",
    "Parker": "(3) Parker",
    "AZ West": "(4) South Lake Havasu",
    "South Lake Havasu": "(4) South Lake Havasu",
    "Reno": "(5) Reno"
}

CATEGORY_MAP = {
    "Utility Vehicle": "UTV", "Side x Side": "UTV", "Side by Side": "UTV", "SxS": "UTV",
    "ATV": "ATV", "All Terrain Vehicle": "ATV", "Quad": "ATV",
    "Motorcycle": "Motorcycle", "Street Bike": "Motorcycle", "Dirt Bike": "Motorcycle",
    "Scooter": "Motorcycle", "Cruiser": "Motorcycle",
    "Personal Watercraft": "PWC", "PWC": "PWC", "Watercraft": "PWC", "Jet Ski": "PWC",
    "Boat": "Boat", "Pontoon": "Boat", "Marine": "Boat",
    "Snowmobile": "Snowmobile", "Sled": "Snowmobile"
}

def fetch_inventory_feed():
    print(f"🚀 Downloading Inventory Feed...")
    try:
        response = requests.get(FEED_URL, timeout=30)
        if response.status_code != 200:
            print(f"❌ Error fetching feed: {response.status_code}")
            return []
        data = response.json()
        if isinstance(data, dict):
            for key in data:
                if isinstance(data[key], list):
                    data = data[key]
                    break
        return data
    except Exception as e:
        print(f"❌ Critical Error: {e}")
        return []

def resolve_location(item):
    raw_loc = item.get('location') or item.get('dealer_name') or ""
    if not raw_loc:
        tags = item.get('tags')
        if tags:
            tag_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
            for city in LOCATION_MAP.keys():
                if city.lower() in tag_str.lower():
                    return LOCATION_MAP[city]
    
    for key, val in LOCATION_MAP.items():
        if key.lower() in raw_loc.lower():
            return val
            
    url = item.get('url') or item.get('vehicle_url') or ""
    for slug, store_name in LOCATION_MAP.items():
        if slug.lower().replace(" ", "-") in url.lower():
            return store_name

    return "Unassigned Location"

def resolve_category(item):
    stock = str(item.get('stocknumber') or item.get('stock') or item.get('id') or "").lower()
    if 't' in stock and len(stock) > 4: 
        return "Trailer"

    raw_cat = item.get('category') or item.get('vehicle_type') or item.get('type') or item.get('class') or ""
    if raw_cat:
        for key, val in CATEGORY_MAP.items():
            if key.lower() in raw_cat.lower():
                return val
    
    title = item.get('title', '').lower()
    if 'rzr' in title or 'ranger' in title or 'maverick' in title or 'defender' in title or 'general' in title or 'zforce' in title or 'uforce' in title:
        return "UTV"
    if 'sportsman' in title or 'outlander' in title or 'grizzly' in title or 'cforce' in title or 'pioneer' in title or 'talon' in title or 'mule' in title or 'teryx' in title or 'wolverine' in title or 'viking' in title:
        return "UTV" 
    if 'ninja' in title or 'gsx' in title or 'road glide' in title or 'chief' in title or 'scout' in title or 'ibex' in title or 'crf' in title or 'kx' in title or 'yz' in title or 'klr' in title or 'mt-' in title:
        return "Motorcycle"
    if 'sea-doo' in title or 'waverunner' in title or 'jet ski' in title or 'switch' in title or 'spark' in title or 'fishpro' in title:
        return "PWC"
    if 'bennington' in title or 'godfrey' in title or 'yamaha boat' in title:
        return "Boat"
    if 'rmk' in title or 'khaos' in title or 'timbersled' in title:
        return "Snowmobile"
    
    return "Other"

def process_inventory(raw_data):
    clean_inventory = []
    for item in raw_data:
        title = item.get('title') or f"{item.get('year', '')} {item.get('make', '')} {item.get('model', '')}"
        stock = str(item.get('stocknumber') or item.get('stock') or item.get('id') or "Unknown").strip().upper()
        location = resolve_location(item)
        category = resolve_category(item)
        link = item.get('url') or item.get('vehicle_url') or "#"
        
        cond_raw = str(item.get('condition') or "").lower()
        url_raw = str(link).lower()
        if "used" in cond_raw or "pre-owned" in cond_raw or "used" in url_raw or "pre-owned" in url_raw:
            condition = "Used"
        else:
            condition = "New"

        clean_inventory.append({
            "title": title.strip(),
            "stock": stock,
            "location": location,
            "category": category,
            "condition": condition,
            "link": link
        })
    
    clean_inventory.sort(key=lambda x: x['stock'])
    return clean_inventory

def load_specs():
    if not os.path.exists(SPECS_FILE):
        return []
    with open(SPECS_FILE, 'r') as f:
        return json.load(f)

def calculate_match_score(unit_title, model_keywords):
    title_tokens = set(re.findall(r'\w+', unit_title.lower()))
    best_keyword_score = 0
    for keyword_phrase in model_keywords:
        kw_tokens = set(re.findall(r'\w+', keyword_phrase.lower()))
        match_count = len(kw_tokens.intersection(title_tokens))
        if match_count == len(kw_tokens):
            score = match_count * 10 
            if score > best_keyword_score:
                best_keyword_score = score
    return best_keyword_score

def match_unit_to_specs(unit_title, specs_db):
    best_match = None
    highest_score = 0
    for model in specs_db:
        score = calculate_match_score(unit_title, model['model_keywords'])
        if score > highest_score and score > 0:
            highest_score = score
            best_match = model
    return best_match

def generate_html(inventory, specs_db):
    print("🛠️  Generating Trainer Dashboard...")
    enhanced_inv = []
    loc_counts = {}
    
    for unit in inventory:
        spec_data = match_unit_to_specs(unit['title'], specs_db)
        unit['specs'] = spec_data
        enhanced_inv.append(unit)
        loc = unit['location']
        loc_counts[loc] = loc_counts.get(loc, 0) + 1

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    stats_html = " | ".join([f"{k}: {v}" for k, v in loc_counts.items()])
    json_data = json.dumps(enhanced_inv)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Anderson Powersports Product Trainer</title>
        
        <script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js"></script>
        <script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-auth.js"></script>
        <script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-database.js"></script>

        <style>
            :root {{
                --bg-color: #121212;
                --card-bg: #1e1e1e;
                --text-main: #e0e0e0;
                --text-muted: #b0bec5;
                --accent-blue: #64b5f6;
                --accent-green: #00e676;
                --accent-orange: #ff9800;
                --header-bg: #1f1f1f;
                --border-color: #333;
                --input-bg: #2c2c2c;
                --highlight-bg: #263238;
            }}
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg-color); color: var(--text-main); padding: 0; margin: 0; }}
            
            /* LOGIN SCREEN */
            #login-overlay {{
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: #121212; z-index: 9999; display: flex;
                justify-content: center; align-items: center; flex-direction: column;
            }}
            .login-box {{
                background: var(--card-bg); padding: 40px; border-radius: 8px;
                border: 1px solid var(--border-color); text-align: center; width: 300px;
            }}
            .login-box input {{
                width: 100%; padding: 12px; margin-bottom: 15px; background: #2c2c2c;
                border: 1px solid #444; color: white; border-radius: 4px; box-sizing: border-box;
            }}
            .login-box button {{
                width: 100%; padding: 12px; background: var(--accent-blue); color: black;
                border: none; font-weight: bold; border-radius: 4px; cursor: pointer;
            }}
            .login-box button:hover {{ background: #90caf9; }}
            #login-error {{ color: #ff5252; margin-top: 10px; font-size: 0.9em; }}
            
            /* APP CONTENT (Hidden by default) */
            #app-content {{ padding: 20px; display: none; }}
            
            .header {{ background: var(--header-bg); color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color); position: relative; }}
            .stats {{ font-size: 0.85em; opacity: 0.8; margin-top: 5px; color: var(--text-muted); }}
            
            .logout-btn {{
                position: absolute; top: 20px; right: 20px;
                background: transparent; border: 1px solid #666; color: #aaa;
                padding: 5px 10px; cursor: pointer; border-radius: 4px; font-size: 0.8em;
            }}
            .logout-btn:hover {{ color: white; border-color: white; }}
            
            /* FILTER BAR */
            .filter-container {{ display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }}
            .filter-select {{ padding: 12px; font-size: 16px; background: var(--input-bg); color: white; border: 2px solid var(--border-color); border-radius: 8px; flex: 1; min-width: 200px; cursor: pointer; }}
            .search-box {{ width: 100%; padding: 15px; font-size: 18px; background: var(--input-bg); color: white; border: 2px solid var(--border-color); border-radius: 8px; margin-bottom: 20px; box-sizing: border-box; }}
            
            /* CARDS */
            .card {{ background: var(--card-bg); padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 15px; border-left: 5px solid #555; cursor: pointer; transition: transform 0.2s, border-left-color 0.2s; position: relative; }}
            .card:hover {{ transform: translateY(-3px); border-left-color: var(--accent-blue); }}
            .card.has-specs {{ border-left-color: var(--accent-green); }}
            .card.has-note {{ border-right: 5px solid var(--accent-orange); }} 
            
            .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; }}
            .location-tag {{ background: #1565c0; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.9em; font-weight: bold; margin-left: 10px; white-space: nowrap; }}
            .category-tag {{ background: #ff9800; color: black; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; margin-right: 5px; text-transform: uppercase; }}
            .condition-tag {{ background: #7b1fa2; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; margin-right: 5px; text-transform: uppercase; }}
            .stock-tag {{ background: #455a64; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.9em; display: inline-block; margin-top: 5px; }}
            
            .selling-points {{ background: var(--highlight-bg); padding: 15px; margin-top: 10px; border-radius: 6px; border: 1px solid var(--border-color); }}
            .selling-points h4 {{ margin-top: 0; color: #80cbc4; margin-bottom: 5px; }}
            .headline {{ font-weight: bold; color: white; display: block; margin-bottom: 8px; font-size: 1.1em; }}
            .specs-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-top: 10px; }}
            .spec-item {{ background: #2c2c2c; border: 1px solid #444; padding: 8px; text-align: center; border-radius: 4px; font-size: 0.85em; color: var(--text-main); }}
            
            /* NOTES SECTION */
            .note-container {{ margin-top: 20px; padding-top: 15px; border-top: 1px solid #444; }}
            .note-status {{ font-size: 0.8em; color: #888; margin-bottom: 5px; float: right; }}
            textarea.note-input {{ width: 100%; height: 80px; padding: 10px; background: #121212; color: white; border: 1px solid #444; border-radius: 4px; box-sizing: border-box; font-family: sans-serif; resize: vertical; }}
            textarea.note-input:focus {{ border-color: var(--accent-blue); outline: none; }}
            .note-badge {{ position: absolute; bottom: 10px; right: 10px; background: var(--accent-orange); color: black; border-radius: 50%; width: 24px; height: 24px; text-align: center; font-weight: bold; display: none; }}

            a {{ color: var(--accent-blue); text-decoration: none; font-weight: bold; font-size: 1.1em; }}
            a:hover {{ text-decoration: underline; color: #90caf9; }}

            /* MODAL SPLIT SCREEN */
            .modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.85); backdrop-filter: blur(5px); }}
            .modal-content {{ background-color: var(--bg-color); margin: 2vh auto; width: 96%; height: 94%; border: 1px solid var(--border-color); border-radius: 8px; display: flex; flex-direction: column; overflow: hidden; }}
            .modal-header {{ padding: 10px 20px; background: var(--header-bg); border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; }}
            .modal-header h2 {{ margin: 0; font-size: 1.2em; color: white; }}
            .close-btn {{ color: #aaa; font-size: 28px; font-weight: bold; cursor: pointer; }}
            .close-btn:hover {{ color: white; }}
            
            .split-container {{ display: flex; flex: 1; height: 100%; overflow: hidden; }}
            .pane-left {{ flex: 0 0 35%; padding: 20px; overflow-y: auto; background: var(--card-bg); border-right: 1px solid var(--border-color); min-width: 320px; }}
            .pane-right {{ flex: 1; background: white; position: relative; }}
            .iframe-loader {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%; -50%); color: black; }}
            iframe {{ width: 100%; height: 100%; border: none; }}
            
            /* Responsive Modal */
            @media (max-width: 768px) {{
                .split-container {{ flex-direction: column; }}
                .pane-left {{ flex: 0 0 40%; border-right: none; border-bottom: 1px solid var(--border-color); }}
                .pane-right {{ flex: 1; }}
            }}
        </style>
    </head>
    <body>
    
        <div id="login-overlay">
            <div class="login-box">
                <h2 style="margin-top:0;">Staff Login</h2>
                <input type="email" id="email" placeholder="Email">
                <input type="password" id="password" placeholder="Password">
                <button onclick="login()">Login</button>
                <p id="login-error"></p>
            </div>
        </div>

        <div id="app-content">
            <div class="header">
                <h1>Anderson Powersports | Inventory & Product Trainer</h1>
                <p>Updated: {timestamp} | Total Inventory: {len(enhanced_inv)} | <span id="matchCount" style="color: var(--accent-green); font-weight: bold;">Showing: {len(enhanced_inv)}</span></p>
                <div class="stats">{stats_html}</div>
                <button class="logout-btn" onclick="logout()">Logout</button>
            </div>

            <div class="filter-container">
                <select id="storeSelect" class="filter-select"><option value="All">All Locations</option></select>
                <select id="categorySelect" class="filter-select"><option value="All">All Categories</option></select>
                <select id="conditionSelect" class="filter-select"><option value="All">All Conditions</option></select>
            </div>

            <input type="text" id="searchInput" class="search-box" placeholder="Search (e.g. 'Pro R', '12345')...">
            <div id="resultsArea"></div>
        </div>

        <div id="unitModal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2 id="modalTitle">Unit Details</h2>
                    <span class="close-btn" onclick="closeModal()">&times;</span>
                </div>
                <div class="split-container">
                    <div class="pane-left" id="modalLeftPane"></div>
                    <div class="pane-right">
                        <div class="iframe-loader">Loading Dealer Site...</div>
                        <iframe id="modalFrame" src=""></iframe>
                    </div>
                </div>
            </div>
        </div>

        <script>
            const inventory = {json_data};
            const firebaseConfig = {FIREBASE_CONFIG_JS};
            
            // FIREBASE INIT
            if (firebaseConfig.apiKey && firebaseConfig.apiKey !== "PASTE_YOUR_API_KEY_HERE") {{
                firebase.initializeApp(firebaseConfig);
                var auth = firebase.auth();
                var db = firebase.database();
                console.log("Firebase Connected");
                
                // AUTH OBSERVER
                auth.onAuthStateChanged((user) => {{
                    const overlay = document.getElementById('login-overlay');
                    const app = document.getElementById('app-content');
                    
                    if (user) {{
                        // Logged In
                        overlay.style.display = 'none';
                        app.style.display = 'block';
                        // Trigger render to sync badges
                        render();
                    }} else {{
                        // Logged Out
                        overlay.style.display = 'flex';
                        app.style.display = 'none';
                    }}
                }});
                
            }} else {{
                console.warn("Firebase not configured correctly.");
            }}

            // LOGIN LOGIC
            function login() {{
                const email = document.getElementById('email').value;
                const pass = document.getElementById('password').value;
                const errorText = document.getElementById('login-error');
                
                errorText.textContent = "Logging in...";
                
                auth.signInWithEmailAndPassword(email, pass)
                    .catch((error) => {{
                        errorText.textContent = error.message;
                    }});
            }}

            function logout() {{
                auth.signOut();
            }}

            // APP LOGIC
            const resultsArea = document.getElementById('resultsArea');
            const searchInput = document.getElementById('searchInput');
            const storeSelect = document.getElementById('storeSelect');
            const categorySelect = document.getElementById('categorySelect');
            const conditionSelect = document.getElementById('conditionSelect');
            const modal = document.getElementById('unitModal');
            const modalTitle = document.getElementById('modalTitle');
            const modalLeftPane = document.getElementById('modalLeftPane');
            const modalFrame = document.getElementById('modalFrame');

            const locations = [...new Set(inventory.map(item => item.location))].sort();
            const categories = [...new Set(inventory.map(item => item.category))].sort();
            const conditions = [...new Set(inventory.map(item => item.condition))].sort();

            locations.forEach(loc => storeSelect.add(new Option(loc, loc)));
            categories.forEach(cat => categorySelect.add(new Option(cat, cat)));
            conditions.forEach(cond => conditionSelect.add(new Option(cond, cond)));

            function render() {{
                const term = searchInput.value.toLowerCase();
                const selectedStore = storeSelect.value;
                const selectedCategory = categorySelect.value;
                const selectedCondition = conditionSelect.value;

                const filtered = inventory.filter(item => {{
                    if (selectedStore !== 'All' && item.location !== selectedStore) return false;
                    if (selectedCategory !== 'All' && item.category !== selectedCategory) return false;
                    if (selectedCondition !== 'All' && item.condition !== selectedCondition) return false;
                    if (term === '') return true;
                    
                    return (
                        item.title.toLowerCase().includes(term) || 
                        item.stock.toLowerCase().includes(term) ||
                        (item.specs && item.specs.headline.toLowerCase().includes(term))
                    );
                }});
                
                const matchCountElement = document.getElementById('matchCount');
                if (matchCountElement) {{
                    matchCountElement.textContent = `Showing: ${{filtered.length}}`;
                }}

                if (filtered.length === 0) {{ resultsArea.innerHTML = '<p style="text-align:center; color:#888;">No matches found.</p>'; return; }}

                resultsArea.innerHTML = filtered.slice(0, 100).map((item, index) => {{
                    let badgeColor = item.specs ? 'var(--accent-green)' : '#555';
                    let condColor = item.condition === 'New' ? '#00e676' : '#ffb74d'; 
                    let condStyle = `background: ${{condColor}}; color: black; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; margin-right: 5px; text-transform: uppercase;`;
                    
                    return `
                        <div class="card" id="card-${{item.stock}}" style="border-left-color: ${{badgeColor}}" onclick="openModal('${{item.stock}}')">
                            <div class="card-header">
                                <div>
                                    <span style="${{condStyle}}">${{item.condition}}</span>
                                    <span class="category-tag">${{item.category}}</span>
                                    <strong>${{item.title}}</strong>
                                    <br>
                                    <span class="stock-tag">#${{item.stock}}</span>
                                </div>
                                <span class="location-tag">${{item.location}}</span>
                            </div>
                            ${{item.specs ? `<div style="margin-top:10px; font-size:0.9em; color:#bbb;">💡 ${{(item.specs.headline)}}</div>` : ''}}
                            <div id="badge-${{item.stock}}" class="note-badge">📝</div>
                        </div>
                    `;
                }}).join('');
                
                // SYNC BADGES (If DB is ready)
                if (typeof db !== 'undefined' && auth.currentUser) {{
                    filtered.slice(0, 100).forEach(item => {{
                        db.ref('notes/' + item.stock).once('value').then(snapshot => {{
                            if (snapshot.exists() && snapshot.val().trim() !== "") {{
                                const badge = document.getElementById('badge-' + item.stock);
                                if (badge) badge.style.display = 'block';
                            }}
                        }});
                    }});
                }}
            }}

            window.openModal = function(stock) {{
                const item = inventory.find(i => i.stock === stock);
                if (!item) return;

                modalTitle.textContent = item.title;
                modalFrame.src = item.link;

                let content = `
                    <div style="margin-bottom:20px;">
                        <span class="category-tag">${{item.category}}</span>
                        <span class="stock-tag">#${{item.stock}}</span>
                        <div style="margin-top:10px; color: var(--accent-blue); font-weight:bold;">${{item.location}}</div>
                    </div>
                `;
                
                // NOTES SECTION
                content += `
                    <div class="note-container">
                        <span id="noteStatus" class="note-status">Loading notes...</span>
                        <h4 style="margin:0 0 10px 0;">📝 Sales Notes</h4>
                        <textarea id="noteInput" class="note-input" placeholder="Add sales notes here (e.g., Winch added, customer interested)..."></textarea>
                    </div>
                `;

                if (item.specs) {{
                    const points = item.specs.selling_points.map(p => `<li>${{p}}</li>`).join('');
                    const specs = Object.entries(item.specs.specs).map(([k, v]) => 
                        `<div class="spec-item"><strong>${{k}}</strong><br>${{v}}</div>`
                    ).join('');
                    
                    content += `
                        <div class="selling-points" style="margin-top:20px;">
                            <h4 style="font-size:1.2em; border-bottom:1px solid #444; padding-bottom:5px;">💡 Sales Knowledge</h4>
                            <span class="headline" style="font-size:1.3em; margin:15px 0;">${{item.specs.headline}}</span>
                            <ul style="line-height:1.6;">${{points}}</ul>
                            <h4 style="margin-top:20px;">⚙️ Key Specs</h4>
                            <div class="specs-grid">${{specs}}</div>
                        </div>
                    `;
                }} else {{
                    content += `<div style="padding:20px; text-align:center; color:#777; border:1px dashed #444; border-radius:8px; margin-top:20px;">
                        <h3>No Training Card Available</h3>
                    </div>`;
                }}
                
                content += `<div style="margin-top:30px; padding-top:20px; border-top:1px solid #333;">
                    <a href="${{item.link}}" target="_blank" style="display:block; padding:12px; background:var(--accent-blue); color:black; text-align:center; border-radius:6px; text-decoration:none;">Open Website in New Tab ↗</a>
                </div>`;

                modalLeftPane.innerHTML = content;
                modal.style.display = "block";
                document.body.style.overflow = "hidden"; 
                
                if (typeof db !== 'undefined') {{
                    const noteInput = document.getElementById('noteInput');
                    const noteStatus = document.getElementById('noteStatus');
                    const noteRef = db.ref('notes/' + stock);
                    
                    // Listen
                    noteRef.on('value', (snapshot) => {{
                        const val = snapshot.val() || "";
                        if (document.activeElement !== noteInput) {{ 
                            noteInput.value = val;
                        }}
                        noteStatus.textContent = "Synced";
                    }});
                    
                    // Save
                    noteInput.addEventListener('input', (e) => {{
                        noteStatus.textContent = "Saving...";
                        noteRef.set(e.target.value).then(() => {{
                            noteStatus.textContent = "Saved";
                        }});
                    }});
                }}
            }};

            window.closeModal = function() {{
                modal.style.display = "none";
                modalFrame.src = ""; 
                document.body.style.overflow = "auto";
            }};

            searchInput.addEventListener('keyup', render);
            storeSelect.addEventListener('change', render);
            categorySelect.addEventListener('change', render);
            conditionSelect.addEventListener('change', render);

            // Initial render call moved to auth state listener
        </script>
    </body>
    </html>
    """
    
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write(html_content)
    print(f"✅ Dashboard generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    raw_data = fetch_inventory_feed()
    
    if raw_data:
        current_inventory = process_inventory(raw_data)
        spec_database = load_specs()
        
        match_count = 0
        for item in current_inventory:
            match = match_unit_to_specs(item['title'], spec_database)
            if match:
                match_count += 1
        
        print(f"Total Inventory: {len(current_inventory)}")
        print(f"Total Matched: {match_count}")
        
        generate_html(current_inventory, spec_database) 
    else:
        print("⚠️ Failed to load inventory.")
