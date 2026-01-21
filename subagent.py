import requests
import json
import datetime
import os
import re

# --- CONFIGURATION ---
FEED_URL = "https://motohunt.com/feed/inventory/g2387-426e2dea251a38c7bd9a6d5ea9741933.json"
SPECS_FILE = "specs_database.json"
OUTPUT_FILE = "index.html"  # Changed for Web Hosting

# Mapping Feed Location Names to Your Store Numbers
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
    # 1. Try direct keys
    raw_loc = item.get('location') or item.get('dealer_name') or ""
    
    # 2. If empty, check Tags
    if not raw_loc:
        tags = item.get('tags')
        if tags:
            if isinstance(tags, list):
                tag_str = ", ".join(tags)
            else:
                tag_str = str(tags)
            for city in LOCATION_MAP.keys():
                if city.lower() in tag_str.lower():
                    return LOCATION_MAP[city]
    
    # 3. Match against the map
    for key, val in LOCATION_MAP.items():
        if key.lower() in raw_loc.lower():
            return val
            
    # 4. Check URL
    url = item.get('url') or item.get('vehicle_url') or ""
    for slug, store_name in LOCATION_MAP.items():
        if slug.lower().replace(" ", "-") in url.lower():
            return store_name

    return "Unassigned Location"

def process_inventory(raw_data):
    clean_inventory = []
    for item in raw_data:
        title = item.get('title') or f"{item.get('year', '')} {item.get('make', '')} {item.get('model', '')}"
        stock = str(item.get('stocknumber') or item.get('stock') or item.get('id') or "Unknown")
        location = resolve_location(item)
        link = item.get('url') or item.get('vehicle_url') or "#"

        clean_inventory.append({
            "title": title.strip(),
            "stock": stock,
            "location": location,
            "link": link
        })
    return clean_inventory

def load_specs():
    if not os.path.exists(SPECS_FILE):
        return []
    with open(SPECS_FILE, 'r') as f:
        return json.load(f)

def match_unit_to_specs(unit_title, specs_db):
    sorted_specs = sorted(specs_db, key=lambda x: len(x['model_keywords'][0]), reverse=True)
    for model in sorted_specs:
        for keyword in model['model_keywords']:
            if keyword.lower() in unit_title.lower():
                return model
    return None

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

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Anderson Powersports Product Trainer</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f4f9; padding: 20px; }}
            .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
            .stats {{ font-size: 0.85em; opacity: 0.9; margin-top: 5px; }}
            .search-box {{ width: 100%; padding: 15px; font-size: 18px; border: 2px solid #ddd; border-radius: 8px; margin-bottom: 20px; box-sizing: border-box; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 15px; border-left: 5px solid #ccc; }}
            .card.has-specs {{ border-left-color: #27ae60; }}
            .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; }}
            .location-tag {{ background: #3498db; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.9em; font-weight: bold; margin-left: 10px; }}
            .stock-tag {{ background: #7f8c8d; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.9em; }}
            .selling-points {{ background: #e8f8f5; padding: 15px; margin-top: 10px; border-radius: 6px; }}
            .selling-points h4 {{ margin-top: 0; color: #16a085; margin-bottom: 5px; }}
            .headline {{ font-weight: bold; color: #2c3e50; display: block; margin-bottom: 8px; }}
            .specs-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-top: 10px; }}
            .spec-item {{ background: #fff; border: 1px solid #eee; padding: 8px; text-align: center; border-radius: 4px; font-size: 0.85em; }}
            a {{ color: #2c3e50; text-decoration: none; font-weight: bold; font-size: 1.1em; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Anderson Powersports | Inventory & Product Trainer</h1>
            <p>Updated: {timestamp} | Total Units: {len(enhanced_inv)}</p>
            <div class="stats">{stats_html}</div>
        </div>
        <input type="text" id="searchInput" class="search-box" placeholder="Search (e.g. 'Pro R', 'Parker', '240 HP', '12345')...">
        <div id="resultsArea"></div>
        <script>
            const inventory = {json.dumps(enhanced_inv)};
            const resultsArea = document.getElementById('resultsArea');
            const searchInput = document.getElementById('searchInput');

            function render(items) {{
                if (items.length === 0) {{ resultsArea.innerHTML = '<p style="text-align:center; color:#777;">No matches found.</p>'; return; }}
                const displayItems = items.slice(0, 100);
                resultsArea.innerHTML = displayItems.map(item => {{
                    let trainingHtml = '';
                    if (item.specs) {{
                        const points = item.specs.selling_points.map(p => `<li>${{p}}</li>`).join('');
                        const specs = Object.entries(item.specs.specs).map(([k, v]) => 
                            `<div class="spec-item"><strong>${{k}}</strong><br>${{v}}</div>`
                        ).join('');
                        trainingHtml = `<div class="selling-points"><h4>💡 Sales Knowledge</h4><span class="headline">${{item.specs.headline}}</span><ul>${{points}}</ul><div class="specs-grid">${{specs}}</div></div>`;
                    }} else {{
                        trainingHtml = `<div style="margin-top:10px; color:#aaa; font-style:italic; font-size:0.9em;">Training card not yet created for this model.</div>`;
                    }}
                    return `<div class="card ${{item.specs ? 'has-specs' : ''}}"><div class="card-header"><div><a href="${{item.link}}" target="_blank">${{item.title}}</a><br><span class="stock-tag">#${{item.stock}}</span></div><span class="location-tag">${{item.location}}</span></div>${{trainingHtml}}</div>`;
                }}).join('');
            }}
            render(inventory);
            searchInput.addEventListener('keyup', (e) => {{
                const term = e.target.value.toLowerCase();
                const filtered = inventory.filter(item => item.title.toLowerCase().includes(term) || item.location.toLowerCase().includes(term) || item.stock.toLowerCase().includes(term));
                render(filtered);
            }});
        </script>
    </body>
    </html>
    """
    
    with open(OUTPUT_FILE, "w") as f:
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