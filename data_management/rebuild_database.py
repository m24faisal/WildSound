# build_api_search_youtube_download.py
"""
ULTRA-STREAMLINED YOUTUBE DOWNLOADER
- Searches Top 10 YouTube results per animal (Fast, safe, un-crashable).
- Top 10 Wild + Top 10 Domestic per continent.
"""

import requests
import time
import random
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

CONTINENTS = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
}

FALLBACK_ANIMALS = {
    "north_america": {
        "Mammalia": ["Eastern Grey Squirrel", "White-Tailed Deer", "Coyote"], 
        "Aves": ["American Robin", "Bald Eagle"],
        "Amphibia": ["Spring Peeper", "American Bullfrog"], 
        "Reptilia": ["Rattlesnake", "American Alligator"]
    },
    "south_america": {
        "Mammalia": ["Jaguar", "Capybara", "Giant Anteater"], 
        "Aves": ["Toucan", "Harpy Eagle"],
        "Amphibia": ["Red-Eyed Tree Frog", "Poison Dart Frog"], 
        "Reptilia": ["Green Anaconda"]
    },
    "europe": {
        "Mammalia": ["Red Fox", "Wild Boar", "Red Deer"], 
        "Aves": ["European Robin", "Common Nightingale"],
        "Amphibia": ["Common Toad"], 
        "Reptilia": ["Grass Snake"]
    },
    "africa": {
        "Mammalia": ["African Elephant", "Lion", "Spotted Hyena"], 
        "Aves": ["African Grey Parrot", "Lilac-Breasted Roller"],
        "Amphibia": ["African Bullfrog"], 
        "Reptilia": ["Nile Crocodile"]
    },
    "asia": {
        "Mammalia": ["Bengal Tiger", "Indian Elephant", "Snow Leopard"], 
        "Aves": ["Asian Koel", "Peacock"],
        "Amphibia": ["Asian Common Toad"], 
        "Reptilia": ["King Cobra"]
    },
    "oceania": {
        "Mammalia": ["Dingo", "Platypus", "Koala"], 
        "Aves": ["Kookaburra", "Superb Lyrebird"],
        "Amphibia": ["Green Tree Frog"], 
        "Reptilia": ["Saltwater Crocodile"]
    }
}

TOP_10_DOMESTIC = [
    "Dog", "Cat", "Cow", "Horse", "Goat", 
    "Sheep", "Pig", "Chicken", "Duck", "Turkey"
]

MAX_WILD = 10 
MAX_FILES = 3 

# ==========================================
# STEP 1: INATURALIST
# ==========================================
def get_wild_list(place_id, limit):
    species_list = []
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    params = {
        "place_id": place_id, "has[]": "sounds", "verifiable": True,
        "quality_grade": "research", "per_page": limit, "order_by": "count", "order": "desc"
    }
    try:
        response = requests.get(url, params=params, headers=INAT_HEADERS, timeout=15)
        data = response.json()
        results = data.get('results', [])
        for result in results:
            taxon = result.get('taxon', {})
            sci_name = taxon.get('name', '')
            com_name = taxon.get('preferred_common_name', sci_name).title()
            if sci_name and com_name and com_name != 'Unknown':
                animal_class = taxon.get('iconic_taxon_name', 'Unknown')
                species_list.append({'common': com_name, 'class': animal_class})
    except Exception as e:
        print(f"\n  [Warning] API Error: {e}")
    return species_list

def ensure_all_classes_exist(master_list, continent_name):
    required_classes = ["Mammalia", "Aves", "Reptilia", "Amphibia"]
    current_classes = {item['class'] for item in master_list}
    added_count = 0
    for missing_class in required_classes:
        if missing_class not in current_classes:
            fallback_data = FALLBACK_ANIMALS.get(continent_name)
            if fallback_data and missing_class in fallback_data:
                for animal_name in fallback_data[missing_class]:
                    if animal_name not in [item['common'] for item in master_list]:
                        master_list.append({'common': animal_name, 'class': missing_class})
                        current_classes.add(missing_class)
                        added_count += 1
                        break 
    return master_list, added_count

