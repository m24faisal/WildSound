# rebuild_top_animals_safe.py
"""
Rebuild animal sounds dataset with:
- Top 20 most common wild animals per continent (with audio)
- Top 10 most common domestic animals per continent (with audio)
- Only downloads uncorrupted audio files
- Safe API handling with retries and rate limiting
"""

import os
import time
import requests
import soundfile as sf
from pathlib import Path
from tqdm import tqdm
import argparse
import json
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuration
RATE_LIMIT_DELAY = 1.5  # seconds between API calls (safe)
DOWNLOAD_DELAY = 0.8    # seconds between downloads
MAX_RETRIES = 5
TIMEOUT = 45
MAX_RECORDINGS_PER_SPECIES = 10
OUTPUT_DIR = "animal_sounds"

# Continents with their iNaturalist place IDs
CONTINENTS = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
}

# Domestic animals to check (expanded list)
DOMESTIC_TAXA = [
    "Canis lupus familiaris",  # Dog
    "Felis catus",            # Cat
    "Bos taurus",             # Cattle
    "Equus caballus",         # Horse
    "Capra hircus",           # Goat
    "Ovis aries",             # Sheep
    "Sus scrofa domesticus",  # Pig
    "Gallus gallus domesticus", # Chicken
    "Anas platyrhynchos domesticus", # Duck
    "Meleagris gallopavo",   # Turkey
    "Lama glama",            # Llama
    "Cavia porcellus",       # Guinea pig
    "Oryctolagus cuniculus", # Rabbit
    "Columba livia domestica", # Pigeon
    "Serinus canaria domestica", # Canary
    "Melopsittacus undulatus", # Budgerigar
    "Anser anser domesticus", # Goose
    "Numida meleagris",      # Guineafowl
    "Camelus dromedarius",   # Camel
    "Bubalus bubalis",       # Water buffalo
]

# Create a session with retry strategy
def create_session():
    """Create requests session with retry strategy"""
    session = requests.Session()
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

session = create_session()

def make_api_request(url, params=None, max_attempts=MAX_RETRIES):
    """Make API request with exponential backoff"""
    for attempt in range(max_attempts):
        try:
            # Add delay before request to respect rate limits
            if attempt == 0:
                time.sleep(RATE_LIMIT_DELAY)
            else:
                wait_time = (2 ** attempt) * 2
                print(f"    Retry {attempt}/{max_attempts} - waiting {wait_time}s")
                time.sleep(wait_time)
            
            response = session.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            print(f"    Timeout (attempt {attempt + 1}/{max_attempts})")
            if attempt == max_attempts - 1:
                return None
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get('Retry-After', 30))
                print(f"    Rate limited - waiting {retry_after}s")
                time.sleep(retry_after)
            else:
                print(f"    HTTP error: {e}")
                if attempt == max_attempts - 1:
                    return None
            time.sleep(RATE_LIMIT_DELAY * (attempt + 1))
            
        except Exception as e:
            print(f"    Request failed: {e}")
            if attempt == max_attempts - 1:
                return None
            time.sleep(RATE_LIMIT_DELAY * (attempt + 1))
    
    return None

def get_top_wild_species(place_id, limit=20):
    """Get top N most observed wild species with audio in a continent"""
    
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    params = {
        "place_id": place_id,
        "has[]": "sounds",
        "verifiable": True,
        "quality_grade": "research",
        "per_page": limit,
        "order_by": "count",
        "order": "desc"
    }
    
    print(f"    Requesting top {limit} species...")
    data = make_api_request(url, params)
    
    if not data or 'results' not in data:
        print(f"    ⚠️ No data returned")
        return []
    
    species_list = []
    for result in data.get('results', []):
        taxon = result.get('taxon', {})
        species_list.append({
            'id': taxon.get('id'),
            'name': taxon.get('name'),
            'common_name': taxon.get('preferred_common_name', taxon.get('name')),
            'observation_count': result.get('count', 0)
        })
    
    return species_list

def get_top_domestic_species(place_id, limit=10):
    """Get top N most observed domestic species with audio in a continent"""
    
    domestic_counts = []
    
    for idx, taxon_name in enumerate(DOMESTIC_TAXA):
        print(f"    Checking {idx+1}/{len(DOMESTIC_TAXA)}: {taxon_name.split()[-1]}...", end="")
        
        url = "https://api.inaturalist.org/v1/observations"
        params = {
            "taxon_name": taxon_name,
            "place_id": place_id,
            "has[]": "sounds",
            "verifiable": True,
            "quality_grade": "research",
            "per_page": 1
        }
        
        data = make_api_request(url, params)
        count = data.get('total_results', 0) if data else 0
        
        if count > 0:
            common_name = taxon_name.replace("_", " ").replace("domesticus", "domestic").title()
            domestic_counts.append({
                'name': taxon_name,
                'common_name': common_name,
                'observation_count': count
            })
            print(f" ✅ {count} recordings")
        else:
            print(f" ❌ none")
    
    # Sort by count and return top N
    domestic_counts.sort(key=lambda x: x['observation_count'], reverse=True)
    return domestic_counts[:limit]

