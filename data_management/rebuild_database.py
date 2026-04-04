# build_api_search_youtube_download.py
"""
API SEARCH -> YOUTUBE DOWNLOAD (DESCRIPTIVE EDITION)
- Gets Top 20 Wild animals per continent via iNaturalist API.
- Appends Top 20 most common Domestic animals globally.
- GUARANTEES Mammals, Birds, Reptiles, and Amphibians are included.
- Uses YouTube to download the actual audio files.
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

CONTINENTS = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
}

# Strictly Mammals, Birds, Reptiles, and Amphibians
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

# Top 20 most common domestic animals globally
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
    # Strictly checking for the 4 requested land-based classes
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
                        break # Only add 1 fallback per missing class
            time.sleep(0.2)
        
    return master_list, added_count

# ==========================================
# STEP 2: YOUTUBE (Get The Audio)
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
        'ffmpeg_location': str(Path(__file__).parent / 'ffmpeg.exe') 
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
    print("============================================================")
    print("API SEARCH -> YOUTUBE DOWNLOAD (WILD + DOMESTIC)")
    print("============================================================\n")
    
    # Verify ffmpeg exists before starting
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
    
    for continent_name in continent_names:
        place_id = CONTINENTS[continent_name]
        
        print(f"🌍 {continent_name.upper()}")
        print("-" * 55)
        
        master_list = []

        # 1. Get Top 20 WILD
        print(f"  Fetching Top 20 Wild animals...", end=" ... ")
        wild_list = get_wild_list(place_id, MAX_WILD)
        master_list.extend(wild_list)
        print(f"Found {len(wild_list)} wild animals.")
        
        # 2. Ensure all 4 classes are present
        print("  Checking for missing classes...", end=" ... ")
        master_list, added_fallbacks = ensure_all_classes_exist(master_list, continent_name)
        
        if added_fallbacks > 0:
            print(f"  ⚠️ Added {added_fallbacks} fallback animal(s) to cover missing classes.")
        else:
            print("  ✅ All classes covered!")
        
        # 3. Inject Top 20 DOMESTIC
        print(f"  Injecting Top 20 Domestic animals...", end=" ... ")
        for domestic_animal in TOP_20_DOMESTIC:
            master_list.append({'common': domestic_animal, 'class': 'Domestic'})
        print(f"Added 20 domestic animals.")

        # Sort the list logically
        class_order = {
            "Aves": 0, "Amphibia": 1, "Reptilia": 2, "Mammalia": 3, "Domestic": 4, "Unknown": 5
        }
        master_list.sort(key=lambda x: class_order.get(x.get('class', 'Unknown'), 99))

        print(f"\n  FINAL TOTAL: {len(master_list)} animals for {continent_name.upper()}\n")

        # 4. DOWNLOAD FROM YOUTUBE
        print("  Downloading from YouTube:")
        for idx, item in enumerate(master_list):
            com_name = item['common']
            animal_class = item['class']
            
            # Tweak search query slightly for domestic vs wild
            if animal_class == "Domestic":
                yt_search = f"{com_name} animal sounds noises"
            else:
                yt_search = f"{com_name} sound vocalization"
            
            safe_folder_name = com_name.replace(" ", "_")
            save_folder = OUTPUT_DIR / continent_name / animal_class / safe_folder_name
            save_folder.mkdir(parents=True, exist_ok=True)
            
            # Descriptive output
            print(f"    [{idx+1}/{len(master_list)}] {com_name}", end=" ... ")
            print(f"       🔍 Query: \"{yt_search}\"", end=" ... ")
            
            count = 0
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(download_youtube_audio, com_name, yt_search, save_folder, MAX_FILES)
                    count = future.result(timeout=300)
            except Exception:
                count = 0
            
            if count > 0:
                print(f"       ✅ SUCCESS: Grabbed {count} audio files.")
                total_downloaded += count
            else:
                print("       ❌ FAILED: No suitable audio found on YouTube.")
                    
            time.sleep(random.uniform(5, 10))

    print("\n============================================================")
    print(f"🎉 COMPLETE! Total files downloaded: {total_downloaded}")
    print("============================================================")

if __name__ == "__main__":
    main()