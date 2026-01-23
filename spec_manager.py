import json
import os
import re
import requests
from bs4 import BeautifulSoup
import time
import random

# Try to import googlesearch, but handle if it's missing
try:
    from googlesearch import search
    HAS_GOOGLE_SEARCH = True
except ImportError:
    HAS_GOOGLE_SEARCH = False
    print("⚠️  'googlesearch-python' not installed. Auto-discovery will be limited.")

DB_FILE = "specs_database.json"

# --- SEED DATA BASED ON RESEARCH ---
# This ensures immediate high-quality results for top models
SEED_DATA = [
    {
        "model_keywords": ["RZR Pro R", "Pro R 4", "Pro R Ultimate"],
        "oem": "Polaris",
        "headline": "The 225HP Naturally Aspirated Beast",
        "selling_points": [
            "225 HP ProStar Fury 2.0L engine - The biggest factory engine in a side-by-side.",
            "One-piece chassis with fully welded cage (No bolts to rattle loose).",
            "MaxLink Suspension: 29 inches of usable travel for eating whoops.",
            "Steel belt transmission (No rubber belt to break)."
        ],
        "specs": {
            "Horsepower": "225 HP",
            "Engine": "2.0L 4-Cylinder DOHC",
            "Width": "74 inches",
            "Clearance": "16 inches",
            "Alternator": "1700 Watt (Belt driven)"
        }
    },
    {
        "model_keywords": ["Maverick R", "Maverick R X"],
        "oem": "Can-Am",
        "headline": "240HP DCT Precision Monster",
        "selling_points": [
            "240 HP Rotax Turbo engine - Highest HP in class.",
            "7-Speed Dual Clutch Transmission (DCT) - No CVT belt.",
            "Tall Knuckle Suspension geometry for superior bump absorption.",
            "10.25-inch Touchscreen Display with BRP GO! navigation."
        ],
        "specs": {
            "Horsepower": "240 HP",
            "Transmission": "7-Speed DCT",
            "Travel": "25 in (F) / 26 in (R)",
            "Width": "77 inches"
        }
    },
    {
        "model_keywords": ["Ranger XD 1500", "Ranger Crew XD"],
        "oem": "Polaris",
        "headline": "Extreme Duty: Built Like a Truck",
        "selling_points": [
            "Industry-first 1500cc 3-cylinder engine (110 HP).",
            "STEELDRIVE transmission: 100% steel belt, fully sealed, liquid cooled.",
            "3,500 lb towing capacity (More than many compact cars).",
            "Heated seats and HVAC available in NorthStar trims."
        ],
        "specs": {
            "Horsepower": "110 HP",
            "Torque": "105 lb-ft",
            "Service Interval": "6,000 Miles (Transmission)",
            "Box Capacity": "1,500 lbs"
        }
    },
    {
        "model_keywords": ["Xpedition", "XP", "ADV"],
        "oem": "Polaris",
        "headline": "The Overlanding Adventure Rig",
        "selling_points": [
            "Fully enclosed cab with HVAC standard on NorthStar trims.",
            "200+ mile fuel range for long adventures.",
            "Lockable, weathertight storage options (ADV model).",
            "Fox Podium QS3 shocks for plush ride quality."
        ],
        "specs": {
            "Horsepower": "114 HP",
            "Engine": "ProStar 1000 Gen 2",
            "Tires": "30-inch Pro Armor Crawler XP"
        }
    },
        {
        "model_keywords": ["Defender", "Defender MAX", "Defender HD10", "Defender HD9"],
        "oem": "Can-Am",
        "headline": "Workhorse with Comfort",
        "selling_points": [
            "Rotax HD10 V-Twin delivers 82 HP and 69 lb-ft torque.",
            "Quietest cab in the utility segment.",
            "Versa-Pro bench seats for all-day comfort.",
            "Removable toolbox and massive under-dash storage."
        ],
        "specs": {
            "Engine": "Rotax V-Twin",
            "Torque": "69 lb-ft (HD10)",
            "Towing": "2,500 lbs"
        }
    },
    {
        "model_keywords": ["Maverick X3", "X3 MAX", "X3 DS", "X3 RS"],
        "oem": "Can-Am",
        "headline": "The Dune Shredder",
        "selling_points": [
            "200 HP Turbo RR engine options available.",
            "Low seating position provides a true sports-car feel.",
            "Smart-Shox technology available for instant dampening adjustments.",
            "72-inch width options for ultimate stability."
        ],
        "specs": {
            "Horsepower": "135 HP (std) / 200 HP (Turbo RR)",
            "Width": "64 or 72 inches",
            "Travel": "Up to 24 inches"
        }
    },
    {
        "model_keywords": ["Ranger XP 1000", "Ranger Crew XP 1000", "Ranger Crew 1000"],
        "oem": "Polaris",
        "headline": "The King of Utility",
        "selling_points": [
            "82 HP ProStar engine with 2,500 lb towing capacity.",
            "13 inches of ground clearance for ranch/farm work.",
            "Drive modes: Performance, Standard, Work.",
            "Widest range of Lock & Ride accessories available."
        ],
        "specs": {
            "Horsepower": "82 HP",
            "Engine": "999cc Twin Cylinder",
            "Payload": "1,500 lbs"
        }
    },
    {
        "model_keywords": ["RZR 200", "RZR 200 EFI"],
        "oem": "Polaris",
        "headline": "The Ultimate Youth Ride",
        "selling_points": [
            "Youth Ride Control: Set speed limits and geofencing via App.",
            "Helmet Aware Technology: Vehicle won't start unless the helmet beacon is detected.",
            "Hard doors and roof standard for safety.",
            "Independent rear suspension for a smooth ride."
        ],
        "specs": {
            "Engine": "180cc EFI",
            "Age Rating": "10+ Years",
            "Safety": "Pin Code Start & Helmet Aware",
            "Tires": "24-inch"
        }
    },
    {
        "model_keywords": ["Switch", "Switch Cruise", "Switch Sport"],
        "oem": "Sea-Doo",
        "headline": "The Pontoon Revolution",
        "selling_points": [
            "Handlebar steering makes it as easy to drive as a Sea-Doo.",
            "Modular deck tiles: Move seats and tables anywhere in seconds.",
            "Jet propulsion: No prop to worry about in shallow water.",
            "Brakes: The only pontoon with Sea-Doo's iBR braking system."
        ],
        "specs": {
            "Engine": "Rotax 1630 ACE",
            "Steering": "Handlebar",
            "Brakes": "iBR System"
        }
    },
    {
        "model_keywords": ["Spark", "Spark Trixx"],
        "oem": "Sea-Doo",
        "headline": "Playful and Affordable Fun",
        "selling_points": [
            "Lightweight Polytec hull makes it easy to tow and whip around.",
            "Rotax 900 ACE engine is extremely fuel efficient.",
            "Trixx package allows for wheelies on water.",
            "Fully customizable with graphic kits."
        ],
        "specs": {
            "Hull": "Polytec",
            "Engine": "Rotax 900 ACE (60 or 90 HP)",
            "Capacity": "2 or 3 Rider options"
        }
    },
    {
        "model_keywords": ["RXP", "RXP-X", "RXT-X", "325"],
        "oem": "Sea-Doo",
        "headline": "325 Horsepower - Highest in Industry",
        "selling_points": [
            "Rotax 1630 ACE-325 engine delivers 0-60 in 3.4 seconds.",
            "T3-R Hull design for incredibly aggressive cornering (RXP).",
            "Ergolock-R seating locks you in during hard turns.",
            "Tech Package: BRP Audio Premium and full color display."
        ],
        "specs": {
            "Horsepower": "325 HP",
            "Engine": "Rotax 1630 ACE Supercharged",
            "0-60 mph": "3.4 Seconds"
        }
    },
    {
        "model_keywords": ["FX Cruiser", "FX SVHO", "FX HO"],
        "oem": "Yamaha",
        "headline": "Luxury & Performance on Water",
        "selling_points": [
            "SVHO Supercharged engine options for massive speed.",
            "Connext touchscreen display with GPS maps.",
            "RiDE system: Dual throttle control for intuitive handling.",
            "Multi-mount system for speakers and accessories."
        ],
        "specs": {
            "Engine": "1.8L Supercharged SVHO",
            "Hull": "NanoXcel2",
            "Display": "7-inch Color Touchscreen"
        }
    },
    {
        "model_keywords": ["GP1800", "GP SVHO", "GP HO"],
        "oem": "Yamaha",
        "headline": "Race-Ready Watercraft",
        "selling_points": [
            "The #1 choice for professional racers.",
            "Cornering auto-trim for tighter turns.",
            "Launch control for perfect hole shots.",
            "Integrated audio system available."
        ],
        "specs": {
            "Engine": "SVHO or HO 1.8L",
            "Rider Capacity": "1-3 persons",
            "Hull": "NanoXcel2"
        }
    },
    {
        "model_keywords": ["KRX 1000", "Teryx KRX"],
        "oem": "Kawasaki",
        "headline": "Built to Conquer Rocks",
        "selling_points": [
            "Massive torque CVT designed specifically for crawling.",
            "High clearance A-arms and trailing arms standard.",
            "Roomiest cabin in the class.",
            "Stock 31-inch tires on beadlock wheels (select trims)."
        ],
        "specs": {
            "Engine": "999cc Parallel Twin",
            "Suspension": "FOX 2.5 Podium LSC",
            "Width": "68 inches"
        }
    },
    {
        "model_keywords": ["Mule", "Mule PRO-FXT", "Mule PRO-MX"],
        "oem": "Kawasaki",
        "headline": "Kawasaki Strong 3-Year Warranty",
        "selling_points": [
            "Trans Cab system (FXT) changes from 3 to 6 seats in 1 minute.",
            "3-Year Warranty is standard (Industry Leading).",
            "Steel cargo bed floor for durability.",
            "Simple, reliable design favored by fleets."
        ],
        "specs": {
            "Warranty": "3-Year Limited",
            "Steering": "Electric Power Steering (EPS)",
            "Engine": "812cc 3-Cylinder or 999cc Twin"
        }
    },
    {
        "model_keywords": ["Talon 1000", "Talon 1000R", "Talon 1000X"],
        "oem": "Honda",
        "headline": "Direct Drive Reliability",
        "selling_points": [
            "Dual-Clutch Transmission (DCT) - Shifts like a car, no rubber belts.",
            "i-4WD System provides traction without steering effort.",
            "FOX Live Valve suspension available on select trims.",
            "Launch Control mode for drag racing starts."
        ],
        "specs": {
            "Horsepower": "105 HP (approx)",
            "Transmission": "6-Speed Automatic DCT",
            "Width": "64 in (X) / 68.4 in (R)"
        }
    },
    {
        "model_keywords": ["Pioneer 1000", "Pioneer 1000-5", "Pioneer 1000-6"],
        "oem": "Honda",
        "headline": "Versatility Defined",
        "selling_points": [
            "QuickFlip seating (1000-5) converts cargo bed to seats instantly.",
            "DCT Transmission - No rubber belts to slip or burn.",
            "Turf Mode to protect delicate lawns.",
            "1000-6 Crew offers full-size rear doors and massive room."
        ],
        "specs": {
            "Engine": "999cc Twin",
            "Transmission": "6-Speed DCT",
            "Capacity": "3, 5, or 6 passengers"
        }
    },
    {
        "model_keywords": ["CRF450R", "CRF250R", "CRF450RX"],
        "oem": "Honda",
        "headline": "Podium Proven Motocross",
        "selling_points": [
            "Unicam engine design provides instant power and light weight.",
            "HRC Launch Control for perfect starts.",
            "Showa suspension tailored for track dominance.",
            "Reliability that wins championships."
        ],
        "specs": {
            "Engine": "Liquid-cooled Single Cylinder",
            "Start": "Electric Start",
            "Frame": "Aluminum Twin-Spar"
        }
    },
    {
        "model_keywords": ["KX450", "KX250"],
        "oem": "Kawasaki",
        "headline": "The Bike That Builds Champions",
        "selling_points": [
            "Ergo-Fit system: Adjustable footpegs and handlebars.",
            "Hydraulic clutch for consistent feel.",
            "Launch Control Mode standard.",
            "Slim perimeter frame for nimble handling."
        ],
        "specs": {
            "Clutch": "Hydraulic",
            "Start": "Electric",
            "Frame": "Aluminum Perimeter"
        }
    },
    {
        "model_keywords": ["KLX110", "KLX140", "KLX300"],
        "oem": "Kawasaki",
        "headline": "Off-Road Play Bikes",
        "selling_points": [
            "Push-button electric start.",
            "Centrifugal clutch (on 110) prevents stalling.",
            "Disc brakes front and rear (on 140 and up).",
            "Low maintenance air-cooled engines."
        ],
        "specs": {
            "Transmission": "4 or 5 Speed",
            "Start": "Electric",
            "Brakes": "Petal Disc"
        }
    },
    {
        "model_keywords": ["Raptor 90", "YFZ50", "Grizzly 90"],
        "oem": "Yamaha",
        "headline": "Youth ATV Reliability",
        "selling_points": [
            "CVT Transmission (Automatic) - Just gas and go.",
            "Electric start with kick-start backup.",
            "Parental speed limiters included.",
            "Styling matches the big adult quads."
        ],
        "specs": {
            "Engine": "Air-cooled 4-stroke",
            "Transmission": "CVT",
            "Drive": "Chain"
        }
    },
    {
        "model_keywords": ["TT-R125", "TT-R110", "TT-R50", "PW50"],
        "oem": "Yamaha",
        "headline": "The Place Learning Starts",
        "selling_points": [
            "PW50 is the iconic first bike with shaft drive (no chain maintenance).",
            "Electric start on TT-R lines.",
            "Adjustable throttle stop to limit speed for learners.",
            "Proven durability for generations."
        ],
        "specs": {
            "Engine": "Air-cooled 4-stroke (2-stroke PW50)",
            "Start": "Electric (TT-R models)",
            "Drive": "Shaft (PW50) / Chain (TT-R)"
        }
    },
    {
        "model_keywords": ["RMAX 1000", "RMAX2", "RMAX4"],
        "oem": "Yamaha",
        "headline": "Proven Off-Road Capability",
        "selling_points": [
            "10-Year Belt Warranty (The only one in the industry).",
            "Class-leading 108 HP 999cc Twin engine.",
            "D-Mode (Drive Mode) throttle control: Crawl, Trail, Sport.",
            "Comfortable interior with soft touch points and high quality feel."
        ],
        "specs": {
            "Engine": "999cc Parallel Twin",
            "Warranty": "10-Year Belt",
            "Tires": "30-inch Maxxis Carnivore"
        }
    },
    {
        "model_keywords": ["YXZ", "YXZ1000R"],
        "oem": "Yamaha",
        "headline": "Shift Your Perspective",
        "selling_points": [
            "The only pure sport SxS with a sequential manual transmission.",
            "10,500 RPM Redline - sounds incredible.",
            "Launch Control system for perfect starts.",
            "Rear-mounted radiator to keep heat out of the cabin."
        ],
        "specs": {
            "Transmission": "5-Speed Sequential Manual or Sport Shift",
            "Engine": "998cc Triple Cylinder",
            "Drivetrain": "On-Command 4WD"
        }
    },
    {
        "model_keywords": ["Outlaw 70", "Outlaw 110", "Sportsman 110"],
        "oem": "Polaris",
        "headline": "Kids' First ATV",
        "selling_points": [
            "EFI (Electronic Fuel Injection) for reliable starting in cold/hot weather.",
            "Parent-adjustable speed limiter.",
            "Safety flag and helmet included.",
            "Long-travel suspension for a smooth ride."
        ],
        "specs": {
            "Engine": "EFI 4-Stroke",
            "Safety": "Speed Limiter Standard",
            "Start": "Electric"
        }
    }
]

