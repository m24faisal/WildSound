# build_strict_quotas_clean_slate.py
"""
CLEAN SLATE STRICT QUOTA DATABASE BUILDER
- Deletes old database folder automatically.
- No skip logic. Downloads everything fresh.
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
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    params = {
        "place_id": place_id, 
        "taxon_id": taxon_id,      
        "has[]": "sounds", "verifiable": True,
        "quality_grade": "research", 
        "per_page": limit, 
        "order_by": "count", "order": "desc"
    }
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        data = response.json()
        for result in data.get('results', [])[:limit]:
            taxon = result.get('taxon', {})
            sci_name = taxon.get('name', '')
            com_name = taxon.get('preferred_common_name', sci_name).title()
            if sci_name and com_name and com_name != 'Unknown':
                species_list.append({'common': com_name, 'class': CLASS_NAMES[taxon_id]})
    except: pass
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
    # Clean up any crashed downloads
    for part_file in save_folder.glob("*.part"):
        try: part_file.unlink()
        except: pass

    files_before = len(list(save_folder.glob("*.mp3")))

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
        'outtmpl': str(save_folder / f"{animal_name.replace(' ', '_')}_%(autonumber)d.%(ext)s"),
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
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_download)
            future.result(timeout=300)
    except: pass

    # Clean up any crashed downloads post-attempt
    for part_file in save_folder.glob("*.part"):
        try: part_file.unlink()
        except: pass

    return len(list(save_folder.glob("*.mp3"))) - files_before

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("=" * 60)
    print("CLEAN SLATE STRICT QUOTA DATABASE BUILDER")
    print("=" * 60)
    
    # PRE-CLEAN: Delete the old database folder if it exists
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

        # 1. Get exactly 20 WILD animals based on strict class quotas
        for taxon_id, limit in QUOTAS.items():
            class_name = CLASS_NAMES[taxon_id]
            wild_animals = get_wild_by_class(place_id, taxon_id, limit)
            for animal in wild_animals:
                animal['category'] = 'Wild'
                animal['yt_search'] = f"{animal['common']} sound vocalization"
                master_list.append(animal)
            time.sleep(0.5)

        # 2. Get up to 10 DOMESTIC animals
        domestic_animals = get_domestic(place_id)
        for animal in domestic_animals:
            animal['category'] = 'Domestic'
            master_list.append(animal)

        # Sort the list (Birds -> Amphibians -> Reptiles -> Mammals -> Domestic)
        class_order = {"Aves": 0, "Amphibia": 1, "Reptilia": 2, "Mammalia": 3, "Domestic": 4}
        master_list.sort(key=lambda x: class_order.get(x['class'], 5))

        print(f"  Total Target: {len(master_list)} animals\n")

        # 3. DOWNLOAD THEM ALL
        for idx, item in enumerate(master_list):
            com_name = item['common']
            animal_class = item['class']
            animal_category = item['category']
            yt_search = item.get('yt_search', f"{com_name} sound")
            
            save_folder = OUTPUT_DIR / continent_name / animal_category / animal_class / com_name
            save_folder.mkdir(parents=True, exist_ok=True)
            
            icon = "🏠" if animal_category == "Domestic" else "🦁"
            
            print(f"  {icon} [{idx+1}/{len(master_list)}] {com_name} ({animal_class})")
            print(f"      🔍 Searching: \"{yt_search}\"", end=" ... ")
            
            count = download_youtube_audio(com_name, yt_search, save_folder, MAX_FILES)
            
            # BACKUP SEARCH LOGIC 
            if count == 0:
                print(f"\n      ⚠️ Primary search failed. Trying backup...", end=" ... ")
                
                if animal_class == "Aves":
                    backup_search = "Wild bird sound vocalization"
                elif animal_class == "Amphibia":
                    backup_search = "Wild frog sound vocalization"
                elif animal_class == "Reptilia":
                    backup_search = "Wild reptile sound vocalization"
                elif animal_category == "Domestic":
                    backup_search = f"{com_name} sound"
                else: 
                    backup_search = "Wild mammal sound vocalization"
                
                count = download_youtube_audio(com_name, backup_search, save_folder, MAX_FILES)
            
            # Descriptive Result Block
            if count > 0:
                print(f"\n      ✅ SUCCESS: Downloaded {count} new files.")
                total_downloaded += count
            else:
                print(f"\n      ❌ FAILED: No suitable videos found.")
                    
            time.sleep(random.uniform(2, 5))

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Total files downloaded: {total_downloaded}")
    print("=" * 60)

if __name__ == "__main__":
    main()