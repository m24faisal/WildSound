#!/usr/bin/env python3
"""
Wild Sound Dataset Builder
Downloads top 100 wild + top 20 domestic animal sounds per continent from iNaturalist
"""

import requests
import time
import os
import json
from pathlib import Path
import argparse
from datetime import datetime

# Configuration
API_BASE = "https://api.inaturalist.org/v1"
USER_AGENT = "WildSoundDatasetBuilder/1.0"
RATE_LIMIT_DELAY = 1  # seconds between API calls to be respectful

# Continents with their iNaturalist place IDs
CONTINENTS = {
    "north_america": 97394,
    "south_america": 97389,
    "europe": 97391,
    "africa": 97392,
    "asia": 97395,
    "oceania": 97393
}

# Domestic animal species to search for
DOMESTIC_SPECIES = [
    {"scientific": "Canis lupus familiaris", "common": "Domestic Dog"},
    {"scientific": "Felis catus", "common": "Domestic Cat"},
    {"scientific": "Bos taurus", "common": "Domestic Cattle"},
    {"scientific": "Equus caballus", "common": "Domestic Horse"},
    {"scientific": "Equus asinus", "common": "Donkey"},
    {"scientific": "Capra hircus", "common": "Domestic Goat"},
    {"scientific": "Ovis aries", "common": "Domestic Sheep"},
    {"scientific": "Sus scrofa domesticus", "common": "Domestic Pig"},
    {"scientific": "Gallus gallus domesticus", "common": "Domestic Chicken"},
    {"scientific": "Anas platyrhynchos domesticus", "common": "Domestic Duck"},
    {"scientific": "Meleagris gallopavo", "common": "Domestic Turkey"},
    {"scientific": "Lama glama", "common": "Llama"},
    {"scientific": "Vicugna pacos", "common": "Alpaca"},
    {"scientific": "Cavia porcellus", "common": "Guinea Pig"},
    {"scientific": "Oryctolagus cuniculus", "common": "European Rabbit"},
    {"scientific": "Columba livia domestica", "common": "Domestic Pigeon"},
    {"scientific": "Serinus canaria domestica", "common": "Domestic Canary"},
    {"scientific": "Melopsittacus undulatus", "common": "Budgerigar"},
    {"scientific": "Mesocricetus auratus", "common": "Golden Hamster"},
    {"scientific": "Mustela putorius furo", "common": "Ferret"},
    {"scientific": "Anser anser domesticus", "common": "Domestic Goose"},
    {"scientific": "Numida meleagris", "common": "Guineafowl"},
    {"scientific": "Camelus dromedarius", "common": "Dromedary Camel"},
    {"scientific": "Camelus bactrianus", "common": "Bactrian Camel"},
    {"scientific": "Bubalus bubalis", "common": "Domestic Water Buffalo"},
]

def make_api_request(url, params=None):
    """Make a rate-limited API request to iNaturalist"""
    headers = {"User-Agent": USER_AGENT}
    time.sleep(RATE_LIMIT_DELAY)  # Be respectful of the API
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None

def download_audio_file(url, output_path):
    """Download an audio file from a URL"""
    headers = {"User-Agent": USER_AGENT}
    
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
    except Exception as e:
        print(f"  Failed to download {url}: {e}")
        return False

def get_wild_species_for_continent(continent_name, place_id, limit=100):
    """Get top wild species with audio for a continent"""
    print(f"\nGetting top {limit} wild species for {continent_name}...")
    
    url = f"{API_BASE}/observations/species_counts"
    params = {
        "place_id": place_id,
        "has[]": "sounds",
        "verifiable": True,
        "quality_grade": "research",
        "per_page": limit
    }
    
    data = make_api_request(url, params)
    if not data or 'results' not in data:
        print(f"  Failed to get data for {continent_name}")
        return []
    
    species_list = []
    for result in data['results']:
        taxon = result['taxon']
        species_list.append({
            "taxon_id": taxon['id'],
            "scientific_name": taxon['name'],
            "common_name": taxon.get('preferred_common_name', taxon['name']),
            "observation_count": result['count'],
            "rank": taxon.get('rank', 'species')
        })
    
    print(f"  Found {len(species_list)} species")
    return species_list

