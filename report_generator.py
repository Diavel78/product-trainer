import requests
import json
import csv
import io
import os
import datetime
import re
from collections import defaultdict

# --- CONFIGURATION ---
INVENTORY_FEED = "https://motohunt.com/feed/inventory/g2387-426e2dea251a38c7bd9a6d5ea9741933.json"
GOOGLE_FEED = "https://motohunt.com/feed/google-vehicle-ads/g2387-426e2dea251a38c7bd9a6d5ea9741933?store_code=abc"
FACEBOOK_FEED = "https://motohunt.com/feed/facebook-product/g2387-426e2dea251a38c7bd9a6d5ea9741933"
SNAPSHOT_FILE = "previous_snapshot.json"
REPORT_OUTPUT = "report.html"

# Store resolution from URL patterns
URL_STORE_MAP = {
    "andersonpowersportshavasu.com": "North Lake Havasu",
    "andersonpowersportsbullhead.com": "Bullhead City",
    "andersonpowersportsparker.com": "Parker",
    "andersonazwestallsports.com": "South Lake Havasu",
    "andersonpowersportsreno.com": "Reno",
}

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
    "Snowmobile": "Snowmobile", "Sled": "Snowmobile",
    "Trailer": "Trailer", "Cargo Trailer": "Trailer",
}


# ──────────────────────────────────────────────
# FEED FETCHERS
# ──────────────────────────────────────────────

def fetch_json_feed():
    """Fetch the main inventory JSON feed."""
    print("📦 Fetching Inventory JSON feed...")
    try:
        resp = requests.get(INVENTORY_FEED, timeout=60)
        data = resp.json()
        if isinstance(data, dict):
            for key in data:
                if isinstance(data[key], list):
                    return data[key]
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []


def fetch_google_feed():
    """Fetch the Google Vehicle Ads TSV feed."""
    print("🔍 Fetching Google Vehicle Ads feed...")
    try:
        resp = requests.get(GOOGLE_FEED, timeout=60)
        reader = csv.DictReader(io.StringIO(resp.text), delimiter='\t')
        return list(reader)
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []


def fetch_facebook_feed():
    """Fetch the Facebook/Meta Product CSV feed."""
    print("📘 Fetching Facebook Product feed...")
    try:
        resp = requests.get(FACEBOOK_FEED, timeout=60)
        reader = csv.DictReader(io.StringIO(resp.text))
        return list(reader)
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []


# ──────────────────────────────────────────────
# RESOLUTION HELPERS
# ──────────────────────────────────────────────

def resolve_store_from_url(url):
    """Extract store name from URL domain."""
    if not url:
        return "Unknown"
    url_lower = url.lower()
    for domain, store in URL_STORE_MAP.items():
        if domain in url_lower:
            return store
    return "Unknown"


def resolve_store_label(store_name):
    """Convert store name to numbered label."""
    for key, val in LOCATION_MAP.items():
        if key.lower() in store_name.lower():
            return val
    return store_name


def resolve_category(item):
    """Resolve category from inventory JSON item."""
    stock = str(item.get('stocknumber') or item.get('stock') or "").lower()
    if 't' in stock and len(stock) > 4:
        raw_type = str(item.get('type') or '').lower()
        if 'trailer' in raw_type:
            return "Trailer"

    raw_cat = item.get('type') or item.get('category') or ""
    if raw_cat:
        for key, val in CATEGORY_MAP.items():
            if key.lower() in raw_cat.lower():
                return val

    title = (item.get('title') or '').lower()
    if any(k in title for k in ['rzr', 'ranger', 'maverick', 'defender', 'general', 'zforce', 'uforce',
                                  'pioneer', 'talon', 'mule', 'teryx', 'wolverine', 'viking', 'commander',
                                  'sportsman', 'outlander', 'xpedition']):
        return "UTV"
    if any(k in title for k in ['ninja', 'rebel', 'scout', 'chief', 'challenger', 'ibex', 'grom',
                                  'crf', 'klr', 'klx', 'mt-', 'tenere', 'yz', 'slingshot']):
        return "Motorcycle"
    if any(k in title for k in ['sea-doo', 'waverunner', 'jet ski', 'spark', 'fishpro', 'gti', 'gtx',
                                  'rxt', 'rxp', 'gtr', 'superjet', 'jetblaster']):
        return "PWC"
    if any(k in title for k in ['bennington', 'godfrey', 'switch', 'pontoon', 'aquapatio', 'sweetwater']):
        return "Boat"
    if any(k in title for k in ['rmk', 'khaos', 'timbersled', 'snowmobile']):
        return "Snowmobile"
    if any(k in title for k in ['trailer', 'echo trailer']):
        return "Trailer"

    return "Other"


# ──────────────────────────────────────────────
# PROCESS & NORMALIZE INVENTORY
# ──────────────────────────────────────────────

