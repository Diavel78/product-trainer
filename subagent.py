import requests
import json
import datetime
import os
import re

# --- CONFIGURATION ---
FEED_URL = "https://motohunt.com/feed/inventory/g2387-426e2dea251a38c7bd9a6d5ea9741933.json"
SPECS_FILE = "specs_database.json"
OUTPUT_FILE = "index.html"

# Mapping Feed Location Names & URL Slugs to Your Store Numbers
LOCATION_MAP = {
    "North Lake Havasu": "(1) North Lake Havasu",
    "Bullhead City": "(2) Bullhead City",
    "Bullhead": "(2) Bullhead City",
    "Parker": "(3) Parker",
    "AZ West": "(4) South Lake Havasu",
    "South Lake Havasu": "(4) South Lake Havasu",
    "Reno": "(5) Reno"
}

def fetch_inventory_feed():
    try:
        response = requests.get(FEED_URL, timeout=30)
        if response.status_code != 200: return []
        data = response.json()
        if isinstance(data, dict):
            for key in data:
                if isinstance(data[key], list): return data[key]
        return data if isinstance(data, list) else []
    except: return []

def resolve_location(item):
    # 1. Direct Keys (Feed provided location)
    raw_loc = item.get('location') or item.get('dealer_name') or ""
    
    # 2. URL Check (The most accurate method for Anderson)
    url = (item.get('url') or item.get('vehicle_url') or "").lower()
    
    # Combine raw location and URL for a broad search
    check_str = (raw_loc + " " + url).lower()
    
    # --- DOMAIN & KEYWORD MAPPING RULES ---
    
    # (1) North Lake Havasu
    if "andersonpowersportshavasu.com" in check_str: return "(1) North Lake Havasu"
    if "north lake" in check_str: return "(1) North Lake Havasu"
    if "havasu city, az 86403" in check_str: return "(1) North Lake Havasu"
    
    # (2) Bullhead City
    if "andersonpowersportsbullhead.com" in check_str: return "(2) Bullhead City"
    if "bullhead" in check_str: return "(2) Bullhead City"
    
    # (3) Parker
    if "andersonpowersportsparker" in check_str: return "(3) Parker"
    if "parker" in check_str: return "(3) Parker"
    
    # (4) South Lake Havasu (AZ West)
    if "az west" in check_str: return "(4) South Lake Havasu"
    if "south lake" in check_str: return "(4) South Lake Havasu"
    if "havasu city, az 86406" in check_str: return "(4) South Lake Havasu"
    
    # (5) Reno
    if "andersonpowersportsreno.com" in check_str: return "(5) Reno"
    if "reno" in check_str: return "(5) Reno"
    
    return "Unassigned"

def process_inventory(raw_data):
    clean_inventory = []
    for item in raw_data:
        title = item.get('title') or f"{item.get('year', '')} {item.get('make', '')} {item.get('model', '')}"
        stock = str(item.get('stocknumber') or item.get('stock') or item.get('id') or "Unknown")
        location = resolve_location(item)
        link = item.get('url') or item.get('vehicle_url') or "#"
        
        # Categorization Logic for Filters
        v_type = item.get('type') or item.get('category') or "Other"
        make = item.get('make') or "Other"
        condition = item.get('condition') or "New"

        clean_inventory.append({
            "title": title.strip(),
            "stock": stock,
            "location": location,
            "link": link,
            "type": v_type,
            "make": make,
            "condition": condition
        })
    return clean_inventory

def load_specs():
    if not os.path.exists(SPECS_FILE): return []
    with open(SPECS_FILE, 'r') as f: return json.load(f)

def match_unit_to_specs(unit_title, specs_db):
    sorted_specs = sorted(specs_db, key=lambda x: len(x['model_keywords'][0]), reverse=True)
    for model in sorted_specs:
        for keyword in model['model_keywords']:
            if keyword.lower() in unit_title.lower(): return model
    return None