class SpecManager:
    def __init__(self):
        self.db = self.load_db()
        self.seed_if_empty()

    def load_db(self):
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                return json.load(f)
        return []

    def save_db(self):
        with open(DB_FILE, 'w') as f:
            json.dump(self.db, f, indent=4)

    def seed_if_empty(self):
        """Pre-populates the DB with high-quality seed data if it's new."""
        # Simple check: if seed items aren't present, add them
        existing_headlines = {i.get('headline') for i in self.db}
        for item in SEED_DATA:
            if item['headline'] not in existing_headlines:
                self.db.append(item)
        self.save_db()

    def find_specs(self, title):
        """
        Tries to find a spec match in the DB.
        Returns the spec dict or None.
        """
        # Sort DB by keyword specificity (longer lists of keywords first)
        # This helps avoid matching "RZR" generally when we have "RZR Pro R" specifically
        sorted_specs = sorted(self.db, key=lambda x: len(x['model_keywords'][0]), reverse=True)
        
        for model in sorted_specs:
            for keyword in model['model_keywords']:
                # Basic normalization
                if keyword.lower() in title.lower():
                    return model
        return None

    def discover_specs(self, title):
        """
        The 'AI Bot' function.
        Attempts to fetch specs from the web if not found in DB.
        """
        if not HAS_GOOGLE_SEARCH:
            print(f"⚠️  Cannot auto-discover specs for '{title}' (googlesearch lib missing)")
            return None

        print(f"🤖 AI Bot: Searching web for '{title}' specs...")
        
        try:
            # 1. Search for the vehicle
            query = f"{title} specs horsepower width clearance"
            results = list(search(query, num_results=3, advanced=True))
            
            if not results:
                return None

            # 2. Try to scrape the first result
            url = results[0].url
            print(f"   Reading: {url}")
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.content, 'html.parser')
            text = soup.get_text()

            # 3. Simple Heuristic Extraction (The "AI" part)
            extracted_specs = {}
            
            # HP Regex
            hp_match = re.search(r'(\d+)\s*(?:hp|horsepower)', text, re.IGNORECASE)
            if hp_match:
                extracted_specs['Horsepower'] = f"{hp_match.group(1)} HP"

            # Width Regex
            width_match = re.search(r'Width.*?(\d+(?:\.\d+)?)\s*(?:in|")', text, re.IGNORECASE)
            if width_match:
                extracted_specs['Width'] = f"{width_match.group(1)} inches"

            # Clearance Regex
            clear_match = re.search(r'(?:Ground)?\s*Clearance.*?(\d+(?:\.\d+)?)\s*(?:in|")', text, re.IGNORECASE)
            if clear_match:
                extracted_specs['Ground Clearance'] = f"{clear_match.group(1)} inches"

            if not extracted_specs:
                print("   ❌ Could not extract structured data.")
                return None

            # 4. Construct a new DB entry
            new_entry = {
                "model_keywords": [title.split()[0] + " " + title.split()[1]], # Very rough guess at model name
                "oem": "Unknown", # Could infer from title
                "headline": f"Auto-Discovered Specs for {title}",
                "selling_points": ["Specs auto-fetched from web search.", f"Source: {url}"],
                "specs": extracted_specs
            }
            
            # Save to DB so we don't search again
            self.db.append(new_entry)
            self.save_db()
            print("   ✅ Specs saved to database.")
            return new_entry

        except Exception as e:
            print(f"   ❌ Error during auto-discovery: {e}")
            return None

if __name__ == "__main__":
    # Test
    sm = SpecManager()
    print(f"Database loaded with {len(sm.db)} entries.")