def process_inventory(raw_data):
    """Normalize inventory JSON into a clean list."""
    inventory = []
    for item in raw_data:
        title = item.get('title') or f"{item.get('year', '')} {item.get('make', '')} {item.get('model', '')}"
        stock = str(item.get('stocknumber') or item.get('stock') or item.get('id') or "").strip().upper()
        url = item.get('url') or ""
        store = resolve_store_from_url(url)
        store_label = resolve_store_label(store)
        category = resolve_category(item)

        cond_raw = str(item.get('condition') or "").lower()
        url_lower = url.lower()
        condition = "Used" if ("used" in cond_raw or "pre-owned" in cond_raw or "used" in url_lower or "pre-owned" in url_lower) else "New"

        price_raw = str(item.get('price') or "").strip()
        try:
            price = float(re.sub(r'[^\d.]', '', price_raw)) if price_raw else 0
        except:
            price = 0

        photos = item.get('photos') or []
        if not photos and item.get('photo'):
            photos = [item['photo']]
        photo_count = len(photos)

        description = str(item.get('description') or "").strip()
        mileage = str(item.get('mileage') or "").strip()
        make = str(item.get('make') or "").strip()
        model = str(item.get('model') or "").strip()
        year = str(item.get('year') or "").strip()
        vin = str(item.get('vin') or "").strip()

        inventory.append({
            "stock": stock,
            "title": title.strip(),
            "store": store,
            "store_label": store_label,
            "category": category,
            "condition": condition,
            "price": price,
            "photo_count": photo_count,
            "description_length": len(description),
            "description": description[:200],
            "mileage": mileage,
            "make": make,
            "model": model,
            "year": year,
            "vin": vin,
            "url": url,
        })
    return inventory


def process_google_feed(raw_data):
    """Normalize Google feed rows."""
    items = []
    for row in raw_data:
        stock = str(row.get('id') or "").strip().upper()
        title = str(row.get('title') or "").strip()
        url = str(row.get('link') or "").strip()
        store = resolve_store_from_url(url)
        store_label = resolve_store_label(store)
        condition = str(row.get('condition') or "").strip()
        price_raw = str(row.get('price') or "").strip()
        msrp_raw = str(row.get('vehicle_msrp') or "").strip()
        mileage = str(row.get('mileage') or "").strip()
        description = str(row.get('description') or "").strip()
        image = str(row.get('image_link') or "").strip()
        additional = str(row.get('additional_image_link') or "").strip()

        try:
            price = float(re.sub(r'[^\d.]', '', price_raw)) if price_raw else 0
        except:
            price = 0
        try:
            msrp = float(re.sub(r'[^\d.]', '', msrp_raw)) if msrp_raw else 0
        except:
            msrp = 0

        # Count images
        photo_count = 0
        if additional:
            photo_count = len([x for x in additional.split(',') if x.strip()])
        elif image:
            photo_count = 1

        items.append({
            "stock": stock,
            "title": title,
            "store": store,
            "store_label": store_label,
            "condition": condition,
            "price": price,
            "msrp": msrp,
            "mileage": mileage,
            "description_length": len(description),
            "photo_count": photo_count,
            "url": url,
        })
    return items


def process_facebook_feed(raw_data):
    """Normalize Facebook feed rows."""
    items = []
    for row in raw_data:
        stock = str(row.get('id') or "").strip().upper()
        title = str(row.get('title') or "").strip()
        url = str(row.get('link') or "").strip()
        store = resolve_store_from_url(url)
        store_label = resolve_store_label(store)
        condition = str(row.get('condition') or "").strip()
        price_raw = str(row.get('price') or "").strip()
        description = str(row.get('description') or "").strip()
        image = str(row.get('image_link') or "").strip()
        brand = str(row.get('brand') or "").strip()

        try:
            price = float(re.sub(r'[^\d.]', '', price_raw)) if price_raw else 0
        except:
            price = 0

        items.append({
            "stock": stock,
            "title": title,
            "store": store,
            "store_label": store_label,
            "condition": condition,
            "price": price,
            "description_length": len(description),
            "has_image": bool(image),
            "brand": brand,
            "url": url,
        })
    return items


# ──────────────────────────────────────────────
# FEED HEALTH AUDIT
# ──────────────────────────────────────────────

def audit_inventory(inventory):
    """Audit the main inventory feed for data quality issues."""
    issues = []
    for item in inventory:
        unit_issues = []

        if item['price'] == 0:
            unit_issues.append("No price listed")
        if item['photo_count'] < 3:
            unit_issues.append(f"Only {item['photo_count']} photo(s) (need 3+)")
        if item['description_length'] < 50:
            unit_issues.append(f"Missing or short description ({item['description_length']} chars)")
        if item['condition'] == "Used" and not item['mileage']:
            unit_issues.append("Used unit — no mileage/hours listed")

        if unit_issues:
            issues.append({
                "stock": item['stock'],
                "title": item['title'],
                "store_label": item['store_label'],
                "category": item['category'],
                "condition": item['condition'],
                "url": item['url'],
                "problems": unit_issues,
            })
    return issues


