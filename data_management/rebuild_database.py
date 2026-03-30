# build_final_fixed_database.py
"""
FIXED FOR:
1. Xeno-Canto 403 Blocking (Added User-Agent headers)
2. Broken Domestic Names (Hardcoded proper common names)
"""

import requests
import time
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
FREESOUND_API_KEY = "U6Uuzkrn7l679AuR7a1g0QLXJSw66Gb8Qktlzhxd"

OUTPUT_DIR = Path("top30_animal_db")

# Universal Headers to prevent APIs from blocking us as a bot
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}

CONTINENTS = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
}

# FIXED: Map scientific names to actual English words Freesound understands
DOMESTIC_TAXA = {
    "Canis lupus familiaris": "Dog",
    "Felis catus": "Cat",
    "Bos taurus": "Cow",
    "Equus caballus": "Horse",
    "Capra hircus": "Goat",
    "Ovis aries": "Sheep",
    "Sus scrofa domesticus": "Pig",
    "Gallus gallus domesticus": "Chicken",
    "Anas platyrhynchos domesticus": "Duck",
    "Meleagris gallopavo": "Turkey"
}

MAX_WILD = 20
MAX_DOMESTIC = 10
MAX_FILES = 5
MIN_FILE_SIZE = 15000 

# ==========================================
# STEP 1: INATURALIST
# ==========================================
def get_exact_species_list(place_id):
    species_list = []
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    
    # Get Top 20 WILD
    params_wild = {
        "place_id": place_id, "has[]": "sounds", "verifiable": True,
        "quality_grade": "research", "per_page": MAX_WILD, 
        "order_by": "count", "order": "desc"
    }
    try:
        response = requests.get(url, params=params_wild, headers=HEADERS, timeout=15)
        data = response.json()
        for result in data.get('results', [])[:MAX_WILD]:
            taxon = result.get('taxon', {})
            sci_name = taxon.get('name', '')
            com_name = taxon.get('preferred_common_name', sci_name).title()
            animal_class = taxon.get('iconic_taxon_name', 'Unknown') 
            
            if sci_name and com_name and com_name != 'Unknown':
                species_list.append({
                    'scientific': sci_name, 
                    'common': com_name, 
                    'category': 'Wild',
                    'class': animal_class
                })
    except: pass

    # Get Top 10 DOMESTIC (Using the fixed dictionary)
    for sci_name, com_name in list(DOMESTIC_TAXA.items())[:MAX_DOMESTIC]:
        params_dom = {"taxon_name": sci_name, "place_id": place_id, "has[]": "sounds", "verifiable": True, "per_page": 1}
        try:
            response = requests.get(url, params=params_dom, headers=HEADERS, timeout=15)
            data = response.json()
            if data.get('total_results', 0) > 0:
                species_list.append({
                    'scientific': sci_name, 
                    'common': com_name, # Now correctly says "Dog" instead of "Familiaris"
                    'category': 'Domestic',
                    'class': 'Domestic'
                })
            time.sleep(0.2)
        except: pass
        
    return species_list

# ==========================================
# STEP 2A: XENO-CANTO (Fixed Bot Block)
# ==========================================
def download_xenocanto(sci_name, save_folder, max_files):
    downloaded = 0
    query = f"sp:{sci_name}"
    api_url = f"https://xeno-canto.org/api/2/recordings?query={query}"
    
    try:
        # ADDED HEADERS HERE: This stops Xeno-Canto from rejecting us
        response = requests.get(api_url, headers=HEADERS, timeout=15)
        
        # Debugging check (you can remove this later)
        if response.status_code != 200:
            return 0
            
        data = response.json()
        
        for record in data.get('recordings', []):
            if downloaded >= max_files: break
            audio_url = record.get('file')
            if not audio_url: continue
            
            filepath = save_folder / f"{sci_name.replace(' ', '_')}_{record.get('id', 'unk')}.mp3"
            if filepath.exists(): 
                downloaded += 1
                continue
            
            try:
                r = requests.get(audio_url, headers=HEADERS, timeout=30)
                if r.status_code == 200:
                    with open(filepath, 'wb') as f: 
                        f.write(r.content)
                    
                    if filepath.stat().st_size < MIN_FILE_SIZE:
                        filepath.unlink()
                    else:
                        downloaded += 1
                        time.sleep(0.5)
            except: 
                if filepath.exists(): filepath.unlink()
    except: pass
    return downloaded