def get_recordings_for_species(taxon_id, max_recordings=5):
    """Get audio recordings for a specific species"""
    url = f"{API_BASE}/observations"
    params = {
        "taxon_id": taxon_id,
        "has[]": "sounds",
        "verifiable": True,
        "quality_grade": "research",
        "order_by": "votes",
        "per_page": max_recordings
    }
    
    data = make_api_request(url, params)
    if not data or 'results' not in data:
        return []
    
    recordings = []
    for obs in data['results']:
        if 'sounds' in obs:
            for sound in obs['sounds']:
                if 'file_url' in sound:
                    recordings.append({
                        "observation_id": obs['id'],
                        "file_url": sound['file_url'].replace("http://", "https://"),
                        "license": sound.get('license_code', 'unknown'),
                        "observer": obs['user']['login'],
                        "observed_on": obs.get('observed_on', 'unknown'),
                        "quality_grade": obs['quality_grade']
                    })
    
    return recordings[:max_recordings]

def get_domestic_species_for_continent(continent_name, place_id, limit=20):
    """Get top domestic species with audio for a continent"""
    print(f"\nGetting top {limit} domestic species for {continent_name}...")
    
    domestic_with_audio = []
    
    for species in DOMESTIC_SPECIES:
        url = f"{API_BASE}/observations"
        params = {
            "taxon_name": species['scientific'],
            "place_id": place_id,
            "has[]": "sounds",
            "verifiable": True,
            "quality_grade": "research",
            "per_page": 1  # Just need to check if any exist
        }
        
        data = make_api_request(url, params)
        if data and data.get('total_results', 0) > 0:
            domestic_with_audio.append({
                "scientific_name": species['scientific'],
                "common_name": species['common'],
                "observation_count": data['total_results']
            })
    
    # Sort by observation count and take top 'limit'
    domestic_with_audio.sort(key=lambda x: x['observation_count'], reverse=True)
    top_domestic = domestic_with_audio[:limit]
    
    print(f"  Found {len(top_domestic)} domestic species with audio")
    for d in top_domestic:
        print(f"    {d['common_name']}: {d['observation_count']} observations")
    
    return top_domestic