def audit_google(google_items):
    """Audit Google Vehicle Ads feed."""
    issues = []
    for item in google_items:
        unit_issues = []

        if item['price'] == 0:
            unit_issues.append("No price in Google feed")
        if item['msrp'] == 0 and item['condition'].lower() == 'new':
            unit_issues.append("New unit missing MSRP")
        if item['photo_count'] < 3:
            unit_issues.append(f"Only {item['photo_count']} image(s) in Google feed")
        if item['description_length'] < 50:
            unit_issues.append("Missing or short description in Google feed")
        if item['condition'].lower() == 'used' and not item['mileage']:
            unit_issues.append("Used unit — no mileage in Google feed")

        if unit_issues:
            issues.append({
                "stock": item['stock'],
                "title": item['title'],
                "store_label": item['store_label'],
                "condition": item['condition'],
                "url": item['url'],
                "problems": unit_issues,
            })
    return issues


def audit_facebook(fb_items):
    """Audit Facebook/Meta Product feed."""
    issues = []
    for item in fb_items:
        unit_issues = []

        if item['price'] == 0:
            unit_issues.append("No price in Facebook feed")
        if not item['has_image']:
            unit_issues.append("No image in Facebook feed")
        if item['description_length'] < 50:
            unit_issues.append("Missing or short description in Facebook feed")
        if not item['brand']:
            unit_issues.append("Missing brand in Facebook feed")

        if unit_issues:
            issues.append({
                "stock": item['stock'],
                "title": item['title'],
                "store_label": item['store_label'],
                "condition": item['condition'],
                "url": item['url'],
                "problems": unit_issues,
            })
    return issues


# ──────────────────────────────────────────────
# DELTA REPORT
# ──────────────────────────────────────────────

def load_previous_snapshot():
    """Load previous day's snapshot."""
    if not os.path.exists(SNAPSHOT_FILE):
        return None
    try:
        with open(SNAPSHOT_FILE, 'r') as f:
            return json.load(f)
    except:
        return None


def save_snapshot(inventory):
    """Save current inventory as snapshot for tomorrow's comparison."""
    snapshot = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "units": {}
    }
    for item in inventory:
        snapshot["units"][item["stock"]] = {
            "title": item["title"],
            "store_label": item["store_label"],
            "category": item["category"],
            "condition": item["condition"],
            "price": item["price"],
        }
    with open(SNAPSHOT_FILE, 'w') as f:
        json.dump(snapshot, f, indent=2)
    print(f"💾 Snapshot saved: {len(snapshot['units'])} units")


def compute_delta(current_inventory, previous_snapshot):
    """Compare current inventory to previous snapshot."""
    if not previous_snapshot:
        return {"added": [], "removed": [], "price_changes": [], "prev_date": None}

    prev_units = previous_snapshot.get("units", {})
    prev_date = previous_snapshot.get("date", "Unknown")

    current_stocks = {item["stock"]: item for item in current_inventory}
    prev_stocks = set(prev_units.keys())
    curr_stocks = set(current_stocks.keys())

    added = []
    for stock in (curr_stocks - prev_stocks):
        item = current_stocks[stock]
        added.append({
            "stock": stock,
            "title": item["title"],
            "store_label": item["store_label"],
            "category": item["category"],
            "condition": item["condition"],
            "price": item["price"],
        })

    removed = []
    for stock in (prev_stocks - curr_stocks):
        prev = prev_units[stock]
        removed.append({
            "stock": stock,
            "title": prev["title"],
            "store_label": prev["store_label"],
            "category": prev.get("category", ""),
            "condition": prev.get("condition", ""),
            "price": prev.get("price", 0),
        })

    price_changes = []
    for stock in (curr_stocks & prev_stocks):
        curr_price = current_stocks[stock]["price"]
        prev_price = prev_units[stock].get("price", 0)
        if curr_price != prev_price and (curr_price > 0 or prev_price > 0):
            price_changes.append({
                "stock": stock,
                "title": current_stocks[stock]["title"],
                "store_label": current_stocks[stock]["store_label"],
                "old_price": prev_price,
                "new_price": curr_price,
                "change": curr_price - prev_price,
            })

    added.sort(key=lambda x: x['store_label'])
    removed.sort(key=lambda x: x['store_label'])
    price_changes.sort(key=lambda x: x['change'])

    return {
        "added": added,
        "removed": removed,
        "price_changes": price_changes,
        "prev_date": prev_date,
    }


# ──────────────────────────────────────────────
# INVENTORY SUMMARY STATS
# ──────────────────────────────────────────────

