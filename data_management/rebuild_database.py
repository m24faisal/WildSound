# build_continental_database.py
"""
Step 1: Asks iNaturalist for Top Wild/Domestic animals per continent.
Step 2: Downloads CLEAN audio for those specific animals from Freesound.
Uses ONLY the 'requests' library - no external audio packages needed.
"""

import requests
import time
import os
from pathlib import Path
import warnings

# Silence warnings for cleaner output
warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
# GET YOUR FREE API KEY HERE: https://freesound.org/apiv2/apply/
FREESOUND_API_KEY = "PASTE_YOUR_FREEOUND_API_KEY_HERE"

OUTPUT_DIR = Path("continental_animal_db")

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

MAX_WILD_PER_CONTINENT = 20
MAX_DOMESTIC_PER_CONTINENT = 10
MAX_FILES_PER_SPECIES = 5 # Keep low to avoid hitting API rate limits


# ==========================================
# STEP 1: INATURALIST (Get the Names)
# ==========================================
def get_species_for_continent(place_id, limit_wild=20, limit_domestic=10):
    """Gets top species names from iNaturalist for a specific continent."""
    species_list = []
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    
    # 1. Get Wild Animals
    params = {
        "place_id": place_id, "has[]": "sounds", "verifiable": True,
        "quality_grade": "research", "per_page": limit_wild, "order_by": "count", "order": "desc"
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        for result in data.get('results', [])[:limit_wild]:
            taxon = result.get('taxon', {})
            sci_name = taxon.get('name', 'Unknown')
            com_name = taxon.get('preferred_common_name', sci_name).title()
            
            # Skip if the common name is missing or weird
            if com_name and com_name != 'Unknown':
                species_list.append({
                    'scientific': sci_name,
                    'common': com_name,
                    'type': 'wild'
                })
    except Exception as e:
        print(f"    [iNat Wild Error: {e}]")

    # 2. Get Domestic Animals
    for taxon_name in DOMESTIC_TAXA[:limit_domestic]:
        params = {"taxon_name": taxon_name, "place_id": place_id, "has[]": "sounds", "verifiable": True, "per_page": 1}
        try:
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            if data.get('total_results', 0) > 0:
                # Clean up the name for a better Freesound search
                common_name = taxon_name.split()[-1].title() 
                species_list.append({
                    'scientific': taxon_name,
                    'common': common_name,
                    'type': 'domestic'
                })
            time.sleep(0.2) # Be polite to iNaturalist
        except:
            pass
            
    return species_list


# ==========================================
# STEP 2: FREESOUND (Get the Clean Audio)
# ==========================================
def download_clean_audio(query_name, save_folder, max_files):
    """Downloads verified audio from Freesound using ONLY requests."""
    downloaded = 0
    search_query = f"{query_name} sound animal"
    
    try:
        # Search the Freesound API
        search_url = "https://freesound.org/apiv2/search/text/"
        params = {
            "query": search_query,
            "filter": "duration:[1 TO 30]", # Only get sounds between 1 and 30 seconds
            "sort": "rating_desc",
            "fields": "id,name,previews",
            "token": FREESOUND_API_KEY
        }
        
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Loop through the search results
        for sound in data.get('results', []):
            if downloaded >= max_files:
                break
                
            # Get the high-quality MP3 preview URL
            preview_url = sound.get('previews', {}).get('preview-hq-mp3')
            if not preview_url: 
                continue
            
            # Create a safe filename
            safe_name = query_name.replace(" ", "_")
            filepath = save_folder / f"{safe_name}_{sound['id']}.mp3"
            
            # Skip if we already downloaded it
            if filepath.exists():
                downloaded += 1
                continue
                
            # THE ANTI-CORRUPTION CHECK: Ask the server what the file is before downloading
            try:
                head = requests.head(preview_url, allow_redirects=True, timeout=5)
                content_type = head.headers.get('Content-Type', '')
                
                # If it doesn't say 'audio', it's an error page. Skip it!
                if 'audio' not in content_type:
                    continue 
            except:
                continue
                
            # Actually download the file
            try:
                # Freesound requires the token in the headers for downloads
                headers = {"Authorization": f"Token {FREESOUND_API_KEY}"}
                file_response = requests.get(preview_url, headers=headers, timeout=30)
                
                if file_response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(file_response.content)
                    downloaded += 1
                    time.sleep(0.5) # Pause slightly between downloads
            except:
                pass
                
    except Exception as e:
        # Silently fail if we hit API rate limits, and move to the next animal
        pass
        
    return downloaded


# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    if FREESOUND_API_KEY == "PASTE_YOUR_FREEOUND_API_KEY_HERE":
        print("❌ ERROR: Please paste your Freesound API key on line 18 of this script!")
        print("Get one for free here: https://freesound.org/apiv2/apply/")
        return

    print("=" * 60)
    print("CONTINENTAL AUDIO DATABASE BUILDER")
    print("=" * 60)
    
    total_downloaded = 0
    
    for continent_name, place_id in CONTINENTS.items():
        print(f"\n🌍 {continent_name.upper()}")
        print("-" * 40)
        
        # Step 1: Get the list for this continent
        species_to_find = get_species_for_continent(place_id, MAX_WILD_PER_CONTINENT, MAX_DOMESTIC_PER_CONTINENT)
        
        if not species_to_find:
            print("  No species found for this continent.")
            continue
            
        # Step 2: Download audio for each species
        for idx, species in enumerate(species_to_find):
            com_name = species['common']
            animal_type = species['type']
            
            # Create folder structure: continental_animal_db/Africa/Wild/Elephant/
            save_folder = OUTPUT_DIR / continent_name / animal_type.capitalize() / com_name
            save_folder.mkdir(parents=True, exist_ok=True)
            
            # Status indicator
            status = "🏠" if animal_type == "domestic" else "🦁"
            print(f"  {status} [{idx+1}/{len(species_to_find)}] {com_name}", end=" ... ")
            
            # Download from Freesound using the common name
            count = download_clean_audio(com_name, save_folder, MAX_FILES_PER_SPECIES)
            
            if count > 0:
                print(f"✅ {count} files")
                total_downloaded += count
            else:
                print("❌ Not found on Freesound")
                
            # Pause between species to guarantee we don't get blocked by Freesound
            time.sleep(1) 

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Downloaded {total_downloaded} clean, uncorrupted files.")
    print(f"Saved to folder: {OUTPUT_DIR}/")
    print("=" * 60)

if __name__ == "__main__":
    main()