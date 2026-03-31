# build_wikipedia_scraper_fixed.py
"""
FIXED WIKIPEDIA SCRAPER:
- Disguises as a real Chrome browser to force Wikipedia to send the full page (including Info-boxes).
- Upgraded Regex to catch all URL formats.
"""

import requests
import time
import re
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
OUTPUT_DIR = Path("wikipedia_scraper_db")

# THE FIX: A perfect disguise of a real Chrome browser.
# This forces Wikipedia to send the complete HTML, including the Info-box!
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
# STEP 2: SCRAPE WIKIPEDIA ARTICLE (FULL PAGE)
# ==========================================
def scrape_wikipedia_audio(animal_name, save_folder):
    downloaded = 0
    
    wiki_url = f"https://en.wikipedia.org/wiki/{animal_name.replace(' ', '_')}"
    
    try:
        # Wikipedia will now think we are a real user and send the Info-box!
        response = requests.get(wiki_url, headers=HEADERS, timeout=15)
        
        if response.status_code != 200:
            return 0
            
        html_content = response.text
        
        # UPGRADED REGEX: 
        # 1. Looks for //upload.wikimedia...
        # 2. [^"\'<>]+ allows it to grab hyphens, underscores, and URL encodings like %28
        # 3. re.DOTALL allows it to grab URLs even if Wikipedia split them across two lines in the HTML
        raw_urls = re.findall(r'(?:https?:)?(//upload\.wikimedia\.org/[^"\'<>]+\.(?:ogg|mp3|wav))', html_content, re.IGNORECASE | re.DOTALL)
        
        # Clean up any accidental newlines grabbed by the DOTALL flag
        raw_urls = [url.replace('\n', '').replace('\r', '') for url in raw_urls]
        
        # Clean up the URLs by adding "https:" to the front if it's missing
        ogg_urls = []
        for url in raw_urls:
            if url.startswith('//'):
                ogg_urls.append('https:' + url)
            else:
                ogg_urls.append(url)
                
        # Remove duplicates
        ogg_urls = list(set(ogg_urls))
        
        for file_url in ogg_urls:
            # Create safe filename (handles the %28 encoded brackets safely)
            filename = file_url.split('/')[-1]
            filepath = save_folder / filename
            
            if filepath.exists():
                downloaded += 1
                continue
                
            try:
                r = requests.get(file_url, headers=HEADERS, timeout=30)
                if r.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(r.content)
                        
                    if filepath.stat().st_size > MIN_FILE_SIZE:
                        downloaded += 1
                    else:
                        filepath.unlink() 
                time.sleep(0.5)
            except:
                if filepath.exists(): filepath.unlink()
                
    except Exception as e:
        pass
        
    return downloaded

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("=" * 60)
    print("FULL PAGE WIKIPEDIA SCRAPER")
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
                    
            time.sleep(1) # Slightly longer pause to be a polite "human"

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Scraped {total_downloaded} files from Wikipedia.")
    print("=" * 60)

if __name__ == "__main__":
    main()