def compute_summary(inventory):
    """Compute inventory summary stats by location and category."""
    stores = sorted(set(item['store_label'] for item in inventory))
    categories = sorted(set(item['category'] for item in inventory))

    by_store = defaultdict(lambda: {"new": 0, "used": 0, "total": 0, "total_value": 0})
    by_category = defaultdict(lambda: {"new": 0, "used": 0, "total": 0})
    by_store_category = defaultdict(lambda: defaultdict(int))

    for item in inventory:
        sl = item['store_label']
        cat = item['category']
        cond = item['condition'].lower()

        by_store[sl]["total"] += 1
        by_store[sl]["total_value"] += item["price"]
        if cond == "new":
            by_store[sl]["new"] += 1
        else:
            by_store[sl]["used"] += 1

        by_category[cat]["total"] += 1
        if cond == "new":
            by_category[cat]["new"] += 1
        else:
            by_category[cat]["used"] += 1

        by_store_category[sl][cat] += 1

    return {
        "stores": stores,
        "categories": categories,
        "by_store": dict(by_store),
        "by_category": dict(by_category),
        "by_store_category": {k: dict(v) for k, v in by_store_category.items()},
        "total": len(inventory),
        "total_new": sum(1 for i in inventory if i['condition'] == 'New'),
        "total_used": sum(1 for i in inventory if i['condition'] == 'Used'),
    }


# ──────────────────────────────────────────────
# HTML REPORT GENERATOR
# ──────────────────────────────────────────────

