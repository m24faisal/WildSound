# build_wikimedia_database.py
"""
THE BULLETPROOF VERSION:
- Uses Wikimedia Commons (No API keys, unblockable by firewalls)
- Handles Top 20 Wild + Top 10 Domestic per continent
"""

import requests
import time
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
OUTPUT_DIR = Path("wikimedia_animal_db")

HEADERS = {
    'User-Agent': 'WildSoundAppBuilder/1.0 (Educational Database Project)'
}

CONTINENTS = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
}

# Fixed domestic names
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
MIN_FILE_SIZE = 15000 # 15KB

# ==========================================
# STEP 1: INATURALIST (Get the List)
# ==========================================
def get_exact_species_list(place_id):
    species_list = []
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    
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
                species_list.append({'scientific': sci_name, 'common': com_name, 'category': 'Wild', 'class': animal_class})
    except: pass

    for sci_name, com_name in list(DOMESTIC_TAXA.items())[:MAX_DOMESTIC]:
        params_dom = {"taxon_name": sci_name, "place_id": place_id, "has[]": "sounds", "verifiable": True, "per_page": 1}
        try:
            response = requests.get(url, params=params_dom, headers=HEADERS, timeout=15)
            data = response.json()
            if data.get('total_results', 0) > 0:
                species_list.append({'scientific': sci_name, 'common': com_name, 'category': 'Domestic', 'class': 'Domestic'})
            time.sleep(0.2)
        except: pass
        
    return species_list

# ==========================================
# STEP 2: WIKIMEDIA COMMONS (The Downloader)
# ==========================================
def download_wikimedia(search_query, save_folder, max_files):
    """Searches Wikimedia for audio files and downloads them."""
    downloaded = 0
    
    api_url = "https://commons.wikimedia.org/w/api.php"
    
    # We search specifically for files that are audio and match our query
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f'"{search_query}" filetype:audio',
        "gsrnamespace": "6", # Namespace 6 is "File"
        "gsrlimit": 15,      # Get 15 to account for bad results
        "prop": "imageinfo",
        "iiprop": "url|size",
        "format": "json"
    }
    
    try:
        response = requests.get(api_url, params=params, headers=HEADERS, timeout=15)
        data = response.json()
        
        pages = data.get('query', {}).get('pages', {})
        
        for page_id, page_info in pages.items():
            if downloaded >= max_files:
                break
                
            if page_id == "-1": continue # Skip missing files
            
            img_info = page_info.get('imageinfo', [{}])[0]
            file_url = img_info.get('url')
            file_size = img_info.get('size', 0)
            
            if not file_url or file_size < MIN_FILE_SIZE:
                continue
                
            # Wikimedia files usually end in .ogg or .mp3
            ext = file_url.split('.')[-1].split('?')[0]
            if ext not in ['ogg', 'mp3', 'wav']:
                continue
                
            safe_name = search_query.replace(" ", "_")
            filepath = save_folder / f"{safe_name}_{page_id}.{ext}"
            
            if filepath.exists():
                downloaded += 1
                continue
                
            try:
                # Download the actual audio file
                r = requests.get(file_url, headers=HEADERS, timeout=30)
                if r.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(r.content)
                    downloaded += 1
                    time.sleep(0.5)
            except:
                if filepath.exists(): filepath.unlink()
                
    except Exception as e:
        pass # Silently fail on network hiccups
        
    return downloaded

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("=" * 60)
    print("WIKIMEDIA COMMONS DATABASE BUILDER")
    print("No API Keys Required. Firewall Friendly.")
    print("=" * 60)

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
            print(f"  {icon} [{idx+1}/{len(species_list)}] {com_name}", end=" ... ")
            
            # Smart Search: Use scientific name for wild, common name for domestic
            if animal_category == "Domestic":
                search_term = f"{com_name} animal sound"
            else:
                search_term = sci_name
                
            # Download from Wikimedia
            count = download_wikimedia(search_term, save_folder, MAX_FILES)
            
            if count > 0:
                print(f"✅ {count} files")
                total_downloaded += count
            else:
                print("❌ Not found")
                    
            time.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Downloaded {total_downloaded} clean .ogg/.mp3 files.")
    print("=" * 60)

if __name__ == "__main__":
    main()