def build_dataset(output_dir="animal_sounds", max_recordings_per_species=5):
    """Build the complete animal sound dataset"""
    
    # Create base output directory
    base_path = Path(output_dir)
    base_path.mkdir(exist_ok=True)
    
    # Save metadata file
    metadata = {
        "generated": datetime.now().isoformat(),
        "continents": {},
        "stats": {}
    }
    
    total_wild_species = 0
    total_domestic_species = 0
    total_recordings = 0
    
    # Process each continent
    for continent_name, place_id in CONTINENTS.items():
        print(f"\n{'='*60}")
        print(f"Processing {continent_name.upper()}")
        print(f"{'='*60}")
        
        continent_dir = base_path / continent_name
        continent_dir.mkdir(exist_ok=True)
        
        continent_metadata = {
            "wild": [],
            "domestic": []
        }
        
        # 1. Get wild species
        wild_species = get_wild_species_for_continent(continent_name, place_id, limit=100)
        
        # Download recordings for each wild species
        for species in wild_species:
            species_dir = continent_dir / "wild" / species['scientific_name'].replace(" ", "_")
            species_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"\n  Wild: {species['common_name']} ({species['scientific_name']})")
            recordings = get_recordings_for_species(species['taxon_id'], max_recordings_per_species)
            
            species_recordings = []
            for i, rec in enumerate(recordings):
                file_ext = os.path.splitext(rec['file_url'])[1] or '.mp3'
                filename = f"{species['scientific_name'].replace(' ', '_')}_{i+1}{file_ext}"
                filepath = species_dir / filename
                
                print(f"    Downloading recording {i+1}/{len(recordings)}...")
                if download_audio_file(rec['file_url'], filepath):
                    species_recordings.append({
                        "filename": filename,
                        "url": rec['file_url'],
                        "license": rec['license'],
                        "observer": rec['observer'],
                        "observed_on": rec['observed_on']
                    })
                    total_recordings += 1
            
            continent_metadata["wild"].append({
                "scientific_name": species['scientific_name'],
                "common_name": species['common_name'],
                "observation_count": species['observation_count'],
                "recordings": species_recordings
            })
            total_wild_species += 1
        
        # 2. Get domestic species
        domestic_species = get_domestic_species_for_continent(continent_name, place_id, limit=20)
        
        # Download recordings for each domestic species
        for species in domestic_species:
            species_dir = continent_dir / "domestic" / species['scientific_name'].replace(" ", "_")
            species_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"\n  Domestic: {species['common_name']}")
            
            # Get taxon ID first
            url = f"{API_BASE}/taxa"
            params = {"q": species['scientific_name']}
            data = make_api_request(url, params)
            
            if data and data['results']:
                taxon_id = data['results'][0]['id']
                recordings = get_recordings_for_species(taxon_id, max_recordings_per_species)
                
                species_recordings = []
                for i, rec in enumerate(recordings):
                    file_ext = os.path.splitext(rec['file_url'])[1] or '.mp3'
                    filename = f"{species['scientific_name'].replace(' ', '_')}_{i+1}{file_ext}"
                    filepath = species_dir / filename
                    
                    print(f"    Downloading recording {i+1}/{len(recordings)}...")
                    if download_audio_file(rec['file_url'], filepath):
                        species_recordings.append({
                            "filename": filename,
                            "url": rec['file_url'],
                            "license": rec['license'],
                            "observer": rec['observer'],
                            "observed_on": rec['observed_on']
                        })
                        total_recordings += 1
                
                continent_metadata["domestic"].append({
                    "scientific_name": species['scientific_name'],
                    "common_name": species['common_name'],
                    "observation_count": species['observation_count'],
                    "recordings": species_recordings
                })
                total_domestic_species += 1
        
        # Save continent metadata
        metadata["continents"][continent_name] = continent_metadata
    
    # Save overall statistics
    metadata["stats"] = {
        "total_wild_species": total_wild_species,
        "total_domestic_species": total_domestic_species,
        "total_species": total_wild_species + total_domestic_species,
        "total_recordings": total_recordings
    }
    
    # Save metadata file
    with open(base_path / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n{'='*60}")
    print("DATASET BUILD COMPLETE!")
    print(f"{'='*60}")
    print(f"Output directory: {base_path.absolute()}")
    print(f"Total wild species: {total_wild_species}")
    print(f"Total domestic species: {total_domestic_species}")
    print(f"Total species: {total_wild_species + total_domestic_species}")
    print(f"Total recordings: {total_recordings}")
    print(f"Metadata saved to: {base_path / 'metadata.json'}")

def main():
    parser = argparse.ArgumentParser(description='Build animal sound dataset from iNaturalist')
    parser.add_argument('--output', '-o', default='animal_sounds',
                        help='Output directory (default: animal_sounds)')
    parser.add_argument('--recordings', '-r', type=int, default=5,
                        help='Max recordings per species (default: 5)')
    parser.add_argument('--delay', '-d', type=float, default=1.0,
                        help='Delay between API calls in seconds (default: 1.0)')
    
    args = parser.parse_args()
    
    global RATE_LIMIT_DELAY
    RATE_LIMIT_DELAY = args.delay
    
    print("=" * 60)
    print("WILD SOUND DATASET BUILDER")
    print("=" * 60)
    print(f"Output directory: {args.output}")
    print(f"Max recordings per species: {args.recordings}")
    print(f"API delay: {args.delay}s")
    print("=" * 60)
    
    build_dataset(args.output, args.recordings)

if __name__ == "__main__":
    main()