def generate_report(summary, inv_issues, google_issues, fb_issues, delta, inventory):
    """Generate the full HTML report."""
    timestamp = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")
    
    # ── Issue severity counts ──
    total_issues = len(inv_issues) + len(google_issues) + len(fb_issues)
    
    # Categorize inventory issues by type
    issue_type_counts = defaultdict(int)
    for iss in inv_issues:
        for p in iss['problems']:
            if 'price' in p.lower():
                issue_type_counts['no_price'] += 1
            elif 'photo' in p.lower():
                issue_type_counts['low_photos'] += 1
            elif 'description' in p.lower():
                issue_type_counts['bad_description'] += 1
            elif 'mileage' in p.lower() or 'hours' in p.lower():
                issue_type_counts['no_mileage'] += 1

    # Issues by store
    issues_by_store = defaultdict(list)
    for iss in inv_issues:
        issues_by_store[iss['store_label']].append(iss)

    # ── Build HTML sections ──
    
    # Summary cards
    store_cards_html = ""
    for store in sorted(summary['by_store'].keys()):
        s = summary['by_store'][store]
        val_display = f"${s['total_value']:,.0f}" if s['total_value'] > 0 else "—"
        issue_count = len(issues_by_store.get(store, []))
        issue_badge = f'<span class="issue-badge">{issue_count} issues</span>' if issue_count > 0 else '<span class="ok-badge">Clean</span>'
        store_cards_html += f"""
        <div class="store-card">
            <div class="store-name">{store}</div>
            <div class="store-numbers">
                <div class="stat-block">
                    <span class="stat-value">{s['total']}</span>
                    <span class="stat-label">Total</span>
                </div>
                <div class="stat-block">
                    <span class="stat-value new-val">{s['new']}</span>
                    <span class="stat-label">New</span>
                </div>
                <div class="stat-block">
                    <span class="stat-value used-val">{s['used']}</span>
                    <span class="stat-label">Used</span>
                </div>
            </div>
            <div class="store-footer">
                <span class="inv-value">{val_display}</span>
                {issue_badge}
            </div>
        </div>"""

    # Category breakdown
    cat_rows_html = ""
    for cat in sorted(summary['by_category'].keys()):
        c = summary['by_category'][cat]
        cat_rows_html += f"""
        <tr>
            <td class="cat-name">{cat}</td>
            <td class="num">{c['total']}</td>
            <td class="num new-val">{c['new']}</td>
            <td class="num used-val">{c['used']}</td>
        </tr>"""

    # ── Feed Health Issues Table ──
    def build_issues_table(issues, feed_name):
        if not issues:
            return f'<div class="no-issues">✓ No issues found in {feed_name}</div>'
        
        rows = ""
        for iss in issues:
            problems_html = "<br>".join(f'<span class="problem-tag">{p}</span>' for p in iss['problems'])
            title_link = f'<a href="{iss["url"]}" target="_blank">{iss["title"]}</a>' if iss.get('url') else iss['title']
            rows += f"""
            <tr>
                <td class="stock-cell">{iss['stock']}</td>
                <td>{title_link}</td>
                <td>{iss['store_label']}</td>
                <td>{iss.get('condition', '')}</td>
                <td>{problems_html}</td>
            </tr>"""
        
        return f"""
        <div class="issue-count-label">{len(issues)} units with issues</div>
        <table class="issues-table">
            <thead><tr>
                <th>Stock #</th><th>Unit</th><th>Location</th><th>Cond</th><th>Issues</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>"""

    inv_issues_html = build_issues_table(inv_issues, "Inventory Feed")
    google_issues_html = build_issues_table(google_issues, "Google Vehicle Ads Feed")
    fb_issues_html = build_issues_table(fb_issues, "Facebook Product Feed")

    # ── Delta Report ──
    delta_html = ""
    if delta['prev_date'] is None:
        delta_html = """
        <div class="delta-first-run">
            <p>This is the first run — no previous snapshot to compare against.</p>
            <p>Tomorrow's report will show units added, removed, and price changes.</p>
        </div>"""
    else:
        # Added
        added_rows = ""
        for a in delta['added']:
            price_str = f"${a['price']:,.0f}" if a['price'] > 0 else "No price"
            added_rows += f"""
            <tr>
                <td class="stock-cell">{a['stock']}</td>
                <td>{a['title']}</td>
                <td>{a['store_label']}</td>
                <td>{a['category']}</td>
                <td>{a['condition']}</td>
                <td>{price_str}</td>
            </tr>"""
        
        added_html = f"""
        <h3 class="delta-sub">➕ Units Added ({len(delta['added'])})</h3>
        {'<table class="delta-table"><thead><tr><th>Stock</th><th>Unit</th><th>Location</th><th>Type</th><th>Cond</th><th>Price</th></tr></thead><tbody>' + added_rows + '</tbody></table>' if added_rows else '<div class="no-issues">No new units added</div>'}
        """

        # Removed
        removed_rows = ""
        for r in delta['removed']:
            price_str = f"${r['price']:,.0f}" if r['price'] > 0 else "—"
            removed_rows += f"""
            <tr>
                <td class="stock-cell">{r['stock']}</td>
                <td>{r['title']}</td>
                <td>{r['store_label']}</td>
                <td>{r['category']}</td>
                <td>{r['condition']}</td>
                <td>{price_str}</td>
            </tr>"""
        
        removed_html = f"""
        <h3 class="delta-sub">➖ Units Removed / Sold ({len(delta['removed'])})</h3>
        {'<table class="delta-table"><thead><tr><th>Stock</th><th>Unit</th><th>Location</th><th>Type</th><th>Cond</th><th>Price</th></tr></thead><tbody>' + removed_rows + '</tbody></table>' if removed_rows else '<div class="no-issues">No units removed</div>'}
        """

        # Price Changes
        price_rows = ""
        for pc in delta['price_changes']:
            old_str = f"${pc['old_price']:,.0f}" if pc['old_price'] > 0 else "None"
            new_str = f"${pc['new_price']:,.0f}" if pc['new_price'] > 0 else "None"
            change = pc['change']
            if change > 0:
                change_str = f'<span class="price-up">+${change:,.0f}</span>'
            elif change < 0:
                change_str = f'<span class="price-down">−${abs(change):,.0f}</span>'
            else:
                change_str = "—"
            price_rows += f"""
            <tr>
                <td class="stock-cell">{pc['stock']}</td>
                <td>{pc['title']}</td>
                <td>{pc['store_label']}</td>
                <td>{old_str}</td>
                <td>{new_str}</td>
                <td>{change_str}</td>
            </tr>"""
        
        price_html = f"""
        <h3 class="delta-sub">💲 Price Changes ({len(delta['price_changes'])})</h3>
        {'<table class="delta-table"><thead><tr><th>Stock</th><th>Unit</th><th>Location</th><th>Old Price</th><th>New Price</th><th>Change</th></tr></thead><tbody>' + price_rows + '</tbody></table>' if price_rows else '<div class="no-issues">No price changes</div>'}
        """

        delta_html = f"""
        <div class="delta-meta">Compared against snapshot from <strong>{delta['prev_date']}</strong></div>
        {added_html}
        {removed_html}
        {price_html}
        """

    # ── Issue summary by type (top bar) ──
    health_score_pct = max(0, round(100 * (1 - total_issues / max(len(inventory), 1)), 1))
    
    # ── Assemble full HTML ──
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anderson Powersports — Operations Report</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,500;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0d1117;
            --surface: #161b22;
            --surface-2: #1c2129;
            --border: #30363d;
            --text: #e6edf3;
            --text-muted: #8b949e;
            --accent: #58a6ff;
            --green: #3fb950;
            --red: #f85149;
            --orange: #d29922;
            --purple: #bc8cff;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'DM Sans', sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.5;
            padding: 0;
        }}

        .top-bar {{
            background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
            border-bottom: 1px solid var(--border);
            padding: 28px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .top-bar h1 {{
            font-size: 1.6em;
            font-weight: 700;
            letter-spacing: -0.02em;
        }}
        .top-bar h1 span {{ color: var(--accent); }}
        .top-bar .meta {{
            font-size: 0.85em;
            color: var(--text-muted);
            text-align: right;
        }}

        .kpi-strip {{
            display: flex;
            gap: 0;
            border-bottom: 1px solid var(--border);
            overflow-x: auto;
        }}
        .kpi {{
            flex: 1;
            min-width: 150px;
            padding: 20px 24px;
            border-right: 1px solid var(--border);
            text-align: center;
        }}
        .kpi:last-child {{ border-right: none; }}
        .kpi-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.8em;
            font-weight: 600;
            line-height: 1.2;
        }}
        .kpi-label {{
            font-size: 0.75em;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-top: 4px;
        }}

        .content {{ max-width: 1400px; margin: 0 auto; padding: 32px 40px; }}

        .section {{
            margin-bottom: 40px;
        }}
        .section-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
        }}
        .section-header h2 {{
            font-size: 1.15em;
            font-weight: 700;
            letter-spacing: -0.01em;
        }}
        .section-header .badge {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75em;
            padding: 3px 10px;
            border-radius: 12px;
            font-weight: 600;
        }}
        .badge-red {{ background: rgba(248,81,73,0.15); color: var(--red); }}
        .badge-green {{ background: rgba(63,185,80,0.15); color: var(--green); }}
        .badge-blue {{ background: rgba(88,166,255,0.15); color: var(--accent); }}
        .badge-orange {{ background: rgba(210,153,34,0.15); color: var(--orange); }}

        /* Store cards */
        .store-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: 16px;
        }}
        .store-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            transition: border-color 0.2s;
        }}
        .store-card:hover {{ border-color: var(--accent); }}
        .store-name {{
            font-weight: 700;
            font-size: 0.95em;
            margin-bottom: 14px;
            color: var(--accent);
        }}
        .store-numbers {{
            display: flex;
            gap: 16px;
            margin-bottom: 14px;
        }}
        .stat-block {{ text-align: center; }}
        .stat-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.5em;
            font-weight: 600;
            display: block;
        }}
        .stat-label {{
            font-size: 0.7em;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .new-val {{ color: var(--green); }}
        .used-val {{ color: var(--orange); }}
        .store-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 12px;
            border-top: 1px solid var(--border);
            font-size: 0.82em;
        }}
        .inv-value {{ color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }}
        .issue-badge {{
            background: rgba(248,81,73,0.15);
            color: var(--red);
            padding: 2px 10px;
            border-radius: 10px;
            font-weight: 600;
            font-size: 0.85em;
        }}
        .ok-badge {{
            background: rgba(63,185,80,0.15);
            color: var(--green);
            padding: 2px 10px;
            border-radius: 10px;
            font-weight: 600;
            font-size: 0.85em;
        }}

        /* Category table */
        .cat-table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
        }}
        .cat-table th {{
            padding: 10px 16px;
            text-align: left;
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-muted);
            background: var(--surface-2);
            border-bottom: 1px solid var(--border);
        }}
        .cat-table td {{
            padding: 10px 16px;
            border-bottom: 1px solid var(--border);
            font-size: 0.9em;
        }}
        .cat-table tr:last-child td {{ border-bottom: none; }}
        .cat-name {{ font-weight: 600; }}
        .num {{ font-family: 'JetBrains Mono', monospace; text-align: center; }}

        /* Issues tables */
        .issues-table, .delta-table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
            font-size: 0.85em;
        }}
        .issues-table th, .delta-table th {{
            padding: 10px 14px;
            text-align: left;
            font-size: 0.72em;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-muted);
            background: var(--surface-2);
            border-bottom: 1px solid var(--border);
        }}
        .issues-table td, .delta-table td {{
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
            vertical-align: top;
        }}
        .issues-table tr:last-child td, .delta-table tr:last-child td {{ border-bottom: none; }}
        .stock-cell {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            font-size: 0.9em;
            white-space: nowrap;
        }}
        .issues-table a, .delta-table a {{
            color: var(--accent);
            text-decoration: none;
        }}
        .issues-table a:hover, .delta-table a:hover {{ text-decoration: underline; }}

        .problem-tag {{
            display: inline-block;
            background: rgba(248,81,73,0.1);
            color: var(--red);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            margin: 2px 0;
        }}
        .issue-count-label {{
            font-size: 0.85em;
            color: var(--red);
            font-weight: 600;
            margin-bottom: 10px;
        }}
        .no-issues {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            color: var(--green);
            font-weight: 500;
        }}

        /* Tabs */
        .tab-bar {{
            display: flex;
            gap: 4px;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0;
        }}
        .tab-btn {{
            padding: 10px 20px;
            background: none;
            border: none;
            color: var(--text-muted);
            font-family: 'DM Sans', sans-serif;
            font-size: 0.88em;
            font-weight: 500;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            margin-bottom: -1px;
            transition: all 0.15s;
        }}
        .tab-btn:hover {{ color: var(--text); }}
        .tab-btn.active {{
            color: var(--accent);
            border-bottom-color: var(--accent);
        }}
        .tab-panel {{ display: none; }}
        .tab-panel.active {{ display: block; }}

        /* Delta */
        .delta-meta {{
            font-size: 0.85em;
            color: var(--text-muted);
            margin-bottom: 20px;
            padding: 12px 16px;
            background: var(--surface);
            border-radius: 8px;
            border: 1px solid var(--border);
        }}
        .delta-first-run {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 24px;
            text-align: center;
            color: var(--text-muted);
        }}
        .delta-sub {{
            font-size: 1em;
            font-weight: 600;
            margin: 24px 0 12px 0;
        }}
        .delta-sub:first-child {{ margin-top: 0; }}
        .price-up {{ color: var(--red); font-weight: 600; font-family: 'JetBrains Mono', monospace; }}
        .price-down {{ color: var(--green); font-weight: 600; font-family: 'JetBrains Mono', monospace; }}

        /* Filter */
        .filter-bar {{
            display: flex;
            gap: 10px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }}
        .filter-select {{
            padding: 8px 14px;
            background: var(--surface);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-family: 'DM Sans', sans-serif;
            font-size: 0.85em;
            cursor: pointer;
        }}
        .filter-select:focus {{ border-color: var(--accent); outline: none; }}
        .search-input {{
            padding: 8px 14px;
            background: var(--surface);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-family: 'DM Sans', sans-serif;
            font-size: 0.85em;
            flex: 1;
            min-width: 200px;
        }}
        .search-input:focus {{ border-color: var(--accent); outline: none; }}

        /* Responsive */
        @media (max-width: 768px) {{
            .top-bar {{ padding: 20px; }}
            .content {{ padding: 20px; }}
            .store-grid {{ grid-template-columns: 1fr; }}
            .kpi {{ min-width: 100px; padding: 14px; }}
            .kpi-value {{ font-size: 1.3em; }}
        }}
    </style>
