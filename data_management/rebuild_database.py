# build_continental_database.py
"""
Step 1: Asks iNaturalist for Top Wild/Domestic animals per continent.
Step 2: Downloads CLEAN audio for those specific animals from Freesound.
"""

import requests
import time
import os
from pathlib import Path
import argparse
import warnings
import freesound

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
OUTPUT_DIR = Path("continental_animal_db")
FS_CLIENT = freesound.FreesoundClient()
FS_CLIENT.set_token("PASTE_YOUR_FREEOUND_API_KEY_HERE", "token")

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
MAX_FILES_PER_SPECIES = 5 # Keep this low to avoid rate limits for now

# ==========================================
# STEP 1: INATURALIST (Get the Names)
# ==========================================
def get_species_for_continent(place_id, limit_wild=20, limit_domestic=10):
    """Gets top species names from iNaturalist for a specific continent."""
    species_list = []
    
    # Get Wild Animals
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    params = {
        "place_id": place_id, "has[]": "sounds", "verifiable": True,
        "quality_grade": "research", "per_page": limit_wild, "order_by": "count", "order": "desc"
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        for result in data.get('results', [])[:limit_wild]:
            taxon = result.get('taxon', {})
            species_list.append({
                'scientific': taxon.get('name'),
                'common': taxon.get('preferred_common_name', 'Unknown').title(),
                'type': 'wild'
            })
    except Exception as e:
        print(f"    iNat Wild Error: {e}")

    # Get Domestic Animals
    for taxon_name in DOMESTIC_TAXA[:limit_domestic]:
        params = {"taxon_name": taxon_name, "place_id": place_id, "has[]": "sounds", "verifiable": True, "per_page": 1}
        try:
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            if data.get('total_results', 0) > 0:
                common_name = taxon_name.split()[-1].title() # e.g., "familiaris" -> "Familiaris"
                species_list.append({
                    'scientific': taxon_name,
                    'common': common_name,
                    'type': 'domestic'
                })
            time.sleep(0.2)
        except:
            pass
            
    return species_list

# ==========================================
# STEP 2: FREESOUND (Get the Clean Audio)
# ==========================================
def download_clean_audio(query_name, save_folder, max_files):
    """Downloads verified audio from Freesound."""
    downloaded = 0
    
    # We search for the common name + "sound" to get better results
    search_query = f"{query_name} sound animal"
    
    try:
        results = FS_CLIENT.text_search(
            query=search_query,
            filter="duration:[1 TO 30]",
            sort="rating_desc",
            fields="id,name,previews"
        )
        
        for sound in results:
            if downloaded >= max_files:
                break
                
            preview_url = sound.previews.preview_hq_mp3
            if not preview_url: continue
            
            safe_name = query_name.replace(" ", "_")
            filepath = save_folder / f"{safe_name}_{sound.id}.mp3"
            
            if filepath.exists():
                downloaded += 1
                continue
                
            # THE ANTI-CORRUPTION CHECK
            head = requests.head(preview_url, allow_redirects=True, timeout=5)
            if 'audio' not in head.headers.get('Content-Type', ''):
                continue # Skip HTML error pages silently
                
            try:
                sound.retrieve_preview(filepath)
                downloaded += 1
                time.sleep(0.5)
            except:
                pass
                
    except Exception as e:
        # Freesound API throws errors if you hit rate limits, we just skip
        pass
        
    return downloaded

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
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
            print("  No species found.")
            continue
            
        # Step 2: Download audio for each species
        for idx, species in enumerate(species_to_find):
            sci_name = species['scientific']
            com_name = species['common']
            animal_type = species['type']
            
            # Create folder: continent_db/Africa/Wild/Elephant/
            save_folder = OUTPUT_DIR / continent_name / animal_type.capitalize() / com_name
            save_folder.mkdir(parents=True, exist_ok=True)
            
            # Status indicator
            status = "🏠" if animal_type == "domestic" else "🦁"
            print(f"  {status} [{idx+1}/{len(species_to_find)}] {com_name} ({sci_name})", end=" ... ")
            
            # Download from Freesound using the common name
            count = download_clean_audio(com_name, save_folder, MAX_FILES_PER_SPECIES)
            
            if count > 0:
                print(f"✅ {count} files")
                total_downloaded += count
            else:
                print("❌ Not found on Freesound")
                
            time.sleep(1) # Sleep between species to respect Freesound limits

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Downloaded {total_downloaded} clean files.")
    print(f"Saved to: {OUTPUT_DIR}/")
    print("=" * 60)

if __name__ == "__main__":
    main()