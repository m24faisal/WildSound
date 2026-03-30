# build_debug_version.py
"""
DEBUG VERSION - Forces APIs to show us their error messages
"""

import requests
import time
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
FREESOUND_API_KEY = "U6Uuzkrn7l679AuR7a1g0QLXJSw66Gb8Qktlzhxd" # Leave as is for now to test Xeno-Canto

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}

CONTINENTS = {"north_america": 97394}

# ==========================================
# STEP 1: INATURALIST
# ==========================================
def get_exact_species_list(place_id):
    species_list = []
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    params_wild = {"place_id": place_id, "has[]": "sounds", "verifiable": True, "quality_grade": "research", "per_page": 3, "order_by": "count", "order": "desc"}
    
    try:
        response = requests.get(url, params=params_wild, headers=HEADERS, timeout=15)
        data = response.json()
        for result in data.get('results', [])[:3]:
            taxon = result.get('taxon', {})
            sci_name = taxon.get('name', '')
            com_name = taxon.get('preferred_common_name', sci_name).title()
            animal_class = taxon.get('iconic_taxon_name', 'Unknown') 
            if sci_name and com_name:
                species_list.append({'scientific': sci_name, 'common': com_name, 'category': 'Wild', 'class': animal_class})
    except Exception as e:
        print(f"    [iNat Error] {e}")
        
    # Add a domestic animal to test Freesound
    species_list.append({'scientific': "Canis lupus familiaris", 'common': "Dog", 'category': 'Domestic', 'class': 'Domestic'})
    return species_list

# ==========================================
# STEP 2A: XENO-CANTO DEBUG
# ==========================================
def download_xenocanto_debug(sci_name, save_folder):
    print(f"      -> Asking Xeno-Canto for: 'sp:{sci_name}'")
    query = f"sp:{sci_name}"
    api_url = f"https://xeno-canto.org/api/2/recordings?query={query}"
    
    try:
        response = requests.get(api_url, headers=HEADERS, timeout=15)
        print(f"      -> Xeno-Canto Status Code: {response.status_code}")
        
        # If not 200, print what the server actually said
        if response.status_code != 200:
            print(f"      -> XENO-CANTO ERROR MESSAGE: {response.text[:200]}")
            return 0
            
        data = response.json()
        record_count = len(data.get('recordings', []))
        print(f"      -> Xeno-Canto found {record_count} recordings in JSON.")
        
        if record_count == 0:
            return 0
            
        # Try to download the first one
        audio_url = data['recordings'][0].get('file')
        print(f"      -> Attempting download from: {audio_url}")
        
        r = requests.get(audio_url, headers=HEADERS, timeout=30)
        print(f"      -> Audio file download status: {r.status_code}")
        
        if r.status_code == 200:
            filepath = save_folder / "test.mp3"
            with open(filepath, 'wb') as f: 
                f.write(r.content)
            size = filepath.stat().st_size
            print(f"      -> SUCCESS! File size: {size} bytes")
            return 1
        else:
            print(f"      -> AUDIO DOWNLOAD FAILED.")
            return 0
            
    except Exception as e:
        print(f"      -> PYTHON EXCEPTION: {e}")
        return 0

# ==========================================
# STEP 2B: FREESOUND DEBUG
# ==========================================
def download_freesound_debug(com_name, save_folder):
    print(f"      -> Asking Freesound for: '{com_name} sound'")
    
    if FREESOUND_API_KEY == "PASTE_YOUR_FREEOUND_API_KEY_HERE":
        print(f"      -> SKIPPED: No API Key provided.")
        return 0

    try:
        search_url = "https://freesound.org/apiv2/search/text/"
        params = {"query": f"{com_name} sound", "filter": "duration:[1 TO 30]", "sort": "rating_desc", "fields": "id,previews", "token": FREESOUND_API_KEY}
        
        response = requests.get(search_url, params=params, headers=HEADERS, timeout=10)
        print(f"      -> Freesound Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"      -> FREESOUND ERROR MESSAGE: {response.text[:200]}")
            return 0
            
        data = response.json()
        result_count = len(data.get('results', []))
        print(f"      -> Freesound found {result_count} results in JSON.")
        
        if result_count == 0:
            return 0
            
        preview_url = data['results'][0].get('previews', {}).get('preview-hq-mp3')
        print(f"      -> Attempting download from: {preview_url}")
        
        fs_headers = {**HEADERS, "Authorization": f"Token {FREESOUND_API_KEY}"}
        r = requests.get(preview_url, headers=fs_headers, timeout=30)
        print(f"      -> Audio file download status: {r.status_code}")
        
        if r.status_code == 200:
            filepath = save_folder / "test.mp3"
            with open(filepath, 'wb') as f: 
                f.write(r.content)
            size = filepath.stat().st_size
            print(f"      -> SUCCESS! File size: {size} bytes")
            return 1
        else:
            print(f"      -> AUDIO DOWNLOAD FAILED.")
            return 0
            
    except Exception as e:
        print(f"      -> PYTHON EXCEPTION: {e}")
        return 0

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("=" * 60)
    print("DEBUG MODE - EXPOSING HIDDEN ERRORS")
    print("=" * 60)
    
    OUTPUT_DIR = Path("debug_test")
    OUTPUT_DIR.mkdir(exist_ok=True)

    for continent_name, place_id in CONTINENTS.items():
        print(f"\n🌍 Testing {continent_name.upper()} (Just top 3 wild + 1 domestic)")
        print("-" * 40)
        
        species_list = get_exact_species_list(place_id)

        for species in species_list:
            sci_name = species['scientific']
            com_name = species['common']
            animal_class = species['class']
            
            save_folder = OUTPUT_DIR / com_name.replace(" ", "_")
            save_folder.mkdir(parents=True, exist_ok=True)
            
            print(f"\n  🦁 {com_name} ({animal_class})")
            
            if animal_class in ["Aves", "Amphibia", "Reptilia"]:
                download_xenocanto_debug(sci_name, save_folder)
            else:
                download_freesound_debug(com_name, save_folder)

if __name__ == "__main__":
    main()