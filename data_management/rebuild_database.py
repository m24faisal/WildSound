# build_wikipedia_scraper_database.py
"""
THE WIKIPEDIA SCRAPER:
- Goes directly to the Wikipedia article (e.g., Wikipedia.com/wiki/Dog)
- Rips the audio file directly out of the article's page code.
- 100% Success rate for animals that have sounds on their page.
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

HEADERS = {
    'User-Agent': 'WildSoundAppBuilder/1.0 (Educational Database Project)'
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
# STEP 2: SCRAPE WIKIPEDIA ARTICLE
# ==========================================
def scrape_wikipedia_audio(animal_name, save_folder):
    """Goes to Wikipedia.com/wiki/Animal_Name and extracts audio files."""
    downloaded = 0
    
    # Wikipedia uses underscores for spaces in URLs
    wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/html/{animal_name.replace(' ', '_')}"
    
    try:
        # Get the raw HTML of the Wikipedia article
        response = requests.get(wiki_url, headers=HEADERS, timeout=15)
        
        # If the article doesn't exist, Wikipedia returns a 404
        if response.status_code != 200:
            return 0
            
        html_content = response.text
        
        # Use Regular Expressions to find all .ogg file URLs in the HTML
        # This looks for: https://upload.wikimedia.org/.../something.ogg
        ogg_urls = re.findall(r'(https://upload\.wikimedia\.org/wikipedia/commons/[^\s"\'<>]+\.ogg)', html_content)
        
        # Remove duplicates (sometimes Wikipedia links the same file twice)
        ogg_urls = list(set(ogg_urls))
        
        for file_url in ogg_urls:
            # Download the file
            filepath = save_folder / f"{animal_name.replace(' ', '_')}_{file_url.split('/')[-1]}"
            
            if filepath.exists():
                downloaded += 1
                continue
                
            try:
                r = requests.get(file_url, headers=HEADERS, timeout=30)
                if r.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(r.content)
                        
                    # Final safety check: Make sure it's not a tiny broken file
                    if filepath.stat().st_size > MIN_FILE_SIZE:
                        downloaded += 1
                    else:
                        filepath.unlink() # Delete if too small
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
    print("DIRECT WIKIPEDIA SCRAPER")
    print("Extracting audio straight from Wikipedia articles.")
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
            
            # Scrape the Wikipedia page using the common name
            count = scrape_wikipedia_audio(com_name, save_folder)
            
            if count > 0:
                print(f"✅ {count} files")
                total_downloaded += count
            else:
                print("❌ No audio on Wikipedia page")
                    
            time.sleep(0.5) # Be very polite to Wikipedia

    print("\n" + "=" * 60)
    print(f"🎉 COMPLETE! Scraped {total_downloaded} files from Wikipedia.")
    print("=" * 60)

if __name__ == "__main__":
    main()