def download_species_audio(species_name, output_path, max_recordings=10):
    """Download audio for a species and verify it's not corrupted"""
    
    successful = 0
    attempted = 0
    
    try:
        observations = get_observations_safe(
            taxon_name=species_name,
            has_sounds=True,
            quality_grade="research",
            per_page=max_recordings
        )
        
        if not observations:
            return 0, 0
        
        for obs in observations:
            if 'sounds' not in obs or not obs['sounds']:
                continue
            
            for sound in obs['sounds']:
                if 'file_url' not in sound:
                    continue
                    
                url = sound['file_url']
                ext = url.split('.')[-1].split('?')[0]
                if ext not in ['wav', 'mp3', 'm4a']:
                    ext = 'mp3'
                
                filename = f"{species_name.replace(' ', '_')}_{successful+1}.{ext}"
                filepath = output_path / filename
                
                # Download with retry
                for dl_attempt in range(3):
                    try:
                        time.sleep(DOWNLOAD_DELAY)
                        r = session.get(url, timeout=TIMEOUT)
                        if r.status_code == 200:
                            with open(filepath, 'wb') as f:
                                f.write(r.content)
                            attempted += 1
                            
                            # Verify the file is not corrupted
                            if is_audio_valid(filepath):
                                successful += 1
                                print(f"    ✅ Downloaded ({successful}/{max_recordings})")
                            else:
                                filepath.unlink()
                                print(f"    ⚠️ Corrupted - deleted")
                            
                            break
                        else:
                            print(f"    ⚠️ HTTP {r.status_code} - retry {dl_attempt+1}")
                            time.sleep(2)
                            
                    except Exception as e:
                        print(f"    ❌ Error: {e} - retry {dl_attempt+1}")
                        time.sleep(2)
                
                if successful >= max_recordings:
                    break
            
            if successful >= max_recordings:
                break
        
        return successful, attempted
    
    except Exception as e:
        print(f"    ❌ Fatal error: {e}")
        return 0, 0

