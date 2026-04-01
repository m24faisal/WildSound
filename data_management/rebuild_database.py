# build_youtube_continental_database.py
"""
COMPLETE YOUTUBE DATABASE BUILDER
- Searches Top 100 YouTube videos to bypass massive amounts of dead links.
- Hard stops after 5 successful downloads per animal.
- Hard 300-second (5 minute) timeout to prevent freezing on slow connections.
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

DOMESTIC_TAXA = {
    "Canis lupus familiaris": "Dog barking",
    "Felis catus": "Cat meowing",
    "Bos taurus": "Cow mooing",
    "Equus caballus": "Horse neighing",
    "Capra hircus": "Goat bleating",
    "Ovis aries": "Sheep baaing",
    "Sus scrofa domesticus": "Pig oinking",
    "Gallus gallus domesticus": "Chicken clucking",
    "Anas platyrhynchos domesticus": "Duck quacking",
    "Meleagris gallopavo": "Turkey gobbling"
}

MAX_WILD = 20
MAX_DOMESTIC = 10
MAX_YOUTUBE_FILES = 5 # STRICT LIMIT: Will only save 5 files per animal

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
# STEP 2: YOUTUBE DOWNLOADER (DEEP SEARCH + LIMIT)
# ==========================================
def download_youtube_audio(animal_name, search_query, save_folder, max_files):
    """Searches 100 videos, downloads max 5, with a 300-second kill switch"""
    
    # PRE-CLEAN: Delete any leftover .part files from previous crashed runs
    for part_file in save_folder.glob("*.part"):
        try:
            part_file.unlink()
        except:
            pass

    # Count existing files
    files_before = len(list(save_folder.glob("*.mp3")))

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
        'outtmpl': str(save_folder / f"{animal_name.replace(' ', '_')}_%(autonumber)d.%(ext)s"),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'default_search': 'ytsearch100', # SEARCH DEEP: Look at the top 100 YouTube results
        'max_downloads': max_files,       # HARD LIMIT: Stop entirely after 5 successful downloads
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
            # UPDATED: 300-second (5 minute) hard kill switch
            future.result(timeout=300)
            
    except concurrent.futures.TimeoutError:
        pass
    except Exception:
        pass

    # POST-CLEAN: Delete any leftover .part files
    for part_file in save_folder.glob("*.part"):
        try:
            part_file.unlink()
        except:
            pass

    # Count files now to see what actually survived
    files_after = len(list(save_folder.glob("*.mp3")))
    actual_downloads = files_after - files_before

    return actual_downloads

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("=" * 60)
    print("SMART KEYWORD YOUTUBE BUILDER (DEEP SEARCH)")
    print("Searching Top 100 videos. Saving max 5 per animal.")
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
            
            if animal_category == "Domestic":
                search_term = DOMESTIC_TAXA.get(species['scientific'], com_name)
                yt_search = f"{search_term} clean sound effect"
            elif animal_class == "Aves":
                yt_search = f"{com_name} bird call song clean sound effect"
            elif animal_class == "Amphibia":
                yt_search = f"{com_name} frog toad call croaking clean sound effect"
            elif animal_class == "Reptilia":
                yt_search = f"{com_name} reptile hiss sound effect clean"
            else: 
                yt_search = f"{com_name} wild animal sound effect call clean"

            print(f"  {icon} [{idx+1}/{len(species_list)}] {com_name}")
            print(f"      🔍 Scanning top 100 YouTube videos...", end=" ... ")
            
            count = download_youtube_audio(com_name, yt_search, save_folder, MAX_YOUTUBE_FILES)
            
            if count > 0:
                print(f"\n      ✅ SUCCESS: Saved {count} files.")
                total_downloaded += count
            else:
                print(f"\n      ❌ FAILED: All 100 videos were dead, blocked, or timed out.")
                    
            # Random delay to prevent YouTube IP bans
            human_delay = random.uniform(5, 10) 
            time.sleep(human_delay)

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Downloaded {total_downloaded} cleanly named files.")
    print("=" * 60)

if __name__ == "__main__":
    main()