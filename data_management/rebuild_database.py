# download_top_wild_and_domestic.py
"""
Get top 20 wild + top 10 domestic species per continent
- Step 1: Get species lists from iNaturalist
- Step 2: Download verified audio from AnimalSpeak
"""

import os
import requests
import random
import soundfile as sf
from datasets import load_dataset
from pathlib import Path
from tqdm import tqdm
import json
import time
import argparse

# Configuration
DOWNLOAD_DELAY = 0.5
TEST_SPLIT = 0.2
MAX_FILES_PER_SPECIES = 10
OUTPUT_DIR = "animal_sounds"

# Continents with iNaturalist place IDs
CONTINENTS = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
}

# Domestic animals to search for (will get top 10 per continent)
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

def get_top_wild_species(place_id, limit=20):
    """Get top N wild species with audio from iNaturalist"""
    
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
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        species_list = []
        for result in data.get('results', []):
            taxon = result.get('taxon', {})
            species_list.append({
                'name': taxon.get('name'),
                'common_name': taxon.get('preferred_common_name', taxon.get('name')),
                'observation_count': result.get('count', 0),
                'type': 'wild'
            })
        
        return species_list
        
    except Exception as e:
        print(f"  Error getting wild species: {e}")
        return []

def get_top_domestic_species(place_id, limit=10):
    """Get top N domestic species with audio for a continent"""
    
    domestic_counts = []
    
    for taxon_name in DOMESTIC_TAXA:
        url = "https://api.inaturalist.org/v1/observations"
        params = {
            "taxon_name": taxon_name,
            "place_id": place_id,
            "has[]": "sounds",
            "verifiable": True,
            "quality_grade": "research",
            "per_page": 1
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            count = data.get('total_results', 0)
            
            if count > 0:
                common_name = taxon_name.replace("_", " ").replace("domesticus", "domestic").title()
                domestic_counts.append({
                    'name': taxon_name,
                    'common_name': common_name,
                    'observation_count': count,
                    'type': 'domestic'
                })
            
            time.sleep(0.5)  # Rate limit
        except:
            pass
    
    # Sort by count and return top N
    domestic_counts.sort(key=lambda x: x['observation_count'], reverse=True)
    return domestic_counts[:limit]

def is_valid_audio(filepath):
    """Check if audio file is valid"""
    try:
        audio, sr = sf.read(filepath)
        return len(audio) > 0
    except:
        return False

def download_species_from_animalspeak(species_name, output_dir, category, max_files=10):
    """Download a species from AnimalSpeak dataset"""
    
    try:
        # Load dataset in streaming mode
        dataset = load_dataset(
            "davidrrobinson/AnimalSpeak",
            split="train",
            streaming=True
        )
        
        # Collect URLs for this species
        urls = []
        for item in dataset:
            if item.get('species_scientific') == species_name:
                urls.append(item.get('url'))
                if len(urls) >= max_files:
                    break
        
        if not urls:
            return 0, 0
        
        # Shuffle and split
        random.shuffle(urls)
        split_idx = int(len(urls) * (1 - TEST_SPLIT))
        train_urls = urls[:split_idx]
        test_urls = urls[split_idx:]
        
        # Create directories
        safe_name = species_name.replace(" ", "_")
        train_dir = output_dir / "train" / safe_name
        test_dir = output_dir / "test" / safe_name
        train_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        
        downloaded = 0
        
        # Download training files
        for i, url in enumerate(train_urls):
            ext = url.split('.')[-1].split('?')[0]
            if ext not in ['wav', 'mp3', 'm4a']:
                ext = 'mp3'
            
            filepath = train_dir / f"{safe_name}_{i+1}.{ext}"
            
            try:
                time.sleep(DOWNLOAD_DELAY)
                r = requests.get(url, timeout=30)
                if r.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(r.content)
                    if is_valid_audio(filepath):
                        downloaded += 1
                    else:
                        filepath.unlink()
            except:
                pass
        
        # Download test files
        for i, url in enumerate(test_urls):
            ext = url.split('.')[-1].split('?')[0]
            if ext not in ['wav', 'mp3', 'm4a']:
                ext = 'mp3'
            
            filepath = test_dir / f"{safe_name}_{i+1}.{ext}"
            
            try:
                time.sleep(DOWNLOAD_DELAY)
                r = requests.get(url, timeout=30)
                if r.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(r.content)
                    if is_valid_audio(filepath):
                        downloaded += 1
                    else:
                        filepath.unlink()
            except:
                pass
        
        return downloaded, len(urls)
        
    except Exception as e:
        print(f"    Error: {e}")
        return 0, 0

def build_dataset(output_dir=OUTPUT_DIR, max_per_species=10):
    """Build dataset with top 20 wild + top 10 domestic per continent"""
    
    print("=" * 60)
    print("BUILDING TOP SPECIES DATASET")
    print("=" * 60)
    print(f"Output: {output_dir}")
    print(f"Max files per species: {max_per_species}")
    print(f"Test split: {TEST_SPLIT:.0%}")
    print("=" * 60)
    
    base_path = Path(output_dir)
    base_path.mkdir(parents=True, exist_ok=True)
    
    all_species = {}  # name -> {common, type, continents}
    continent_data = {}
    
    # Step 1: Get species for each continent
    for continent_name, place_id in CONTINENTS.items():
        print(f"\n{'='*60}")
        print(f"CONTINENT: {continent_name.upper()}")
        print(f"{'='*60}")
        
        # Get wild species
        print(f"\n🌿 Getting top 20 WILD species...")
        wild_species = get_top_wild_species(place_id, limit=20)
        print(f"  Found {len(wild_species)} wild species")
        
        # Get domestic species
        print(f"\n🏠 Getting top 10 DOMESTIC species...")
        domestic_species = get_top_domestic_species(place_id, limit=10)
        print(f"  Found {len(domestic_species)} domestic species")
        
        # Combine
        all_continent_species = wild_species + domestic_species
        
        continent_data[continent_name] = {
            'wild': wild_species,
            'domestic': domestic_species,
            'downloaded': []
        }
        
        # Add to master list
        for s in all_continent_species:
            if s['name'] not in all_species:
                all_species[s['name']] = {
                    'common_name': s['common_name'],
                    'type': s['type'],
                    'continents': [continent_name]
                }
            else:
                all_species[s['name']]['continents'].append(continent_name)
        
        # Show summary
        print(f"\n📊 {continent_name.upper()} SUMMARY:")
        print(f"  Wild: {len(wild_species)} species")
        print(f"  Domestic: {len(domestic_species)} species")
        if wild_species:
            print(f"  Top wild: {wild_species[0]['common_name']} ({wild_species[0]['observation_count']} obs)")
        if domestic_species:
            print(f"  Top domestic: {domestic_species[0]['common_name']} ({domestic_species[0]['observation_count']} obs)")
    
    print(f"\n{'='*60}")
    print(f"TOTAL UNIQUE SPECIES: {len(all_species)}")
    print(f"  Wild: {sum(1 for s in all_species.values() if s['type'] == 'wild')}")
    print(f"  Domestic: {sum(1 for s in all_species.values() if s['type'] == 'domestic')}")
    print(f"{'='*60}")
    
    # Step 2: Download audio from AnimalSpeak
    print(f"\n📥 DOWNLOADING AUDIO FROM ANIMALSPEAK")
    print(f"{'='*60}")
    
    total_files = 0
    successful_species = 0
    species_list = list(all_species.keys())
    
    for idx, species_name in enumerate(species_list):
        species_info = all_species[species_name]
        print(f"\n[{idx+1}/{len(species_list)}] {species_info['common_name']} ({species_name})")
        print(f"  Type: {species_info['type']} | Continents: {', '.join(species_info['continents'])}")
        
        valid, total = download_species_from_animalspeak(
            species_name, 
            base_path, 
            species_info['type'],
            max_per_species
        )
        
        if valid > 0:
            successful_species += 1
            total_files += valid
            print(f"  ✅ Downloaded {valid}/{total} valid files")
        else:
            print(f"  ❌ No valid files found")
    
    # Step 3: Save metadata
    metadata = {
        "source": "iNaturalist (species lists) + AnimalSpeak (audio)",
        "description": "Top 20 wild + top 10 domestic species per continent",
        "continents": list(CONTINENTS.keys()),
        "species_by_continent": continent_data,
        "total_unique_species": len(all_species),
        "wild_species_count": sum(1 for s in all_species.values() if s['type'] == 'wild'),
        "domestic_species_count": sum(1 for s in all_species.values() if s['type'] == 'domestic'),
        "species_with_audio": successful_species,
        "total_files": total_files,
        "max_files_per_species": max_per_species,
        "test_split": TEST_SPLIT
    }
    
    with open(base_path / "dataset_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    print(f"Unique species found: {len(all_species)}")
    print(f"  Wild: {metadata['wild_species_count']}")
    print(f"  Domestic: {metadata['domestic_species_count']}")
    print(f"Species with audio: {successful_species}")
    print(f"Total audio files: {total_files}")
    print(f"Output: {output_dir}/")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='animal_sounds')
    parser.add_argument('--max', type=int, default=10, help='Max files per species')
    args = parser.parse_args()
    
    build_dataset(args.output, args.max)

if __name__ == "__main__":
    main()