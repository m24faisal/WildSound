# rebuild_top_animals_safe.py
"""
Rebuild animal sounds dataset with:
- Top 20 most common wild animals per continent (with audio)
- Top 10 most common domestic animals per continent (with audio)
- Only downloads uncorrupted audio files
- Shows download progress
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

# Domestic animals to check
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
            if attempt == 0:
                time.sleep(RATE_LIMIT_DELAY)
            else:
                wait_time = (2 ** attempt) * 2
                time.sleep(wait_time)
            
            response = session.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            if attempt == max_attempts - 1:
                return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get('Retry-After', 30))
                time.sleep(retry_after)
            else:
                if attempt == max_attempts - 1:
                    return None
            time.sleep(RATE_LIMIT_DELAY * (attempt + 1))
        except Exception as e:
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
    
    data = make_api_request(url, params)
    
    if not data or 'results' not in data:
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
    
    domestic_counts.sort(key=lambda x: x['observation_count'], reverse=True)
    return domestic_counts[:limit]

def get_audio_urls_for_species(species_name, max_recordings=10):
    """Get audio URLs for a species (returns list of URLs)"""
    
    from pyinaturalist import get_observations
    
    urls = []
    
    try:
        time.sleep(RATE_LIMIT_DELAY)
        observations = get_observations(
            taxon_name=species_name,
            has_sounds=True,
            quality_grade="research",
            per_page=max_recordings
        )
        
        if not observations or not observations.get('results'):
            return urls
        
        for obs in observations.get('results', []):
            if 'sounds' not in obs or not obs['sounds']:
                continue
            
            for sound in obs['sounds']:
                if 'file_url' in sound:
                    urls.append(sound['file_url'])
                    if len(urls) >= max_recordings:
                        return urls
        
        return urls
        
    except Exception as e:
        print(f"      Error getting URLs: {e}")
        return urls

def download_audio_file(url, output_path, retries=3):
    """Download a single audio file with verification"""
    
    for attempt in range(retries):
        try:
            time.sleep(DOWNLOAD_DELAY)
            response = session.get(url, timeout=TIMEOUT)
            
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                # Verify file is not corrupted
                if is_audio_valid(output_path):
                    return True
                else:
                    output_path.unlink()
                    return False
            else:
                if attempt < retries - 1:
                    time.sleep(2)
                    
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
    
    return False

def download_species_audio(species_name, output_path, max_recordings=10):
    """Download audio for a species with progress bar"""
    
    # Get audio URLs
    urls = get_audio_urls_for_species(species_name, max_recordings)
    
    if not urls:
        return 0, 0
    
    successful = 0
    
    # Download each URL with progress
    for i, url in enumerate(urls):
        ext = url.split('.')[-1].split('?')[0]
        if ext not in ['wav', 'mp3', 'm4a']:
            ext = 'mp3'
        
        filename = f"{species_name.replace(' ', '_')}_{i+1}.{ext}"
        filepath = output_path / filename
        
        print(f"      Downloading {i+1}/{len(urls)}: {filename[:50]}...", end="")
        
        if download_audio_file(url, filepath):
            successful += 1
            print(f" ✅")
        else:
            print(f" ❌")
    
    return successful, len(urls)

def is_audio_valid(filepath):
    """Check if audio file is valid and not corrupted"""
    try:
        audio, sr = sf.read(filepath)
        return len(audio) > 0
    except Exception:
        return False

def rebuild_dataset(output_dir=OUTPUT_DIR, max_per_species=10):
    """Rebuild dataset with top species only"""
    
    print("=" * 60)
    print("REBUILDING TOP ANIMAL SOUNDS DATASET")
    print("=" * 60)
    print(f"Output: {output_dir}")
    print(f"Max recordings per species: {max_per_species}")
    print(f"API delay: {RATE_LIMIT_DELAY}s")
    print(f"Download delay: {DOWNLOAD_DELAY}s")
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
        print(f"\n📊 Getting top 20 wild species...")
        wild_species = get_top_wild_species(place_id, limit=20)
        print(f"  Found {len(wild_species)} species with audio")
        
        # Download wild species
        wild_path = continent_path / "wild"
        wild_path.mkdir(exist_ok=True)
        
        wild_stats = []
        for species in wild_species:
            species_name = species['name']
            species_path = wild_path / species_name.replace(" ", "_")
            species_path.mkdir(exist_ok=True)
            
            print(f"\n  🎵 {species['common_name']} ({species_name})")
            print(f"     Observations: {species['observation_count']}")
            print(f"     Downloading up to {max_per_species} recordings...")
            
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
                print(f"     ✅ Downloaded {valid}/{attempted} valid files")
            else:
                print(f"     ❌ No valid files downloaded")
        
        # Get top 10 domestic species
        print(f"\n📊 Getting top 10 domestic species...")
        domestic_species = get_top_domestic_species(place_id, limit=10)
        print(f"  Found {len(domestic_species)} species with audio")
        
        # Download domestic species
        domestic_path = continent_path / "domestic"
        domestic_path.mkdir(exist_ok=True)
        
        domestic_stats = []
        for species in domestic_species:
            species_name = species['name']
            species_path = domestic_path / species_name.replace(" ", "_")
            species_path.mkdir(exist_ok=True)
            
            print(f"\n  🎵 {species['common_name']} ({species_name})")
            print(f"     Observations: {species['observation_count']}")
            print(f"     Downloading up to {max_per_species} recordings...")
            
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
                print(f"     ✅ Downloaded {valid}/{attempted} valid files")
            else:
                print(f"     ❌ No valid files downloaded")
        
        # Save continent stats
        dataset_stats["continents"][continent_name] = {
            "wild": wild_stats,
            "domestic": domestic_stats
        }
        
        # Summary for this continent
        print(f"\n📊 {continent_name.upper()} SUMMARY:")
        wild_valid = sum(s['valid_files'] for s in wild_stats)
        domestic_valid = sum(s['valid_files'] for s in domestic_stats)
        print(f"  Wild: {len(wild_stats)} species, {wild_valid} valid files")
        print(f"  Domestic: {len(domestic_stats)} species, {domestic_valid} valid files")
    
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
    parser = argparse.ArgumentParser(description='Rebuild top animal sounds dataset')
    parser.add_argument('--output', default='animal_sounds', help='Output directory')
    parser.add_argument('--max', type=int, default=10, help='Max recordings per species')
    parser.add_argument('--delay', type=float, default=1.5, help='API delay in seconds')
    args = parser.parse_args()
    
    global RATE_LIMIT_DELAY
    RATE_LIMIT_DELAY = args.delay
    
    rebuild_dataset(args.output, args.max)

if __name__ == "__main__":
    main()