def generate_html(inventory, specs_db):
    enhanced_inv = []
    for unit in inventory:
        unit['specs'] = match_unit_to_specs(unit['title'], specs_db)
        enhanced_inv.append(unit)

    timestamp = datetime.datetime.now().strftime("%m/%d %I:%M %p")
    inv_json = json.dumps(enhanced_inv)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Anderson Product Trainer</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            :root {{ --bg: #121212; --card: #1e1e1e; --text: #e0e0e0; --accent: #e74c3c; --accent-hover: #c0392b; --green: #2ecc71; }}
            body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; height: 100vh; overflow: hidden; }}
            
            /* Sidebar */
            .sidebar {{ width: 280px; background: #181818; padding: 20px; display: flex; flex-direction: column; border-right: 1px solid #333; }}
            .sidebar h2 {{ color: var(--accent); margin: 0 0 20px 0; font-size: 1.5rem; text-transform: uppercase; letter-spacing: 1px; }}
            .filter-group {{ margin-bottom: 20px; }}
            .filter-label {{ display: block; font-size: 0.8rem; text-transform: uppercase; color: #888; margin-bottom: 8px; font-weight: bold; }}
            select, input {{ width: 100%; background: #2a2a2a; border: 1px solid #444; color: white; padding: 10px; border-radius: 6px; margin-bottom: 10px; font-size: 0.9rem; }}
            select:focus, input:focus {{ outline: none; border-color: var(--accent); }}
            
            /* Main Content */
            .main {{ flex: 1; padding: 20px; overflow-y: auto; position: relative; }}
            .header-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #333; }}
            .status {{ font-size: 0.9rem; color: #888; }}
            
            /* Grid */
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }}
            
            /* Cards */
            .card {{ background: var(--card); border-radius: 8px; overflow: hidden; transition: transform 0.2s; border: 1px solid #333; display: flex; flex-direction: column; }}
            .card:hover {{ transform: translateY(-3px); border-color: #555; }}
            .card-header {{ padding: 15px; border-bottom: 1px solid #333; background: #252525; }}
            .card-title {{ font-size: 1.1rem; font-weight: bold; color: white; text-decoration: none; display: block; margin-bottom: 5px; }}
            .card-title:hover {{ color: var(--accent); }}
            .badges {{ display: flex; gap: 5px; flex-wrap: wrap; }}
            .badge {{ font-size: 0.75rem; padding: 3px 8px; border-radius: 4px; font-weight: 600; }}
            .badge-stock {{ background: #333; color: #ccc; }}
            .badge-loc {{ background: var(--accent); color: white; }}
            
            /* Training Section */
            .training {{ padding: 15px; flex: 1; background: #222; }}
            .training h4 {{ margin: 0 0 10px 0; font-size: 0.85rem; color: var(--green); text-transform: uppercase; }}
            .headline {{ font-weight: bold; display: block; margin-bottom: 8px; font-size: 0.95rem; }}
            .points {{ margin: 0; padding-left: 20px; color: #bbb; font-size: 0.9rem; line-height: 1.4; }}
            .specs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 15px; padding-top: 10px; border-top: 1px solid #333; }}
            .spec {{ font-size: 0.8rem; color: #888; }}
            .spec span {{ color: #ddd; font-weight: bold; }}
            
            .no-data {{ color: #666; font-style: italic; font-size: 0.9rem; padding: 15px; text-align: center; }}

            /* Mobile */
            @media (max-width: 768px) {{
                body {{ flex-direction: column; }}
                .sidebar {{ width: auto; padding: 15px; max-height: 150px; overflow-y: auto; }}
                .grid {{ grid-template-columns: 1fr; }}
            }}
        </style>
    </head>
    <body>

        <div class="sidebar">
            <h2>Anderson <span style="font-size:0.6em; color:#888;">Trainer</span></h2>
            
            <div class="filter-group">
                <label class="filter-label">Search</label>
                <input type="text" id="search" placeholder="Model, Stock #...">
            </div>

            <div class="filter-group">
                <label class="filter-label">Location</label>
                <select id="locFilter">
                    <option value="">All Locations</option>
                    <option value="(1)">North Lake Havasu</option>
                    <option value="(2)">Bullhead City</option>
                    <option value="(3)">Parker</option>
                    <option value="(4)">South Lake Havasu</option>
                    <option value="(5)">Reno</option>
                </select>
            </div>

            <div class="filter-group">
                <label class="filter-label">Type</label>
                <select id="typeFilter">
                    <option value="">All Types</option>
                </select>
            </div>
            
            <div class="filter-group">
                <label class="filter-label">Make</label>
                <select id="makeFilter">
                    <option value="">All Makes</option>
                </select>
            </div>
        </div>

        <div class="main">
            <div class="header-bar">
                <div class="status">Updated: {timestamp}</div>
                <div class="status" id="count">Loading...</div>
            </div>
            <div id="grid" class="grid"></div>
        </div>

        <script>
            const data = {inv_json};
            const grid = document.getElementById('grid');
            const countLabel = document.getElementById('count');
            
            // Populate Filters
            const types = [...new Set(data.map(i => i.type))].sort();
            const makes = [...new Set(data.map(i => i.make))].sort();
            
            types.forEach(t => document.getElementById('typeFilter').innerHTML += `<option value="${{t}}">${{t}}</option>`);
            makes.forEach(m => document.getElementById('makeFilter').innerHTML += `<option value="${{m}}">${{m}}</option>`);

            function render(items) {{
                countLabel.innerText = `${{items.length}} Units Found`;
                
                if (items.length === 0) {{
                    grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:#555;">No units match your filters.</div>';
                    return;
                }}

                grid.innerHTML = items.map(item => {{
                    let content = '';
                    if (item.specs) {{
                        const pts = item.specs.selling_points.slice(0,3).map(p => `<li>${{p}}</li>`).join('');
                        const specKeys = Object.entries(item.specs.specs).slice(0,4);
                        const specHtml = specKeys.map(([k,v]) => `<div class="spec">${{k}}: <span>${{v}}</span></div>`).join('');
                        
                        content = `
                            <div class="training">
                                <h4><i class="fas fa-bolt"></i> ${{item.specs.headline}}</h4>
                                <ul class="points">${{pts}}</ul>
                                <div class="specs">${{specHtml}}</div>
                            </div>
                        `;
                    }} else {{
                        content = `<div class="no-data">No training card available.<br>Type: ${{item.type}}</div>`;
                    }}

                    return `
                        <div class="card">
                            <div class="card-header">
                                <a href="${{item.link}}" target="_blank" class="card-title">${{item.title}}</a>
                                <div class="badges">
                                    <span class="badge badge-stock">#${{item.stock}}</span>
                                    <span class="badge badge-loc">${{item.location.replace(/\(.\) /, '')}}</span>
                                </div>
                            </div>
                            ${{content}}
                        </div>
                    `;
                }}).join('').slice(0, 500000); 
            }}

            function filter() {{
                const s = document.getElementById('search').value.toLowerCase();
                const l = document.getElementById('locFilter').value;
                const t = document.getElementById('typeFilter').value;
                const m = document.getElementById('makeFilter').value;

                const filtered = data.filter(i => {{
                    const matchSearch = i.title.toLowerCase().includes(s) || i.stock.toLowerCase().includes(s);
                    const matchLoc = l === "" || i.location.includes(l);
                    const matchType = t === "" || i.type === t;
                    const matchMake = m === "" || i.make === m;
                    return matchSearch && matchLoc && matchType && matchMake;
                }});
                
                render(filtered.slice(0, 50));
            }}

            document.getElementById('search').addEventListener('keyup', filter);
            document.getElementById('locFilter').addEventListener('change', filter);
            document.getElementById('typeFilter').addEventListener('change', filter);
            document.getElementById('makeFilter').addEventListener('change', filter);

            render(data.slice(0, 50));
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
        generate_html(current_inventory, spec_database)
    else:
        print("⚠️ Failed to load inventory.")
