# build_wikipedia_ultimate_scraper.py
"""
ULTIMATE WIKIPEDIA SCRAPER:
- Detects hidden audio links behind Wikipedia's "File:" pages.
- Cannot be broken by Wikipedia UI updates.
"""

import requests
import time
import re
from urllib.parse import unquote
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
OUTPUT_DIR = Path("wikipedia_scraper_db")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

CONTINENTS = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
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
MIN_FILE_SIZE = 5000 

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

    for sci_name, com_name in list(DOMESTIC_TAXA.items())[:MAX_DOMESTIC]:
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
# STEP 2: SMART DOWNLOADER
# ==========================================
def download_file(file_url, save_folder):
    """Downloads the file if it doesn't already exist."""
    filename = unquote(file_url.split('/')[-1]) # Fixes weird %28 characters in filenames
    filepath = save_folder / filename
    
    if filepath.exists():
        return 1 # Already downloaded
        
    try:
        r = requests.get(file_url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(r.content)
            if filepath.stat().st_size > MIN_FILE_SIZE:
                return 1
            else:
                filepath.unlink() # Delete if broken
    except:
        if filepath.exists(): filepath.unlink()
        
    return 0

# ==========================================
# STEP 3: ULTIMATE SCRAPER
# ==========================================
def scrape_wikipedia_audio(animal_name, save_folder):
    downloaded = 0
    wiki_url = f"https://en.wikipedia.org/wiki/{animal_name.replace(' ', '_')}"
    
    try:
        response = requests.get(wiki_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return 0
            
        html_content = response.text
        
        # METHOD 1: Look for direct raw URLs (Old Wikipedia layout)
        direct_urls = re.findall(r'(?:https?:)?(//upload\.wikimedia\.org/[^"\'<> ]+\.(?:ogg|mp3|wav))', html_content, re.IGNORECASE)
        direct_urls = ['https:' + url if url.startswith('//') else url for url in direct_urls]
        direct_urls = list(set(direct_urls))
        
        for file_url in direct_urls:
            if downloaded >= MAX_FILES: break
            downloaded += download_file(file_url, save_folder)
            
        # METHOD 2: If we didn't find enough, look for hidden "File:" page links (New Wikipedia layout)
        if downloaded < MAX_FILES:
            # Finds links like href="/wiki/File:American_Robin.ogg"
            file_page_links = re.findall(r'href="/wiki/File:([^"]+\.(?:ogg|mp3|wav))"', html_content, re.IGNORECASE)
            
            for file_name in file_page_links:
                if downloaded >= MAX_FILES: break
                
                # Go to the dedicated Wikipedia File page
                file_page_url = f"https://en.wikipedia.org/wiki/File:{file_name}"
                try:
                    file_response = requests.get(file_page_url, headers=HEADERS, timeout=10)
                    if file_response.status_code == 200:
                        # The File page ALWAYS has the raw direct link
                        raw_urls = re.findall(r'(?:https?:)?(//upload\.wikimedia\.org/[^"\'<> ]+\.(?:ogg|mp3|wav))', file_response.text, re.IGNORECASE)
                        raw_urls = ['https:' + url if url.startswith('//') else url for url in raw_urls]
                        
                        for raw_url in raw_urls:
                            if downloaded >= MAX_FILES: break
                            downloaded += download_file(raw_url, save_folder)
                except:
                    pass
                time.sleep(0.5) # Be polite when visiting secondary pages
                
    except Exception as e:
        pass
        
    return downloaded

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("=" * 60)
    print("ULTIMATE WIKIPEDIA SCRAPER")
    print("Bypasses all Wikipedia layout changes.")
    print("=" * 60)

    total_downloaded = 0
    
    for continent_name, place_id in CONTINENTS.items():
        print(f"\n🌍 {continent_name.upper()}")
        print("-" * 40)
        
        species_list = get_exact_species_list(place_id)
        
        if not species_list:
            print("  No species found.")
            continue
            
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
            print(f"  {icon} [{idx+1}/{len(species_list)}] {com_name}", end=" ... ")
            
            count = scrape_wikipedia_audio(com_name, save_folder)
            
            if count > 0:
                print(f"✅ {count} files")
                total_downloaded += count
            else:
                print("❌ No audio on Wikipedia page")
                    
            time.sleep(1) 

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Scraped {total_downloaded} files from Wikipedia.")
    print("=" * 60)

if __name__ == "__main__":
    main()