</head>
<body>

    <div class="top-bar">
        <div>
            <h1>Anderson Powersports <span>Operations Report</span></h1>
        </div>
        <div class="meta">
            {timestamp}<br>
            <a href="index.html" style="color: var(--accent); text-decoration: none; font-size: 0.95em;">← Back to Trainer</a>
        </div>
    </div>

    <div class="kpi-strip">
        <div class="kpi">
            <div class="kpi-value">{summary['total']}</div>
            <div class="kpi-label">Total Units</div>
        </div>
        <div class="kpi">
            <div class="kpi-value" style="color:var(--green)">{summary['total_new']}</div>
            <div class="kpi-label">New</div>
        </div>
        <div class="kpi">
            <div class="kpi-value" style="color:var(--orange)">{summary['total_used']}</div>
            <div class="kpi-label">Used</div>
        </div>
        <div class="kpi">
            <div class="kpi-value" style="color:{'var(--red)' if total_issues > 20 else 'var(--orange)' if total_issues > 0 else 'var(--green)'}">{total_issues}</div>
            <div class="kpi-label">Feed Issues</div>
        </div>
        <div class="kpi">
            <div class="kpi-value" style="color:var(--accent)">{len(delta['added'])}</div>
            <div class="kpi-label">Added Today</div>
        </div>
        <div class="kpi">
            <div class="kpi-value" style="color:var(--purple)">{len(delta['removed'])}</div>
            <div class="kpi-label">Removed Today</div>
        </div>
    </div>

    <div class="content">

        <!-- INVENTORY SNAPSHOT -->
        <div class="section">
            <div class="section-header">
                <h2>Inventory by Location</h2>
                <span class="badge badge-blue">{len(summary['by_store'])} stores</span>
            </div>
            <div class="store-grid">{store_cards_html}</div>
        </div>

        <div class="section">
            <div class="section-header">
                <h2>Inventory by Category</h2>
            </div>
            <table class="cat-table">
                <thead><tr><th>Category</th><th style="text-align:center">Total</th><th style="text-align:center">New</th><th style="text-align:center">Used</th></tr></thead>
                <tbody>{cat_rows_html}</tbody>
            </table>
        </div>

        <!-- FEED HEALTH AUDIT -->
        <div class="section">
            <div class="section-header">
                <h2>Feed Health Audit</h2>
                <span class="badge {'badge-red' if total_issues > 20 else 'badge-orange' if total_issues > 0 else 'badge-green'}">{total_issues} total issues</span>
            </div>

            <div class="tab-bar">
                <button class="tab-btn active" onclick="switchTab('inv')">Inventory Feed ({len(inv_issues)})</button>
                <button class="tab-btn" onclick="switchTab('google')">Google Ads Feed ({len(google_issues)})</button>
                <button class="tab-btn" onclick="switchTab('fb')">Facebook Feed ({len(fb_issues)})</button>
            </div>

            <div id="tab-inv" class="tab-panel active">
                <div class="filter-bar">
                    <select id="inv-store-filter" class="filter-select" onchange="filterIssues('inv')">
                        <option value="All">All Locations</option>
                    </select>
                    <select id="inv-type-filter" class="filter-select" onchange="filterIssues('inv')">
                        <option value="All">All Issue Types</option>
                        <option value="price">No Price</option>
                        <option value="photo">Low Photos</option>
                        <option value="description">Bad Description</option>
                        <option value="mileage">No Mileage (Used)</option>
                    </select>
                    <input type="text" id="inv-search" class="search-input" placeholder="Search stock # or title..." oninput="filterIssues('inv')">
                </div>
                {inv_issues_html}
            </div>
            <div id="tab-google" class="tab-panel">
                {google_issues_html}
            </div>
            <div id="tab-fb" class="tab-panel">
                {fb_issues_html}
            </div>
        </div>

        <!-- DELTA REPORT -->
        <div class="section">
            <div class="section-header">
                <h2>Daily Changes (Delta Report)</h2>
                <span class="badge badge-blue">{len(delta['added']) + len(delta['removed']) + len(delta['price_changes'])} changes</span>
            </div>
            {delta_html}
        </div>

    </div>

    <script>
        // Tab switching
        function switchTab(id) {{
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-' + id).classList.add('active');
            event.target.classList.add('active');
        }}

        // Populate store filter from table data
        (function() {{
            const table = document.querySelector('#tab-inv .issues-table');
            if (!table) return;
            const rows = table.querySelectorAll('tbody tr');
            const stores = new Set();
            rows.forEach(r => {{
                const cell = r.cells[2];
                if (cell) stores.add(cell.textContent.trim());
            }});
            const sel = document.getElementById('inv-store-filter');
            [...stores].sort().forEach(s => {{
                const opt = document.createElement('option');
                opt.value = s; opt.textContent = s;
                sel.appendChild(opt);
            }});
        }})();

        // Filter issues
        function filterIssues(prefix) {{
            const table = document.querySelector('#tab-' + prefix + ' .issues-table');
            if (!table) return;
            const rows = table.querySelectorAll('tbody tr');
            const storeVal = document.getElementById(prefix + '-store-filter')?.value || 'All';
            const typeVal = document.getElementById(prefix + '-type-filter')?.value || 'All';
            const searchVal = (document.getElementById(prefix + '-search')?.value || '').toLowerCase();

            rows.forEach(row => {{
                const store = row.cells[2]?.textContent.trim() || '';
                const stock = row.cells[0]?.textContent.trim().toLowerCase() || '';
                const title = row.cells[1]?.textContent.trim().toLowerCase() || '';
                const issues = row.cells[4]?.textContent.trim().toLowerCase() || '';

                let show = true;
                if (storeVal !== 'All' && store !== storeVal) show = false;
                if (typeVal !== 'All' && !issues.includes(typeVal)) show = false;
                if (searchVal && !stock.includes(searchVal) && !title.includes(searchVal)) show = false;

                row.style.display = show ? '' : 'none';
            }});
        }}
    </script>

