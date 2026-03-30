# build_exact_top30_database.py
"""
EXACT REQUIREMENTS:
- Top 20 Wild animals per continent
- Top 10 Domestic animals per continent
SMART ROUTING:
- Birds/Amphibians/Reptiles -> Xeno-Canto
- Mammals/Domestic -> Freesound
"""

import requests
import time
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
FREESOUND_API_KEY = "U6Uuzkrn7l679AuR7a1g0QLXJSw66Gb8Qktlzhxd" # Required for Mammals & Domestic

OUTPUT_DIR = Path("top30_animal_db")

CONTINENTS = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
}

DOMESTIC_TAXA = [
    "Canis lupus familiaris", "Felis catus", "Bos taurus", "Equus caballus",
    "Capra hircus", "Ovis aries", "Sus scrofa domesticus", "Gallus gallus domesticus",
    "Anas platyrhynchos domesticus", "Meleagris gallopavo"
]

MAX_WILD = 20      # EXACTLY top 20 wild
MAX_DOMESTIC = 10  # EXACTLY top 10 domestic
MAX_FILES = 5      # Audio files per species

# ==========================================
# STEP 1: INATURALIST (Exact Top 20 & Top 10)
# ==========================================
def get_exact_species_list(place_id):
    """Gets Top 20 Wild and Top 10 Domestic, and identifies their class for routing."""
    species_list = []
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    
    # 1. Get Top 20 WILD (Any class: bird, mammal, reptile, etc.)
    params_wild = {
        "place_id": place_id, "has[]": "sounds", "verifiable": True,
        "quality_grade": "research", "per_page": MAX_WILD, 
        "order_by": "count", "order": "desc"
    }
    try:
        response = requests.get(url, params=params_wild, timeout=15)
        data = response.json()
        for result in data.get('results', [])[:MAX_WILD]:
            taxon = result.get('taxon', {})
            sci_name = taxon.get('name', '')
            com_name = taxon.get('preferred_common_name', sci_name).title()
            # This is the magic key that tells us what database to use!
            animal_class = taxon.get('iconic_taxon_name', 'Unknown') 
            
            if sci_name and com_name and com_name != 'Unknown':
                species_list.append({
                    'scientific': sci_name, 
                    'common': com_name, 
                    'category': 'Wild',
                    'class': animal_class # e.g., "Aves", "Mammalia", "Amphibia"
                })
    except: pass

    # 2. Get Top 10 DOMESTIC
    for taxon_name in DOMESTIC_TAXA[:MAX_DOMESTIC]:
        params_dom = {"taxon_name": taxon_name, "place_id": place_id, "has[]": "sounds", "verifiable": True, "per_page": 1}
        try:
            response = requests.get(url, params=params_dom, timeout=15)
            data = response.json()
            if data.get('total_results', 0) > 0:
                common_name = taxon_name.split()[-1].title() 
                species_list.append({
                    'scientific': taxon_name, 
                    'common': common_name, 
                    'category': 'Domestic',
                    'class': 'Domestic' # Force route to Freesound
                })
            time.sleep(0.2)
        except: pass
        
    return species_list

# ==========================================
# STEP 2A: XENO-CANTO (For Birds, Amphibians, Reptiles)
# ==========================================
def download_xenocanto(sci_name, save_folder, max_files):
    downloaded = 0
    query = f"sp:{sci_name}"
    api_url = f"https://xeno-canto.org/api/2/recordings?query={query}"
    
    try:
        response = requests.get(api_url, timeout=15)
        if response.status_code != 200: return 0
        data = response.json()
        
        for record in data.get('recordings', []):
            if downloaded >= max_files: break
            audio_url = record.get('file')
            if not audio_url: continue
            
            filepath = save_folder / f"{sci_name.replace(' ', '_')}_{record.get('id', 'unk')}.mp3"
            if filepath.exists(): downloaded += 1; continue
            
            try:
                head = requests.head(audio_url, allow_redirects=True, timeout=5)
                if 'audio' not in head.headers.get('Content-Type', ''): continue
            except: continue
            
            try:
                r = requests.get(audio_url, timeout=30)
                if r.status_code == 200:
                    with open(filepath, 'wb') as f: f.write(r.content)
                    downloaded += 1; time.sleep(0.5)
            except: pass
    except: pass
    return downloaded

