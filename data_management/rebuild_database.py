# download_top_wild_and_domestic.py - SILENT VERSION
"""
Downloads only valid audio files. Suppresses all corruption warnings.
"""

import os
import sys
import requests
import random
import soundfile as sf
from datasets import load_dataset
from pathlib import Path
from tqdm import tqdm
import json
import time
import argparse
import warnings
import logging
import subprocess
from contextlib import contextmanager

# ===== SILENCE EVERYTHING =====
warnings.filterwarnings('ignore')
logging.getLogger('datasets').setLevel(logging.ERROR)
logging.getLogger('soundfile').setLevel(logging.ERROR)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Suppress soundfile stderr messages (MPEG errors)
@contextmanager
def suppress_stderr():
    """Temporarily suppress stderr output"""
    stderr_fd = sys.stderr.fileno()
    with open(os.devnull, 'w') as devnull:
        old_stderr = os.dup(stderr_fd)
        os.dup2(devnull.fileno(), stderr_fd)
        try:
            yield
        finally:
            os.dup2(old_stderr, stderr_fd)
            os.close(old_stderr)

def is_valid_audio_silent(filepath):
    """Check if audio is valid - completely silent"""
    try:
        with suppress_stderr():
            audio, sr = sf.read(filepath)
            return len(audio) > 0
    except:
        return False

# Configuration
DOWNLOAD_DELAY = 0.5
TEST_SPLIT = 0.2
MAX_FILES_PER_SPECIES = 10
OUTPUT_DIR = "animal_sounds"

CONTINENTS = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
}

DOMESTIC_TAXA = [
    "Canis lupus familiaris", "Felis catus", "Bos taurus", "Equus caballus",
    "Capra hircus", "Ovis aries", "Sus scrofa domesticus", "Gallus gallus domesticus",
    "Anas platyrhynchos domesticus", "Meleagris gallopavo", "Lama glama", "Cavia porcellus",
    "Oryctolagus cuniculus", "Columba livia domestica", "Serinus canaria domestica",
    "Melopsittacus undulatus", "Anser anser domesticus", "Numida meleagris",
    "Camelus dromedarius", "Bubalus bubalis"
]

def get_top_wild_species(place_id, limit=20):
    """Get top wild species - silent"""
    url = "https://api.inaturalist.org/v1/observations/species_counts"
    params = {
        "place_id": place_id, "has[]": "sounds", "verifiable": True,
        "quality_grade": "research", "per_page": limit, "order_by": "count", "order": "desc"
    }
    try:
        response = requests.get(url, params=params, timeout=30)
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
    except:
        return []

def get_top_domestic_species(place_id, limit=10):
    """Get top domestic species - silent"""
    domestic_counts = []
    for taxon_name in DOMESTIC_TAXA:
        url = "https://api.inaturalist.org/v1/observations"
        params = {"taxon_name": taxon_name, "place_id": place_id, "has[]": "sounds", "verifiable": True, "quality_grade": "research", "per_page": 1}
        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            count = data.get('total_results', 0)
            if count > 0:
                common_name = taxon_name.replace("_", " ").replace("domesticus", "domestic").title()
                domestic_counts.append({
                    'name': taxon_name, 'common_name': common_name,
                    'observation_count': count, 'type': 'domestic'
                })
            time.sleep(0.3)
        except:
            pass
    domestic_counts.sort(key=lambda x: x['observation_count'], reverse=True)
    return domestic_counts[:limit]

def download_species_silent(species_name, output_dir, max_files=10):
    """Download species - only shows success count, no errors"""
    
    try:
        dataset = load_dataset("davidrrobinson/AnimalSpeak", split="train", streaming=True)
        
        urls = []
        for item in dataset:
            if item.get('species_scientific') == species_name:
                urls.append(item.get('url'))
                if len(urls) >= max_files:
                    break
        
        if not urls:
            return 0, 0
        
        random.shuffle(urls)
        split_idx = int(len(urls) * (1 - TEST_SPLIT))
        train_urls = urls[:split_idx]
        test_urls = urls[split_idx:]
        
        safe_name = species_name.replace(" ", "_")
        train_dir = output_dir / "train" / safe_name
        test_dir = output_dir / "test" / safe_name
        train_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        
        downloaded = 0
        
        # Download training files (silent)
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
                    if is_valid_audio_silent(filepath):
                        downloaded += 1
                    else:
                        filepath.unlink()
            except:
                pass
        
        # Download test files (silent)
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
                    if is_valid_audio_silent(filepath):
                        downloaded += 1
                    else:
                        filepath.unlink()
            except:
                pass
        
        return downloaded, len(urls)
        
    except:
        return 0, 0

def build_dataset(output_dir=OUTPUT_DIR, max_per_species=10):
    """Build dataset - silent progress"""
    
    print("=" * 60)
    print("BUILDING DATASET")
    print("=" * 60)
    
    base_path = Path(output_dir)
    base_path.mkdir(parents=True, exist_ok=True)
    
    all_species = {}
    continent_data = {}
    
    for continent_name, place_id in CONTINENTS.items():
        wild_species = get_top_wild_species(place_id, limit=20)
        domestic_species = get_top_domestic_species(place_id, limit=10)
        all_continent_species = wild_species + domestic_species
        
        continent_data[continent_name] = {'wild': wild_species, 'domestic': domestic_species}
        
        for s in all_continent_species:
            if s['name'] not in all_species:
                all_species[s['name']] = {
                    'common_name': s['common_name'],
                    'type': s['type'],
                    'continents': [continent_name]
                }
            else:
                all_species[s['name']]['continents'].append(continent_name)
    
    print(f"Found {len(all_species)} unique species")
    print(f"Downloading audio (this will take a while)...")
    print("=" * 60)
    
    total_files = 0
    successful_species = 0
    species_list = list(all_species.keys())
    
    for idx, species_name in enumerate(species_list):
        species_info = all_species[species_name]
        
        # Show progress without errors
        print(f"[{idx+1}/{len(species_list)}] {species_info['common_name']}", end=" ")
        
        valid, total = download_species_silent(species_name, base_path, max_per_species)
        
        if valid > 0:
            successful_species += 1
            total_files += valid
            print(f"✅ {valid} files")
        else:
            print(f"❌ no files")
    
    # Metadata
    metadata = {
        "total_unique_species": len(all_species),
        "species_with_audio": successful_species,
        "total_files": total_files
    }
    with open(base_path / "dataset_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    print(f"Species with audio: {successful_species}")
    print(f"Total audio files: {total_files}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='animal_sounds')
    parser.add_argument('--max', type=int, default=10)
    args = parser.parse_args()
    build_dataset(args.output, args.max)

if __name__ == "__main__":
    main()