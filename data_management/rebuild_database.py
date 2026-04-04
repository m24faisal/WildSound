# build_api_search_youtube_download.py
"""
API SEARCH -> YOUTUBE DOWNLOAD (CONCURRENT & FREEZE PROOF)
- Uses multiprocessing to download multiple animals at once.
- Isolates downloads so frozen videos CANNOT crash the main script.
- Built-in throttling inside workers to prevent YouTube IP bans.
"""

import requests
import time
import random
import shutil
import multiprocessing
from pathlib import Path
import warnings
import yt_dlp
from typing import Any, cast, Tuple

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
OUTPUT_DIR = Path("youtube_smart_db")
TIMEOUT_SECONDS = 90
MAX_CONCURRENT_DOWNLOADS = 3 # How many animals to download at the exact same time
MIN_DELAY, MAX_DELAY = 5, 10  # Seconds the worker will wait before searching YouTube

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

TOP_20_DOMESTIC = [
    "Dog", "Cat", "Cow", "Horse", "Goat", "Sheep", "Pig", "Chicken", 
    "Duck", "Turkey", "Donkey", "Rabbit", "Guinea Pig", "Hamster", 
    "Canary", "Pigeon", "Goose", "Alpaca", "Camel", "Bee"
]

MAX_WILD = 20
MAX_FILES = 5 

# ==========================================
# STEP 1: INATURALIST (Get The List)
# ==========================================
def get_wild_list(place_id, limit):
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
            time.sleep(0.2)
        
    return master_list, added_count

# ==========================================
# STEP 2: YOUTUBE (Get The Audio)
# ==========================================
# This function IS the worker. It gets passed to a separate CPU core.
def _download_worker(task_data: Tuple[str, str, str, int, str]) -> Tuple[str, int, bool]:
    animal_name, search_query, save_folder_str, max_files, ffmpeg_loc = task_data
    save_folder = Path(save_folder_str)
    
    # 1. Throttle: Sleep HERE inside the worker process, not the main script!
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    # Clean up old partial downloads
    for part_file in save_folder.glob("*.part"):
        try: part_file.unlink()
        except: pass

    files_before = len(list(save_folder.glob("*.mp3")))
    safe_name = animal_name.replace(" ", "_")
    
    http_headers = {'timeout': str(TIMEOUT_SECONDS)}
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
        'outtmpl': str(save_folder / f"{safe_name}_%(autonumber)d.%(ext)s"),
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',}],
        'default_search': 'ytsearch100', 
        'max_downloads': max_files,       
        'noplaylist': True, 'quiet': True, 'no_warnings': True,
        'max_filesize': 10 * 1024 * 1024, 'ignoreerrors': True, 
        'http_headers': http_headers,
        'ffmpeg_location': ffmpeg_loc
    }
    
    timed_out = False
    
    try:
        with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
            ydl.download([search_query])
    except Exception:
        pass
    finally:
        for part_file in save_folder.glob("*.part"):
            try: part_file.unlink()
            except: pass

    files_after = len(list(save_folder.glob("*.mp3")))
    return animal_name, (files_after - files_before), timed_out


# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    multiprocessing.freeze_support()

    print("============================================================")
    print("API SEARCH -> YOUTUBE DOWNLOAD (CONCURRENT & FREEZE PROOF)")
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
    ffmpeg_loc_str = str(ffmpeg_path)
    continent_names = list(CONTINENTS.keys())
    
    for continent_name in continent_names:
        place_id = CONTINENTS[continent_name]
        
        print(f"🌍 {continent_name.upper()}")
        print("-" * 55)
        
        master_list = []

        print(f"  Fetching Top 20 Wild animals...", end=" ... ")
        wild_list = get_wild_list(place_id, MAX_WILD)
        master_list.extend(wild_list)
        print(f"Found {len(wild_list)} wild animals.")
        
        print("  Checking for missing classes...", end=" ... ")
        master_list, added_fallbacks = ensure_all_classes_exist(master_list, continent_name)
        
        if added_fallbacks > 0:
            print(f"  ⚠️ Added {added_fallbacks} fallback animal(s) to cover missing classes.")
        else:
            print("  ✅ All classes covered!")
        
        print(f"  Injecting Top 20 Domestic animals...", end=" ... ")
        for domestic_animal in TOP_20_DOMESTIC:
            master_list.append({'common': domestic_animal, 'class': 'Domestic'})
        print(f"Added 20 domestic animals.")

        class_order = {
            "Aves": 0, "Amphibia": 1, "Reptilia": 2, "Mammalia": 3, "Domestic": 4, "Unknown": 5
        }
        master_list.sort(key=lambda x: class_order.get(x.get('class', 'Unknown'), 99))

        print(f"\n  FINAL TOTAL: {len(master_list)} animals for {continent_name.upper()}")
        print(f"  🚀 Spawning {MAX_CONCURRENT_DOWNLOADS} concurrent download workers...\n")

        # 1. Prepare the task list for the multiprocessing pool
        task_list = []
        for item in master_list:
            com_name = item['common']
            animal_class = item['class']
            
            if animal_class == "Domestic":
                yt_search = f"{com_name} animal sounds noises"
            else:
                yt_search = f"{com_name} sound vocalization"
            
            safe_folder_name = com_name.replace(" ", "_")
            save_folder = OUTPUT_DIR / continent_name / animal_class / safe_folder_name
            save_folder.mkdir(parents=True, exist_ok=True)
            
            # Package data into a tuple so multiprocessing can safely pass it to the worker
            task_list.append((com_name, yt_search, str(save_folder), MAX_FILES, ffmpeg_loc_str))

        # 2. Fire up the Pool! (No time.sleep on the main thread!)
        # imap_unordered gives us results as fast as they finish, keeping the console highly responsive
        with multiprocessing.Pool(processes=MAX_CONCURRENT_DOWNLOADS) as pool:
            results = pool.imap_unordered(_download_worker, task_list)
            
            for animal_name, count, timed_out in results:
                if count > 0:
                    print(f"       ✅ [{animal_name}]: Grabbed {count} audio files.")
                    total_downloaded += count
                else:
                    status = "⏱️ TIMED OUT!" if timed_out else "❌ FAILED/SKIPPED"
                    print(f"       {status} [{animal_name}]: No suitable audio found.")

        print(f"\n  ✅ Finished processing {continent_name.upper()}\n")

    print("\n============================================================")
    print(f"🎉 COMPLETE! Total files downloaded: {total_downloaded}")
    print("============================================================")

if __name__ == "__main__":
    main()