</body>
</html>"""

    with open(REPORT_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Report generated: {REPORT_OUTPUT}")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Anderson Powersports — Operations Report Generator")
    print("=" * 60)

    # 1. Fetch all feeds
    raw_inventory = fetch_json_feed()
    raw_google = fetch_google_feed()
    raw_facebook = fetch_facebook_feed()

    print(f"\n📊 Feed sizes: Inventory={len(raw_inventory)}, Google={len(raw_google)}, Facebook={len(raw_facebook)}")

    if not raw_inventory:
        print("⚠️  No inventory data — aborting.")
        exit(1)

    # 2. Process feeds
    inventory = process_inventory(raw_inventory)
    google_items = process_google_feed(raw_google)
    fb_items = process_facebook_feed(raw_facebook)

    # 3. Compute summary
    summary = compute_summary(inventory)
    print(f"\n🏪 Stores: {', '.join(summary['stores'])}")
    print(f"   Total: {summary['total']} | New: {summary['total_new']} | Used: {summary['total_used']}")

    # 4. Audit feeds
    inv_issues = audit_inventory(inventory)
    google_issues = audit_google(google_items)
    fb_issues = audit_facebook(fb_items)
    print(f"\n🔍 Issues: Inventory={len(inv_issues)}, Google={len(google_issues)}, Facebook={len(fb_issues)}")

    # 5. Delta report
    previous = load_previous_snapshot()
    delta = compute_delta(inventory, previous)
    if delta['prev_date']:
        print(f"\n📈 Delta vs {delta['prev_date']}: +{len(delta['added'])} added, -{len(delta['removed'])} removed, {len(delta['price_changes'])} price changes")
    else:
        print("\n📈 First run — no previous snapshot for delta comparison")

    # 6. Generate report
    generate_report(summary, inv_issues, google_issues, fb_issues, delta, inventory)

    # 7. Save snapshot for next run
    save_snapshot(inventory)
