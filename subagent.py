import requests
import json
import datetime
import os
import config  # Importing the config file
from spec_manager import SpecManager # Importing our new "AI Bot"

# --- CONFIGURATION ---
FEED_URL = "https://motohunt.com/feed/inventory/g2387-426e2dea251a38c7bd9a6d5ea9741933.json"
OUTPUT_FILE = "index.html"

def fetch_inventory_feed():
    print(f"🚀 Downloading Inventory Feed...")
    try:
        response = requests.get(FEED_URL, timeout=30)
        if response.status_code != 200:
            print(f"❌ Error fetching feed: {response.status_code}")
            return []
        data = response.json()
        # Flatten structure if nested under a key
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
    """
    Uses config.py logic to resolve locations accurately.
    """
    raw_loc = item.get('location') or item.get('dealer_name') or ""
    
    # Check against Config
    for store_key, store_data in config.STORES.items():
        # Match by name in feed vs config name
        if store_key.lower() in raw_loc.lower():
            return store_data['name']
    
    # Fallback to simple mapping if config match fails
    if "Havasu" in raw_loc: return config.STORES["N. Lake Havasu"]['name']
    if "Parker" in raw_loc: return config.STORES["Parker"]['name']
    if "Bullhead" in raw_loc: return config.STORES["Bullhead City"]['name']
    if "Reno" in raw_loc: return config.STORES["Reno"]['name']

    return "Anderson Powersports" # Default

def process_inventory(raw_data):
    clean_inventory = []
    for item in raw_data:
        # Construct title
        title = item.get('title') or f"{item.get('year', '')} {item.get('make', '')} {item.get('model', '')}"
        
        # Safe extraction
        stock = str(item.get('stocknumber') or item.get('stock') or item.get('id') or "Unknown")
        location = resolve_location(item)
        
        # Link logic
        link = item.get('url') or item.get('vehicle_url') or "#"
        
        # Categorization logic (simple)
        category = "Other"
        title_lower = title.lower()
        if "rzr" in title_lower or "maverick" in title_lower or "ranger" in title_lower or "defender" in title_lower:
            category = "UTV"
        elif "sportsman" in title_lower or "outlander" in title_lower or "atv" in title_lower:
            category = "ATV"
        elif "sea-doo" in title_lower or "waverunner" in title_lower or "jet" in title_lower:
            category = "PWC"
        elif "indian" in title_lower or "kawasaki ninja" in title_lower:
            category = "Motorcycle"

        clean_inventory.append({
            "title": title.strip(),
            "stock": stock,
            "location": location,
            "link": link,
            "category": category,
            "make": item.get('make', 'Unknown'),
            "year": item.get('year', '2025')
        })
    return clean_inventory