def get_observations_safe(**params):
    """Safe wrapper for get_observations with retry"""
    from pyinaturalist import get_observations
    
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(RATE_LIMIT_DELAY)
            result = get_observations(**params)
            if result and result.get('results'):
                return result.get('results', [])
            return []
        except Exception as e:
            print(f"    Observation fetch failed (attempt {attempt+1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(3 ** attempt)
            else:
                return []

def is_audio_valid(filepath):
    """Check if audio file is valid and not corrupted"""
    try:
        audio, sr = sf.read(filepath)
        if len(audio) > 0:
            return True
        return False
    except Exception:
        return False

def rebuild_dataset(output_dir=OUTPUT_DIR, max_per_species=10):
    """Rebuild dataset with top species only"""
    
    print("=" * 60)
    print("REBUILDING TOP ANIMAL SOUNDS DATASET")
    print("=" * 60)
    print(f"Output: {output_dir}")
    print(f"Max recordings per species: {max_per_species}")
    print(f"Rate limit delay: {RATE_LIMIT_DELAY}s")
    print(f"Download delay: {DOWNLOAD_DELAY}s")
    print(f"Max retries: {MAX_RETRIES}")
    print("=" * 60)
    
    base_path = Path(output_dir)
    base_path.mkdir(parents=True, exist_ok=True)
    
    dataset_stats = {
        "continents": {},
        "total_species": 0,
        "total_valid_files": 0,
        "total_attempted": 0
    }
    
    # Process each continent
    for continent_name, place_id in CONTINENTS.items():
        print(f"\n{'='*60}")
        print(f"PROCESSING {continent_name.upper()}")
        print(f"{'='*60}")
        
        continent_path = base_path / continent_name
        continent_path.mkdir(exist_ok=True)
        
        # Get top 20 wild species
        print(f"\n📊 Finding top 20 wild species...")
        wild_species = get_top_wild_species(place_id, limit=20)
        print(f"  Found {len(wild_species)} species with audio")
        
        # Download wild species
        wild_path = continent_path / "wild"
        wild_path.mkdir(exist_ok=True)
        
        wild_stats = []
        for species in tqdm(wild_species, desc="Downloading wild species"):
            species_name = species['name']
            species_path = wild_path / species_name.replace(" ", "_")
            species_path.mkdir(exist_ok=True)
            
            print(f"\n  🎵 {species['common_name']} ({species_name})")
            print(f"     Observations: {species['observation_count']}")
            
            valid, attempted = download_species_audio(species_name, species_path, max_per_species)
            
            wild_stats.append({
                'name': species_name,
                'common_name': species['common_name'],
                'valid_files': valid,
                'attempted': attempted
            })
            
            dataset_stats["total_valid_files"] += valid
            dataset_stats["total_attempted"] += attempted
            
            if valid > 0:
                dataset_stats["total_species"] += 1
        
        # Get top 10 domestic species
        print(f"\n📊 Finding top 10 domestic species...")
        domestic_species = get_top_domestic_species(place_id, limit=10)
        print(f"  Found {len(domestic_species)} species with audio")
        
        # Download domestic species
        domestic_path = continent_path / "domestic"
        domestic_path.mkdir(exist_ok=True)
        
        domestic_stats = []
        for species in tqdm(domestic_species, desc="Downloading domestic species"):
            species_name = species['name']
            species_path = domestic_path / species_name.replace(" ", "_")
            species_path.mkdir(exist_ok=True)
            
            print(f"\n  🎵 {species['common_name']} ({species_name})")
            print(f"     Observations: {species['observation_count']}")
            
            valid, attempted = download_species_audio(species_name, species_path, max_per_species)
            
            domestic_stats.append({
                'name': species_name,
                'common_name': species['common_name'],
                'valid_files': valid,
                'attempted': attempted
            })
            
            dataset_stats["total_valid_files"] += valid
            dataset_stats["total_attempted"] += attempted
            
            if valid > 0:
                dataset_stats["total_species"] += 1
        
        # Save continent stats
        dataset_stats["continents"][continent_name] = {
            "wild": wild_stats,
            "domestic": domestic_stats
        }
        
        # Summary for this continent
        print(f"\n📊 {continent_name.upper()} SUMMARY:")
        wild_valid = sum(s['valid_files'] for s in wild_stats)
        domestic_valid = sum(s['valid_files'] for s in domestic_stats)
        print(f"  Wild species: {len(wild_stats)} | Valid files: {wild_valid}")
        print(f"  Domestic species: {len(domestic_stats)} | Valid files: {domestic_valid}")
        
        # Save continent progress
        with open(continent_path / "progress.json", 'w') as f:
            json.dump({
                "wild": wild_stats,
                "domestic": domestic_stats
            }, f, indent=2)
    
    # Save overall metadata
    metadata = {
        "source": "iNaturalist API",
        "description": "Top 20 wild species + top 10 domestic species per continent",
        "max_recordings_per_species": max_per_species,
        "total_species_with_valid_audio": dataset_stats["total_species"],
        "total_valid_files": dataset_stats["total_valid_files"],
        "total_attempted_downloads": dataset_stats["total_attempted"],
        "success_rate": f"{dataset_stats['total_valid_files']/dataset_stats['total_attempted']*100:.1f}%" if dataset_stats['total_attempted'] > 0 else "N/A",
        "continents_processed": list(CONTINENTS.keys())
    }
    
    with open(base_path / "dataset_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("\n" + "=" * 60)
    print("REBUILD COMPLETE!")
    print("=" * 60)
    print(f"Total species with valid audio: {dataset_stats['total_species']}")
    print(f"Total valid audio files: {dataset_stats['total_valid_files']}")
    print(f"Total download attempts: {dataset_stats['total_attempted']}")
    if dataset_stats['total_attempted'] > 0:
        print(f"Success rate: {dataset_stats['total_valid_files']/dataset_stats['total_attempted']*100:.1f}%")
    print(f"Metadata saved: {base_path / 'dataset_metadata.json'}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description='Rebuild top animal sounds dataset (safe version)')
    parser.add_argument('--output', default='animal_sounds', help='Output directory')
    parser.add_argument('--max', type=int, default=10, help='Max recordings per species')
    parser.add_argument('--delay', type=float, default=1.5, help='API delay in seconds')
    args = parser.parse_args()
    
    global RATE_LIMIT_DELAY
    RATE_LIMIT_DELAY = args.delay
    
    rebuild_dataset(args.output, args.max)

if __name__ == "__main__":
    main()