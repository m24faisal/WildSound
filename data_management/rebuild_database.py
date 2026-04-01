# build_strict_quotas_final.py
"""
FINAL STRICT QUOTA DATABASE BUILDER (TWO-STEP API FIX)
- Uses a two-step process to bypass iNaturalist's API bug with taxon_id + quality_grade.
- Target: 12 Birds, 3 Amphibians, 2 Reptiles, 3 Mammals, 10 Domestic per continent.
"""

import requests
import time
import random
import concurrent.futures
import shutil
from pathlib import Path
import warnings
import yt_dlp
from typing import Any, cast

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
OUTPUT_DIR = Path("youtube_smart_db")

HEADERS = {'User-Agent': 'WildSoundAppBuilder/1.0'}

CONTINENTS = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
}

TAXON_BIRDS = 3
TAXON_AMPHIBIANS = 209
TAXON_REPTILES = 260
TAXON_MAMMALS = 40151

QUOTAS = {
    TAXON_BIRDS: 12,
    TAXON_AMPHIBIANS: 3,
    TAXON_REPTILES: 2,
    TAXON_MAMMALS: 3
}

CLASS_NAMES = {
    TAXON_BIRDS: "Aves",
    TAXON_AMPHIBIANS: "Amphibia",
    TAXON_REPTILES: "Reptilia",
    TAXON_MAMMALS: "Mammalia"
}

DOMESTIC_TAXA = {
    "Canis lupus familiaris": "Dog barking sound",
    "Felis catus": "Cat meowing sound",
    "Bos taurus": "Cow mooing sound",
    "Equus caballus": "Horse neighing sound",
    "Capra hircus": "Goat bleating sound",
    "Ovis aries": "Sheep baaing sound",
    "Sus scrofa domesticus": "Pig oinking sound",
    "Gallus gallus domesticus": "Chicken clucking sound",
    "Anas platyrhynchos domesticus": "Duck quacking sound",
    "Meleagris gallopavo": "Turkey gobbling sound"
}

MAX_FILES = 5 

# ==========================================
# STEP 1: INATURALIST GETTERS
# ==========================================
def get_wild_by_class(place_id, taxon_id, limit):
    species_list = []
    
    # STEP 1: Get top species for this class (NO sounds filter to prevent API bug)
    url1 = "https://api.inaturalist.org/v1/observations/species_counts"
    params1 = {
        "place_id": place_id, 
        "taxon_id": taxon_id,      
        "verifiable": True,
        "quality_grade": 1,  
        "per_page": limit, 
        "order_by": "count", "order": "desc"
    }
    
    try:
        response = requests.get(url1, params=params1, headers=HEADERS, timeout=20)
        data = response.json()
        results = data.get('results', [])
        
        total_available = data.get('total_results', 0)
        print(f"         [iNat found {total_available} total. Filtering for sounds...]", end=" ... ")
        
        # STEP 2: Loop through and individually verify they have sounds
        for result in results:
            taxon = result.get('taxon', {})
            sci_name = taxon.get('name', '')
            com_name = taxon.get('preferred_common_name', sci_name).title()
            
            if not sci_name or com_name == 'Unknown':
                continue
                
            url2 = "https://api.inaturalist.org/v1/observations"
            params2 = {"taxon_name": sci_name, "place_id": place_id, "has[]": "sounds", "verifiable": True, "per_page": 1}
            
            try:
                check_resp = requests.get(url2, params=params2, headers=HEADERS, timeout=10)
                if check_resp.json().get('total_results', 0) > 0:
                    species_list.append({'common': com_name, 'class': CLASS_NAMES[taxon_id]})
                    if len(species_list) >= limit:
                        break 
            except:
                pass
                
    except Exception as e:
        print(f"         [API ERROR: {e}]", end=" ... ")
        
    return species_list

def get_domestic(place_id):
    species_list = []
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    for sci_name, yt_search in DOMESTIC_TAXA.items():
        params = {"taxon_name": sci_name, "place_id": place_id, "has[]": "sounds", "verifiable": True, "per_page": 1}
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=10)
            if response.json().get('total_results', 0) > 0:
                com_name = yt_search.split()[0]
                species_list.append({'common': com_name, 'class': 'Domestic', 'yt_search': yt_search})
        except: pass
        time.sleep(0.2)
    return species_list