# ==========================================
# STEP 2B: FREESOUND (For Mammals & Domestic)
# ==========================================
def download_freesound(sci_name, com_name, save_folder, max_files):
    if FREESOUND_API_KEY == "PASTE_YOUR_FREEOUND_API_KEY_HERE": return 0
    downloaded = 0
    search_query = f"{com_name} {sci_name} sound"
    
    try:
        search_url = "https://freesound.org/apiv2/search/text/"
        params = {"query": search_query, "filter": "duration:[1 TO 30]", "sort": "rating_desc", "fields": "id,previews", "token": FREESOUND_API_KEY}
        response = requests.get(search_url, params=params, timeout=10)
        data = response.json()
        
        for sound in data.get('results', []):
            if downloaded >= max_files: break
            preview_url = sound.get('previews', {}).get('preview-hq-mp3')
            if not preview_url: continue
            
            filepath = save_folder / f"{sci_name.replace(' ', '_')}_{sound['id']}.mp3"
            if filepath.exists(): downloaded += 1; continue
            
            try:
                head = requests.head(preview_url, allow_redirects=True, timeout=5)
                if 'audio' not in head.headers.get('Content-Type', ''): continue
            except: continue
            
            try:
                headers = {"Authorization": f"Token {FREESOUND_API_KEY}"}
                r = requests.get(preview_url, headers=headers, timeout=30)
                if r.status_code == 200:
                    with open(filepath, 'wb') as f: f.write(r.content)
                    downloaded += 1; time.sleep(0.5)
            except: pass
    except: pass
    return downloaded

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("=" * 60)
    print("EXACT TOP 30 DATABASE BUILDER")
    print("Target: 20 Wild + 10 Domestic per Continent")
    print("=" * 60)
    
    if FREESOUND_API_KEY == "PASTE_YOUR_FREEOUND_API_KEY_HERE":
        print("⚠️  WARNING: No Freesound key. Mammals & Domestic will be skipped.\n")

    total_downloaded = 0
    
    for continent_name, place_id in CONTINENTS.items():
        print(f"\n🌍 {continent_name.upper()}")
        print("-" * 40)
        
        # Get exactly 30 animals for this continent
        species_list = get_exact_species_list(place_id)
        
        if not species_list:
            print("  No species found.")
            continue
            
        # Count what we got
        wild_count = sum(1 for s in species_list if s['category'] == 'Wild')
        dom_count = sum(1 for s in species_list if s['category'] == 'Domestic')
        print(f"  Found: {wild_count} Wild | {dom_count} Domestic\n")

        for idx, species in enumerate(species_list):
            sci_name = species['scientific']
            com_name = species['common']
            animal_class = species['class']
            animal_category = species['category']
            
            # Create folder: top30_animal_db/Africa/Wild/Aves/Sparrow/
            save_folder = OUTPUT_DIR / continent_name / animal_category / animal_class / com_name
            save_folder.mkdir(parents=True, exist_ok=True)
            
            # Status icon
            icon = "🏠" if animal_category == "Domestic" else "🦁"
            print(f"  {icon} [{idx+1}/{len(species_list)}] {com_name} ({animal_class})", end=" ... ")
            
            # ROUTING LOGIC: Decide which database to use
            if animal_class in ["Aves", "Amphibia", "Reptilia"]:
                count = download_xenocanto(sci_name, save_folder, MAX_FILES)
            else:
                # Mammals, Domestic, Insects, Fish, etc. all go to Freesound
                count = download_freesound(sci_name, com_name, save_folder, MAX_FILES)
            
            if count > 0:
                print(f"✅ {count} files")
                total_downloaded += count
            else:
                if animal_class not in ["Aves", "Amphibia", "Reptilia"] and FREESOUND_API_KEY == "PASTE_YOUR_FREEOUND_API_KEY_HERE":
                    print("⏭️ Skipped (Needs Freesound Key)")
                else:
                    print("❌ Not found in database")
                    
            time.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Downloaded {total_downloaded} clean files.")
    print("=" * 60)

if __name__ == "__main__":
    main()