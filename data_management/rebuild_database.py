# build_multi_api_simple.py
"""
MULTI-API DATABASE BUILDER
- 12 Birds strictly from eBird.
- 8 Other Wild animals from iNaturalist (Naturally includes Mammals, Reptiles, Amphibians).
- 10 Domestic animals from iNaturalist.
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

INAT_HEADERS = {'User-Agent': 'WildSoundAppBuilder/1.0'}

# GET YOUR FREE EBIRD API KEY HERE: https://ebird.org/api/keygen
EBIRD_API_KEY = "t2h32l4vqp58"
EBIRD_HEADERS = {
    'x-ebirdapitoken': EBIRD_API_KEY,
    'User-Agent': 'WildSoundAppBuilder/1.0'
}

CONTINENTS_EBIRD = {
    "north_america": "US", 
    "south_america": "BR", 
    "europe": "GB", 
    "africa": "ZA", 
    "asia": "IN", 
    "oceania": "AU"
}

CONTINENTS_INAT = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
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
# STEP 1: API GETTERS
# ==========================================
def get_birds_ebird(country_code, limit=12):
    species_list = []
    url = f"https://api.ebird.org/v2/data/obs/{country_code}/top100"
    
    try:
        response = requests.get(url, headers=EBIRD_HEADERS, timeout=20)
        if response.status_code == 200:
            data = response.json()
            print(f"         [eBird: {len(data)} species]", end=" ... ")
            
            for obs in data[:limit]:
                com_name = obs.get('comName', '').title()
                if com_name:
                    species_list.append({
                        'common': com_name, 
                        'class': 'Aves', 
                        'yt_search': f"{com_name} sound vocalization"
                    })
    except Exception as e:
        print(f"         [eBird Error]", end=" ... ")
        
    return species_list

def get_wild_inat(place_id, limit=8):
    """Gets top wild animals, naturally includes reptiles/amphibians/mammals"""
    species_list = []
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    
    params = {
        "place_id": place_id, 
        "has[]": "sounds", 
        "verifiable": True,
        "quality_grade": "research", 
        "per_page": limit, 
        "order_by": "count", "order": "desc"
    }
    
    try:
        response = requests.get(url, params=params, headers=INAT_HEADERS, timeout=15)
        data = response.json()
        results = data.get('results', [])
        
        # Filter out birds so we don't duplicate the eBird list
        for result in results:
            taxon = result.get('taxon', {})
            if taxon.get('iconic_taxon_name') == 'Aves':
                continue
                
            sci_name = taxon.get('name', '')
            com_name = taxon.get('preferred_common_name', sci_name).title()
            if sci_name and com_name and com_name != 'Unknown':
                animal_class = taxon.get('iconic_taxon_name', 'Unknown')
                species_list.append({
                    'common': com_name, 
                    'class': animal_class,
                    'yt_search': f"{com_name} sound vocalization"
                })
                
        print(f"         [iNat Wild: {len(species_list)} others]", end=" ... ")
    except Exception as e:
        print(f"         [iNat Error]", end=" ... ")
        
    return species_list

def get_domestic(place_id):
    species_list = []
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    for sci_name, yt_search in DOMESTIC_TAXA.items():
        params = {"taxon_name": sci_name, "place_id": place_id, "has[]": "sounds", "verifiable": True, "per_page": 1}
        try:
            response = requests.get(url, params=params, headers=INAT_HEADERS, timeout=10)
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
    print("MULTI-API DATABASE BUILDER")
    print("=" * 60)
    
    if OUTPUT_DIR.exists():
        print("\n🧹 Deleting old database folder...")
        shutil.rmtree(OUTPUT_DIR)
        time.sleep(1)
        
    if EBIRD_API_KEY == "PASTE_YOUR_EBIRD_API_KEY_HERE":
        print("\n❌ ERROR: You must get a free eBird API key and paste it in the script!")
        print("Go to: https://ebird.org/api/keygen")
        return

    print("Birds -> eBird | Others -> iNaturalist")
    print("Starting fresh from scratch...\n")

    total_downloaded = 0
    continent_names = list(CONTINENTS_EBIRD.keys())
    
    for continent_name in continent_names:
        print(f"🌍 {continent_name.upper()}")
        print("-" * 40)
        
        master_list = []

        # 1. Get BIRDS from eBird
        print(f"  Fetching Aves (eBird)...")
        master_list.extend(get_birds_ebird(CONTINENTS_EBIRD[continent_name], limit=12))
        time.sleep(1)

        # 2. Get OTHER WILD from iNaturalist
        print(f"  Fetching Wild Mammals/Reptiles/Amphibians (iNaturalist)...")
        master_list.extend(get_wild_inat(CONTINENTS_INAT[continent_name], limit=8))
        time.sleep(0.5)

        # 3. Get DOMESTIC from iNaturalist
        print(f"  Fetching Domestic...")
        master_list.extend(get_domestic(CONTINENTS_INAT[continent_name]))

        # Sort the list
        class_order = {"Aves": 0, "Amphibia": 1, "Reptilia": 2, "Mammalia": 3, "Domestic": 4, "Unknown": 5}
        master_list.sort(key=lambda x: class_order.get(x['class'], 5))

        print(f"\n  Total Target: {len(master_list)} animals\n")

        # 4. DOWNLOAD THEM ALL
        for idx, item in enumerate(master_list):
            com_name = item['common']
            animal_class = item['class']
            animal_category = 'Wild' if animal_class != 'Domestic' else 'Domestic'
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