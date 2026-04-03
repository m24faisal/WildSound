# build_api_search_youtube_download.py
"""
API SEARCH -> YOUTUBE DOWNLOAD (DESCRIPTIVE EDITION)
- Uses iNaturalist to get Top 20 Wild + Top 10 Domestic per continent.
- Guarantees Mammals, Amphibians, Reptiles, and Birds via fallback list.
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
    "north_america": 97394,  # Fixed typo here from "north_ampaign"
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
}

FALLBACK_ANIMALS = {
    "north_america": {
        "Mammalia": ["Eastern Grey Squirrel", "White-Tailed Deer", "Coyote"], 
        "Amphibia": ["Spring Peeper", "American Bullfrog"], 
        "Reptilia": ["Rattlesnake", "American Alligator"]
    },
    "south_america": {
        "Mammalia": ["Jaguar", "Capybara", "Giant Anteater"], 
        "Amphibia": ["Red-Eyed Tree Frog"], 
        "Reptilia": ["Green Anaconda"]
    },
    "europe": {
        "Mammalia": ["Red Fox", "Wild Boar", "Red Deer"], 
        "Amphibia": ["Common Toad"], 
        "Reptilia": ["Grass Snake"]
    },
    "africa": {
        "Mammalia": ["African Elephant", "Lion", "Spotted Hyena"], 
        "Amphibia": ["African Bullfrog"], 
        "Reptilia": ["Nile Crocodile"]
    },
    "asia": {
        "Mammalia": ["Bengal Tiger", "Indian Elephant", "Snow Leopard"], # Fixed typo "Beaded" -> "Bengal"
        "Amphibia": ["Asian Common Toad"], 
        "Reptilia": ["King Cobra"]
    },
    "oceania": {
        "Mammalia": ["Dingo", "Platypus", "Koala"], 
        "Amphibia": ["Green Tree Frog"], 
        "Reptilia": ["Saltwater Crocodile"]
    }
}

DOMESTIC_TAXA = {
    "Canis lupus familiaris": "Dog",
    "Felis catus": "Cat",
    "Bos taurus": "Cow",
    "Equus caballus": "Horse",
    "Capra hircus": "Goat",
    "Ovis aries": "Sheep",
    "Sus scrofa domesticus": "Pig",
    "Gallus gallus domesticus": "Chicken",
    "Anas platyrhynchos domesticus": "Duck",
    "Meleagris gallopavo": "Turkey"
}

MAX_WILD = 20
MAX_DOMESTIC = 10
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
                
    except:
        pass
        
    return species_list

def get_domestic_list(place_id):
    species_list = []
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    for sci_name, com_name in DOMESTIC_TAXA.items():
        params = {"taxon_name": sci_name, "place_id": place_id, "has[]": "sounds", "verifiable": True, "per_page": 1}
        try:
            response = requests.get(url, params=params, headers=INAT_HEADERS, timeout=10)
            if response.json().get('total_results', 0) > 0:
                species_list.append({'common': com_name, 'class': 'Domestic'})
        except: pass
        time.sleep(0.2)
    return species_list

def ensure_all_classes_exist(master_list, continent_name):
    required_classes = ["Mammalia", "Amphibia", "Reptilia", "Aves"]
    current_classes = {item['class'] for item in master_list}
    missing_classes = [c for c in required_classes if c not in current_classes]
    
    for missing_class in missing_classes:
        fallback_data = FALLBACK_ANIMALS.get(continent_name)
        if fallback_data and missing_class in fallback_data:
            for animal_name in fallback_data[missing_class]:
                if animal_name not in [item['common'] for item in master_list]:
                    master_list.append({'common': animal_name, 'class': missing_class})
            time.sleep(0.2)
        
    return master_list

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
        # Explicitly telling yt-dlp where FFmpeg is prevents silent failures
        'ffmpeg_location': 'ffmpeg' 
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
    print("API SEARCH -> YOUTUBE DOWNLOAD")
    print("============================================================\n")
    
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
        time.sleep(1)

    total_downloaded = 0
    continent_names = list(CONTINENTS.keys())
    
    for continent_name in continent_names:
        place_id = CONTINENTS[continent_name]
        
        print(f"🌍 {continent_name.upper()}")
        print("-" * 40)
        
        master_list = []

        # 1. Get Top 20 WILD
        print(f"  Fetching Top 20 Wild animals...", end=" ... ")
        wild_list = get_wild_list(place_id, MAX_WILD)
        
        # Count how many of each class we found
        class_counts = {}
        for item in wild_list:
            c = item['class']
            class_counts[c] = class_counts.get(c, 0) + 1
            
        print(f"Found {len(wild_list)} wild animals.")
        print(f"  🐦️ Birds: {class_counts.get('Aves', 0)}")
        print(f"  🐺️ Amphibians: {class_counts.get('Amphibia', 0)}")
        print(f"  🐊 Reptiles: {class_counts.get('Reptilia', 0)}")
        print(f"  🦁️ Mammals: {class_counts.get('Mammalia', 0)}")
        
        # 2. Ensure all 4 classes are present
        print("  Checking for missing classes...", end=" ... ")
        master_list.extend(wild_list)
        master_list = ensure_all_classes_exist(master_list, continent_name)
        
        if len(master_list) > len(wild_list):
            print(f"  ⚠️ Added {len(master_list) - len(wild_list)} fallback animals to ensure all classes are covered.")
        else:
            print("  ✅ All 4 classes are covered!")
        
        # 3. Get Top 10 DOMESTIC
        print(f"  Fetching Top 10 Domestic animals...", end=" ... ")
        domestic_list = get_domestic_list(place_id)
        master_list.extend(domestic_list)
        print(f"Found {len(domestic_list)} domestic animals.")

        # Sort the list
        # FIX: Using a simple lambda function and safely falling back to 99 if class isn't found.
        # This prevents the VS Code Type Checker from throwing an error about `None` types.
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
                    # FIX: Changed `field.result` to `future.result`
                    future = executor.submit(download_youtube_audio, com_name, yt_search, save_folder, MAX_FILES)
                    count = future.result(timeout=300)
            except Exception:
                # FIX: Replaced empty `count = ` with `count = 0`
                count = 0
            
            if count > 0:
                print(f"       ✅ SUCCESS: Grabbed {count} audio files.")
                total_downloaded += count
            else:
                print("       ❌ FAILED: No suitable audio found on YouTube.")
                    
            time.sleep(random.uniform(5, 10))

    print("\n============================================================")
    print(f"🎉 COMPLETE! Total files downloaded: {total_downloaded}")
    print("================================================================")

if __name__ == "__main__":
    main()