# ==========================================
# STEP 2: YOUTUBE (Simple & Safe)
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
        
        # CHANGED: Top 10 YouTube results instead of 100
        'default_search': 'ytsearch10', 
        
        'max_downloads': max_files,       
        'noplaylist': True, 'quiet': True, 'no_warnings': True,
        'max_filesize': 10 * 1024 * 1024, 'ignoreerrors': True, 
        'socket_timeout': 15, 
        'ffmpeg_location': str(Path(__file__).parent / 'ffmpeg.exe') 
    }
    
    try:
        with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
            ydl.download([search_query])
    except Exception:
        pass
    finally:
        for part_file in save_folder.glob("*.part"):
            try: part_file.unlink()
            except: pass

    return len(list(save_folder.glob("*.mp3"))) - files_before

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("============================================================")
    print("ULTRA-STREAMLINED YOUTUBE DOWNLOADER (TOP 10 SEARCH)")
    print("============================================================\n")
    
    ffmpeg_path = Path(__file__).parent / 'ffmpeg.exe'
    if not ffmpeg_path.exists():
        print("❌ CRITICAL ERROR: ffmpeg.exe NOT FOUND in the script directory!")
        print(f"   Expected it here: {ffmpeg_path}")
        return

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
        time.sleep(1)

    total_downloaded = 0
    continent_names = list(CONTINENTS.keys())
    
    try:
        for continent_name in continent_names:
            place_id = CONTINENTS[continent_name]
            
            print(f"🌍 {continent_name.upper()}")
            print("-" * 55)
            
            master_list = []

            print(f"  Fetching Top 10 Wild animals...", end=" ... ")
            wild_list = get_wild_list(place_id, MAX_WILD)
            master_list.extend(wild_list)
            print(f"Found {len(wild_list)} wild animals.")
            
            print("  Checking for missing wild classes...", end=" ... ")
            master_list, added_fallbacks = ensure_all_classes_exist(master_list, continent_name)
            
            if added_fallbacks > 0:
                print(f"  ⚠️ Added {added_fallbacks} fallback animal(s).")
            else:
                print("  ✅ All classes covered!")
            
            print(f"  Injecting Top 10 Domestic animals...", end=" ... ")
            for domestic_animal in TOP_10_DOMESTIC:
                master_list.append({'common': domestic_animal, 'class': 'Domestic'})
            print(f"Added 10.")

            class_order = {
                "Aves": 0, "Amphibia": 1, "Reptilia": 2, "Mammalia": 3, "Domestic": 4, "Unknown": 5
            }
            master_list.sort(key=lambda x: class_order.get(x.get('class', 'Unknown'), 99))

            print(f"\n  FINAL TOTAL: {len(master_list)} animals for {continent_name.upper()}\n")

            for idx, item in enumerate(master_list):
                com_name = item['common']
                animal_class = item['class']
                
                if animal_class == "Domestic":
                    yt_search = f"{com_name} animal sounds noises"
                else:
                    yt_search = f"{com_name} sound vocalization"
                
                safe_folder_name = com_name.replace(" ", "_")
                save_folder = OUTPUT_DIR / continent_name / animal_class / safe_folder_name
                save_folder.mkdir(parents=True, exist_ok=True)
                
                print(f"    [{idx+1}/{len(master_list)}] {com_name}", end=" ... ")
                
                count = download_youtube_audio(com_name, yt_search, save_folder, MAX_FILES)
                
                if count > 0:
                    print(f"✅ SUCCESS: Grabbed {count} audio files.")
                    total_downloaded += count
                else:
                    print("❌ FAILED: No suitable audio found.")
                
                time.sleep(random.uniform(5, 10))

            print(f"\n  ✅ Finished processing {continent_name.upper()}\n")

    except KeyboardInterrupt:
        print("\n\n🛑 SCRIPT CANCELLED BY USER.")

    print("\n============================================================")
    print(f"🎉 DONE! Total files downloaded: {total_downloaded}")
    print("============================================================")

if __name__ == "__main__":
    main()