def generate_dashboard(inventory, spec_manager):
    print("🛠️  Generating Split-Screen Dashboard...")
    
    # Enrich inventory with specs
    enhanced_inv = []
    for unit in inventory:
        # 1. Try local DB match
        spec_data = spec_manager.find_specs(unit['title'])
        
        # 2. If no match, we could trigger the AI bot here
        # Note: We skip live fetching for ALL units to avoid 1000s of requests.
        # Ideally, this runs as a separate background job.
        
        unit['specs'] = spec_data
        enhanced_inv.append(unit)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Create Filter Options
    locations = sorted(list(set(i['location'] for i in enhanced_inv)))
    makes = sorted(list(set(i['make'] for i in enhanced_inv)))
    categories = sorted(list(set(i['category'] for i in enhanced_inv)))

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Anderson Product Trainer 2.0</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body {{ height: 100vh; overflow: hidden; display: flex; flex-direction: column; }}
            .main-container {{ display: flex; flex: 1; height: 100%; overflow: hidden; }}
            
            /* Sidebar (List) */
            .sidebar {{ width: 350px; background: #f8fafc; border-right: 1px solid #e2e8f0; display: flex; flex-direction: column; }}
            .search-area {{ padding: 15px; background: white; border-bottom: 1px solid #e2e8f0; }}
            .unit-list {{ flex: 1; overflow-y: auto; }}
            .unit-item {{ padding: 15px; border-bottom: 1px solid #eee; cursor: pointer; transition: background 0.2s; }}
            .unit-item:hover {{ background: #e0f2fe; }}
            .unit-item.active {{ background: #0ea5e9; color: white; }}
            .unit-item.active .text-gray-500 {{ color: #e0f2fe; }}
            
            /* Content Area (Split Screen) */
            .content-area {{ flex: 1; display: flex; background: #f1f5f9; }}
            
            /* Left Panel: Training Card */
            .training-card {{ width: 40%; padding: 20px; overflow-y: auto; background: white; border-right: 1px solid #ccc; }}
            
            /* Right Panel: Live Website */
            .browser-view {{ flex: 1; background: #fff; }}
            iframe {{ width: 100%; height: 100%; border: none; }}
            
            /* Specs Grid */
            .specs-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }}
            .spec-box {{ background: #f8fafc; padding: 10px; border-radius: 6px; border: 1px solid #e2e8f0; }}
            .spec-label {{ font-size: 0.75rem; color: #64748b; font-weight: bold; text-transform: uppercase; }}
            .spec-value {{ font-size: 0.9rem; font-weight: 600; color: #334155; }}
            
            .empty-state {{ display: flex; align-items: center; justify-content: center; height: 100%; color: #94a3b8; font-size: 1.5rem; }}
        </style>
    </head>
    <body class="font-sans text-slate-800">
        <header class="bg-slate-800 text-white p-4 flex justify-between items-center shadow-lg z-10">
            <div>
                <h1 class="text-xl font-bold">Anderson Powersports | Sales Trainer</h1>
                <p class="text-xs text-slate-400">Updated: {timestamp} | {len(enhanced_inv)} Units</p>
            </div>
            <div class="flex gap-2">
                <select id="locFilter" class="bg-slate-700 border border-slate-600 text-white text-sm rounded px-2 py-1">
                    <option value="">All Locations</option>
                    {"".join(f'<option value="{x}">{x}</option>' for x in locations)}
                </select>
                <select id="makeFilter" class="bg-slate-700 border border-slate-600 text-white text-sm rounded px-2 py-1">
                    <option value="">All Makes</option>
                    {"".join(f'<option value="{x}">{x}</option>' for x in makes)}
                </select>
            </div>
        </header>

        <div class="main-container">
            <div class="sidebar">
                <div class="search-area">
                    <input type="text" id="searchInput" placeholder="Search units..." class="w-full p-2 border border-slate-300 rounded focus:outline-none focus:border-blue-500">
                </div>
                <div id="unitList" class="unit-list">
                    </div>
            </div>

            <div class="content-area">
                
                <div id="trainingPanel" class="training-card hidden">
                    <div class="mb-6">
                        <span id="unitStock" class="bg-blue-100 text-blue-800 text-xs font-semibold px-2.5 py-0.5 rounded">STOCK#</span>
                        <h2 id="unitTitle" class="text-2xl font-bold text-slate-800 mt-2">Select a Unit</h2>
                        <p id="unitLoc" class="text-sm text-slate-500">Location</p>
                    </div>

                    <div id="specContainer" class="hidden">
                        <div class="bg-emerald-50 border-l-4 border-emerald-500 p-4 mb-6">
                            <h3 class="text-emerald-800 font-bold mb-1" id="specHeadline">Headline</h3>
                            <ul id="sellingPoints" class="list-disc list-inside text-sm text-emerald-700 space-y-1"></ul>
                        </div>

                        <h4 class="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3 border-b pb-1">Technical Specifications</h4>
                        <div id="specsGrid" class="specs-grid"></div>
                    </div>

                    <div id="noSpecMessage" class="hidden bg-slate-50 p-6 rounded-lg text-center border border-dashed border-slate-300 mt-4">
                        <p class="text-slate-500 mb-2">Training card not yet generated for this model.</p>
                        <button class="bg-white border border-slate-300 text-slate-600 px-3 py-1 rounded text-sm hover:bg-slate-100">
                            Request AI Spec Fetch (Future Feature)
                        </button>
                    </div>
                    
                    <div class="mt-8 pt-4 border-t">
                        <a id="extLink" href="#" target="_blank" class="block w-full text-center bg-slate-800 text-white py-3 rounded-lg hover:bg-slate-700 font-semibold">
                            Open Website in New Tab
                        </a>
                        <p class="text-xs text-center text-slate-400 mt-2">Use this if the right panel is blocked.</p>
                    </div>
                </div>

                <div id="browserPanel" class="browser-view relative">
                    <div id="iframePlaceholder" class="empty-state">
                        Select a unit to begin training
                    </div>
                    <iframe id="webFrame" src="" class="hidden" sandbox="allow-scripts allow-same-origin allow-forms"></iframe>
                </div>
            </div>
        </div>

        <script>
            const inventory = {json.dumps(enhanced_inv)};
            
            // DOM Elements
            const unitList = document.getElementById('unitList');
            const searchInput = document.getElementById('searchInput');
            const locFilter = document.getElementById('locFilter');
            const makeFilter = document.getElementById('makeFilter');
            
            const trainingPanel = document.getElementById('trainingPanel');
            const iframePlaceholder = document.getElementById('iframePlaceholder');
            const webFrame = document.getElementById('webFrame');
            
            // Render List
            function renderList(items) {{
                unitList.innerHTML = items.map((item, index) => `
                    <div class="unit-item" onclick="selectUnit(${index})">
                        <div class="font-bold text-sm truncate">${{item.title}}</div>
                        <div class="flex justify-between mt-1">
                            <span class="text-xs text-gray-500">#${{item.stock}}</span>
                            <span class="text-xs bg-slate-200 px-1 rounded text-slate-600">${{item.make}}</span>
                        </div>
                    </div>
                `).join('');
            }}

            // Select Unit Logic
            window.selectUnit = function(index) {{
                const item = inventory[index];
                
                // 1. Highlight List Item (Simple toggle for now)
                
                // 2. Populate Training Card
                trainingPanel.classList.remove('hidden');
                document.getElementById('unitTitle').innerText = item.title;
                document.getElementById('unitStock').innerText = item.stock;
                document.getElementById('unitLoc').innerText = item.location;
                document.getElementById('extLink').href = item.link;

                // Specs Logic
                if (item.specs) {{
                    document.getElementById('specContainer').classList.remove('hidden');
                    document.getElementById('noSpecMessage').classList.add('hidden');
                    
                    document.getElementById('specHeadline').innerText = item.specs.headline;
                    document.getElementById('sellingPoints').innerHTML = item.specs.selling_points.map(p => `<li>${{p}}</li>`).join('');
                    
                    const specsHtml = Object.entries(item.specs.specs).map(([k, v]) => `
                        <div class="spec-box">
                            <div class="spec-label">${{k}}</div>
                            <div class="spec-value">${{v}}</div>
                        </div>
                    `).join('');
                    document.getElementById('specsGrid').innerHTML = specsHtml;
                }} else {{
                    document.getElementById('specContainer').classList.add('hidden');
                    document.getElementById('noSpecMessage').classList.remove('hidden');
                }}

                // 3. Load Iframe
                iframePlaceholder.classList.add('hidden');
                webFrame.classList.remove('hidden');
                webFrame.src = item.link;
            }};

            // Filter Logic
            function filterInventory() {{
                const term = searchInput.value.toLowerCase();
                const loc = locFilter.value;
                const make = makeFilter.value;

                const filtered = inventory.filter(item => {{
                    const matchesTerm = item.title.toLowerCase().includes(term) || item.stock.toLowerCase().includes(term);
                    const matchesLoc = loc === "" || item.location === loc;
                    const matchesMake = make === "" || item.make === make;
                    return matchesTerm && matchesLoc && matchesMake;
                }});
                
                renderList(filtered);
            }}

            // Listeners
            searchInput.addEventListener('keyup', filterInventory);
            locFilter.addEventListener('change', filterInventory);
            makeFilter.addEventListener('change', filterInventory);

            // Init
            renderList(inventory);
        </script>
    </body>
    </html>
    """
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ Dashboard generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    # 1. Initialize Spec Manager (The Brain)
    sm = SpecManager()
    
    # 2. Get Data
    raw_data = fetch_inventory_feed()
    
    if raw_data:
        # 3. Process & Match
        current_inventory = process_inventory(raw_data)
        generate_dashboard(current_inventory, sm)
    else:
        print("⚠️ Failed to load inventory.")
