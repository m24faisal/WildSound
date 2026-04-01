# build_youtube_continental_database.py
"""
COMPLETE YOUTUBE DATABASE BUILDER
- Wild Animals: Searches "Animal Name sound vocalization"
- Domestic Animals: Searches specific noise ("Dog barking sound")
"""

import requests
import time
import random
import concurrent.futures
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

# Domestic animals still need specific verbs to avoid videos of sleeping animals
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

MAX_WILD = 20
MAX_DOMESTIC = 10
MAX_YOUTUBE_FILES = 5 

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

    for sci_name, search_term in list(DOMESTIC_TAXA.items())[:MAX_DOMESTIC]:
        com_name = search_term.split()[0] 
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
# STEP 2: YOUTUBE DOWNLOADER
# ==========================================
def download_youtube_audio(animal_name, search_query, save_folder, max_files):
    """Searches 100 videos, downloads max 5, with a 300-second kill switch"""
    
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
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 10 * 1024 * 1024, 
        'ignoreerrors': True, 
        'socket_timeout': 20, 
    }
    
    def run_download():
        with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
            ydl.download([search_query])

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_download)
            future.result(timeout=300)
    except concurrent.futures.TimeoutError:
        pass
    except Exception:
        pass

    for part_file in save_folder.glob("*.part"):
        try: part_file.unlink()
        except: pass

    files_after = len(list(save_folder.glob("*.mp3")))
    return files_after - files_before

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("=" * 60)
    print("SOUND & VOCALIZATION YOUTUBE BUILDER")
    print("=" * 60)

    total_downloaded = 0
    
    for continent_name, place_id in CONTINENTS.items():
        print(f"\n🌍 {continent_name.upper()}")
        print("-" * 40)
        
        species_list = get_exact_species_list(place_id)
        if not species_list: continue
            
        wild_count = sum(1 for s in species_list if s['category'] == 'Wild')
        dom_count = sum(1 for s in species_list if s['category'] == 'Domestic')
        print(f"  Targeting: {wild_count} Wild | {dom_count} Domestic\n")

        for idx, species in enumerate(species_list):
            com_name = species['common']
            animal_class = species['class']
            animal_category = species['category']
            
            save_folder = OUTPUT_DIR / continent_name / animal_category / animal_class / com_name
            save_folder.mkdir(parents=True, exist_ok=True)
            
            icon = "🏠" if animal_category == "Domestic" else "🦁"
            
            # SEARCH LOGIC
            if animal_category == "Domestic":
                # Use the exact specific phrase from our dictionary
                yt_search = DOMESTIC_TAXA.get(species['scientific'], com_name)
            else:
                # WILD ANIMALS: Uses your exact preferred keywords
                yt_search = f"{com_name} sound vocalization"

            print(f"  {icon} [{idx+1}/{len(species_list)}] {com_name}")
            print(f"      🔍 Searching: \"{yt_search}\"", end=" ... ")
            
            count = download_youtube_audio(com_name, yt_search, save_folder, MAX_YOUTUBE_FILES)
            
            # BACKUP SEARCH LOGIC (Only triggers if simple search fails)
            if count == 0:
                print(f"\n      ⚠️ Specific search failed. Trying backup...", end=" ... ")
                
                if animal_class == "Aves":
                    backup_search = "Wild bird sound vocalization"
                elif animal_class == "Amphibia":
                    backup_search = "Wild frog sound vocalization"
                elif animal_class == "Reptilia":
                    backup_search = "Wild reptile sound vocalization"
                else:
                    backup_search = "Wild mammal sound vocalization"
                
                count = download_youtube_audio(com_name, backup_search, save_folder, MAX_YOUTUBE_FILES)
            
            if count > 0:
                print(f"\n      ✅ SUCCESS: Saved {count} files.")
                total_downloaded += count
            else:
                print(f"\n      ❌ FAILED: Could not find any audio.")
                    
            human_delay = random.uniform(3, 8) 
            time.sleep(human_delay)

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Downloaded {total_downloaded} cleanly named files.")
    print("=" * 60)

if __name__ == "__main__":
    main()