# ==========================================
# STEP 2: YOUTUBE DOWNLOADER
# ==========================================
def download_youtube_audio(animal_name, search_query, save_folder, max_files):
    for part_file in save_folder.glob("*.part"):
        try: part_file.unlink()
        except: pass

    files_before = len(list(save_folder.glob("*.mp3")))
    safe_name = animal_name.replace(" ", "_")

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
        'outtmpl': str(save_folder / f"{safe_name}_%(autonumber)d.%(ext)s"),
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',}],
        'default_search': 'ytsearch100', 
        'max_downloads': max_files,       
        'noplaylist': True, 'quiet': True, 'no_warnings': True,
        'max_filesize': 10 * 1024 * 1024, 'ignoreerrors': True, 'socket_timeout': 20, 
    }
    
    def run_download():
        with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
            ydl.download([search_query])

    try:
        run_download()
    except: pass

    for part_file in save_folder.glob("*.part"):
        try: part_file.unlink()
        except: pass

    return len(list(save_folder.glob("*.mp3"))) - files_before

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("=" * 60)
    print("FINAL STRICT QUOTA DATABASE BUILDER")
    print("=" * 60)
    
    if OUTPUT_DIR.exists():
        print("\n🧹 Deleting old database folder...")
        shutil.rmtree(OUTPUT_DIR)
        time.sleep(1)
        
    print("Target: 12 Birds, 3 Amphibians, 2 Reptiles, 3 Mammals, 10 Domestic")
    print("Starting fresh from scratch...\n")

    total_downloaded = 0
    
    for continent_name, place_id in CONTINENTS.items():
        print(f"🌍 {continent_name.upper()}")
        print("-" * 40)
        
        master_list = []

        # 1. Get WILD animals
        for taxon_id, limit in QUOTAS.items():
            class_name = CLASS_NAMES[taxon_id]
            print(f"  Fetching {class_name}...")
            
            wild_animals = get_wild_by_class(place_id, taxon_id, limit)
            
            for animal in wild_animals:
                animal['category'] = 'Wild'
                animal['yt_search'] = f"{animal['common']} sound vocalization"
                master_list.append(animal)
            time.sleep(0.5)

        # 2. Get DOMESTIC animals
        print(f"  Fetching Domestic...")
        domestic_animals = get_domestic(place_id)
        for animal in domestic_animals:
            animal['category'] = 'Domestic'
            master_list.append(animal)

        # Sort the list
        class_order = {"Aves": 0, "Amphibia": 1, "Reptilia": 2, "Mammalia": 3, "Domestic": 4}
        master_list.sort(key=lambda x: class_order.get(x['class'], 5))

        print(f"\n  Total Target: {len(master_list)} animals\n")

        # 3. DOWNLOAD
        for idx, item in enumerate(master_list):
            com_name = item['common']
            animal_class = item['class']
            animal_category = item['category']
            yt_search = item.get('yt_search', f"{com_name} sound")
            
            safe_folder_name = com_name.replace(" ", "_")
            save_folder = OUTPUT_DIR / continent_name / animal_category / animal_class / safe_folder_name
            save_folder.mkdir(parents=True, exist_ok=True)
            
            icon = "🏠" if animal_category == "Domestic" else "🦁"
            
            print(f"  {icon} [{idx+1}/{len(master_list)}] {com_name} ({animal_class})")
            print(f"      🔍 Searching: \"{yt_search}\"", end=" ... ")
            
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(download_youtube_audio, com_name, yt_search, save_folder, MAX_FILES)
                    count = future.result(timeout=300)
            except:
                count = 0
            
            if count == 0:
                print(f"\n      ⚠️ Failed. Trying backup...", end=" ... ")
                
                if animal_class == "Aves": backup_search = "Wild bird sound vocalization"
                elif animal_class == "Amphibia": backup_search = "Wild frog sound vocalization"
                elif animal_class == "Reptilia": backup_search = "Wild reptile sound vocalization"
                elif animal_category == "Domestic": backup_search = f"{com_name} sound"
                else: backup_search = "Wild mammal sound vocalization"
                
                try:
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(download_youtube_audio, com_name, backup_search, save_folder, MAX_FILES)
                        count = future.result(timeout=300)
                except:
                    count = 0
            
            if count > 0:
                print(f"\n      ✅ SUCCESS: {count} files.")
                total_downloaded += count
            else:
                print(f"\n      ❌ FAILED.")
                    
            time.sleep(random.uniform(5, 10))

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Total files downloaded: {total_downloaded}")
    print("=" * 60)

if __name__ == "__main__":
    main()