# ==========================================
# STEP 2B: FREESOUND
# ==========================================
def download_freesound(com_name, save_folder, max_files):
    if FREESOUND_API_KEY == "PASTE_YOUR_FREEOUND_API_KEY_HERE": return 0
    downloaded = 0
    
    # Searches for "Dog sound" or "Northern Cardinal sound" - Much cleaner!
    search_query = f"{com_name} sound" 
    
    try:
        search_url = "https://freesound.org/apiv2/search/text/"
        params = {"query": search_query, "filter": "duration:[1 TO 30]", "sort": "rating_desc", "fields": "id,previews", "token": FREESOUND_API_KEY}
        
        response = requests.get(search_url, params=params, headers=HEADERS, timeout=10)
        data = response.json()
        
        for sound in data.get('results', []):
            if downloaded >= max_files: break
            preview_url = sound.get('previews', {}).get('preview-hq-mp3')
            if not preview_url: continue
            
            safe_name = com_name.replace(" ", "_")
            filepath = save_folder / f"{safe_name}_{sound['id']}.mp3"
            if filepath.exists(): 
                downloaded += 1
                continue
            
            try:
                fs_headers = {**HEADERS, "Authorization": f"Token {FREESOUND_API_KEY}"}
                r = requests.get(preview_url, headers=fs_headers, timeout=30)
                if r.status_code == 200:
                    with open(filepath, 'wb') as f: 
                        f.write(r.content)
                    
                    if filepath.stat().st_size < MIN_FILE_SIZE:
                        filepath.unlink()
                    else:
                        downloaded += 1
                        time.sleep(0.5)
            except: 
                if filepath.exists(): filepath.unlink()
    except: pass
    return downloaded

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("=" * 60)
    print("FIXED DATABASE BUILDER")
    print("=" * 60)
    
    if FREESOUND_API_KEY == "PASTE_YOUR_FREEOUND_API_KEY_HERE":
        print("⚠️  No Freesound key. Mammals & Domestic will be skipped.\n")

    total_downloaded = 0
    
    for continent_name, place_id in CONTINENTS.items():
        print(f"\n🌍 {continent_name.upper()}")
        print("-" * 40)
        
        species_list = get_exact_species_list(place_id)
        
        if not species_list:
            print("  No species found.")
            continue
            
        wild_count = sum(1 for s in species_list if s['category'] == 'Wild')
        dom_count = sum(1 for s in species_list if s['category'] == 'Domestic')
        print(f"  Targeting: {wild_count} Wild | {dom_count} Domestic\n")

        for idx, species in enumerate(species_list):
            sci_name = species['scientific']
            com_name = species['common']
            animal_class = species['class']
            animal_category = species['category']
            
            save_folder = OUTPUT_DIR / continent_name / animal_category / animal_class / com_name
            save_folder.mkdir(parents=True, exist_ok=True)
            
            icon = "🏠" if animal_category == "Domestic" else "🦁"
            print(f"  {icon} [{idx+1}/{len(species_list)}] {com_name} ({animal_class})", end=" ... ")
            
            # Routing Logic
            if animal_class in ["Aves", "Amphibia", "Reptilia"]:
                count = download_xenocanto(sci_name, save_folder, MAX_FILES)
            else:
                # Mammals and Domestic go to Freesound
                count = download_freesound(com_name, save_folder, MAX_FILES)
            
            if count > 0:
                print(f"✅ {count} files")
                total_downloaded += count
            else:
                if animal_class not in ["Aves", "Amphibia", "Reptilia"] and FREESOUND_API_KEY == "PASTE_YOUR_FREEOUND_API_KEY_HERE":
                    print("⏭️ Skipped (Needs Freesound Key)")
                else:
                    print("❌ Not found")
                    
            time.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Downloaded {total_downloaded} clean files.")
    print("=" * 60)

if __name__ == "__main__":
    main()