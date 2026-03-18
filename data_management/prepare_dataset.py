#!/usr/bin/env python3
"""
Wild Sound - Dataset Preparation Script
Prepares the 667-species animal sound dataset for Perch 2.0 training.
Combines all continents, organizes by species, and creates train/test splits.
"""

import os
import shutil
import random
import glob
import argparse
from pathlib import Path
from sklearn.model_selection import train_test_split
import soundfile as sf
import resampy
import numpy as np
from tqdm import tqdm

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Prepare animal sound dataset for Perch 2.0 training')
    parser.add_argument('--source', '-s', default='animal_sounds',
                        help='Source directory containing the animal_sounds dataset (default: animal_sounds)')
    parser.add_argument('--output', '-o', default='dataset',
                        help='Output directory for prepared dataset (default: dataset)')
    parser.add_argument('--test-split', '-t', type=float, default=0.2,
                        help='Fraction of data to use for testing (default: 0.2)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility (default: 42)')
    parser.add_argument('--copy', action='store_true',
                        help='Copy files instead of creating symlinks (use if symlinks fail)')
    parser.add_argument('--format', choices=['wav', 'mp3'], default='wav',
                        help='Output audio format (default: wav)')
    parser.add_argument('--resample', action='store_true',
                        help='Resample audio to 32kHz for Perch (recommended)')
    return parser.parse_args()

def ensure_dir(directory):
    """Create directory if it doesn't exist."""
    os.makedirs(directory, exist_ok=True)

def get_species_name_from_path(file_path):
    """
    Extract species name from the file path.
    Handles paths like: continent/category/scientific_name/filename
    """
    path = Path(file_path)
    # The species name is the parent directory of the file
    species_dir = path.parent.name
    # Replace underscores with spaces for readability
    return species_dir.replace('_', ' ')

def get_all_audio_files(source_dir):
    """
    Recursively find all audio files in the source directory.
    Returns a dictionary mapping species name to list of file paths.
    """
    species_files = {}
    total_files = 0
    
    print(f"\nScanning {source_dir} for audio files...")
    
    # Supported audio extensions
    audio_extensions = ['.wav', '.mp3', '.m4a', '.3gp', '.flac', '.ogg']
    
    # Walk through all directories
    for root, dirs, files in os.walk(source_dir):
        # Skip metadata.json
        if 'metadata.json' in files:
            continue
            
        for file in files:
            if any(file.lower().endswith(ext) for ext in audio_extensions):
                file_path = os.path.join(root, file)
                species_name = get_species_name_from_path(file_path)
                
                if species_name not in species_files:
                    species_files[species_name] = []
                species_files[species_name].append(file_path)
                total_files += 1
    
    print(f"Found {len(species_files)} species with {total_files} total files")
    return species_files, total_files

def filter_species_with_few_files(species_files, min_files=2):
    """
    Remove species with too few files (can't split train/test).
    Returns filtered dictionary and list of removed species.
    """
    filtered = {}
    removed = []
    
    for species, files in species_files.items():
        if len(files) >= min_files:
            filtered[species] = files
        else:
            removed.append((species, len(files)))
    
    if removed:
        print(f"\nRemoved {len(removed)} species with fewer than {min_files} files:")
        for species, count in removed[:10]:  # Show first 10
            print(f"  - {species}: {count} file(s)")
        if len(removed) > 10:
            print(f"  ... and {len(removed) - 10} more")
    
    return filtered, removed

def resample_audio(input_path, output_path, target_sr=32000):
    """
    Resample audio to target sample rate and save as WAV.
    Perch expects 32kHz audio.
    """
    try:
        # Read audio file
        audio, sr = sf.read(input_path)
        
        # Convert to mono if stereo
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        
        # Resample if needed
        if sr != target_sr:
            audio = resampy.resample(audio, sr, target_sr)
        
        # Ensure float32 in range [-1, 1]
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        # Normalize if needed (optional)
        max_val = np.max(np.abs(audio))
        if max_val > 1.0:
            audio = audio / max_val
        
        # Save as WAV
        sf.write(output_path, audio, target_sr)
        return True
        
    except Exception as e:
        print(f"  Error resampling {input_path}: {e}")
        return False

def copy_or_symlink(src, dst, use_copy=False):
    """Copy or create symlink based on user preference."""
    if use_copy:
        shutil.copy2(src, dst)
    else:
        try:
            # Try symlink first (saves disk space)
            os.symlink(os.path.abspath(src), dst)
        except (OSError, NotImplementedError):
            # Fall back to copy if symlink fails
            shutil.copy2(src, dst)

def prepare_dataset(args):
    """Main dataset preparation function."""
    
    print("=" * 60)
    print("WILD SOUND - DATASET PREPARATION")
    print("=" * 60)
    print(f"Source directory: {args.source}")
    print(f"Output directory: {args.output}")
    print(f"Test split: {args.test_split * 100:.0f}%")
    print(f"Random seed: {args.seed}")
    print(f"Copy files: {args.copy}")
    print(f"Output format: {args.format}")
    print(f"Resample to 32kHz: {args.resample}")
    print("=" * 60)
    
    # Set random seed for reproducibility
    random.seed(args.seed)
    np.random.seed(args.seed)
    
    # Create output directories
    train_dir = os.path.join(args.output, 'train')
    test_dir = os.path.join(args.output, 'test')
    ensure_dir(train_dir)
    ensure_dir(test_dir)
    
    # Get all audio files
    species_files, total_files = get_all_audio_files(args.source)
    
    # Filter species with too few files
    species_files, removed = filter_species_with_few_files(species_files, min_files=2)
    
    if not species_files:
        print("\n❌ No valid species found! Exiting.")
        return
    
    print(f"\nProcessing {len(species_files)} species with at least 2 files each...")
    
    # Statistics tracking
    stats = {
        'total_species': len(species_files),
        'total_files': sum(len(files) for files in species_files.values()),
        'train_files': 0,
        'test_files': 0,
        'species_details': []
    }
    
    # Process each species
    species_list = sorted(species_files.keys())
    
    for idx, species in enumerate(tqdm(species_list, desc="Processing species")):
        files = species_files[species]
        
        # Create species directories
        species_train_dir = os.path.join(train_dir, species)
        species_test_dir = os.path.join(test_dir, species)
        ensure_dir(species_train_dir)
        ensure_dir(species_test_dir)
        
        # Split files into train/test
        # Use stratify to maintain class distribution (though we're already per-class)
        train_files, test_files = train_test_split(
            files,
            test_size=args.test_split,
            random_state=args.seed + idx,  # Different seed per class
            shuffle=True
        )
        
        # Process training files
        for src_file in train_files:
            base_name = os.path.basename(src_file)
            name_without_ext = os.path.splitext(base_name)[0]
            
            if args.resample:
                # Resample and save as WAV
                dst_file = os.path.join(species_train_dir, f"train_{name_without_ext}.wav")
                if resample_audio(src_file, dst_file):
                    stats['train_files'] += 1
            else:
                # Keep original format
                ext = os.path.splitext(src_file)[1]
                dst_file = os.path.join(species_train_dir, f"train_{name_without_ext}{ext}")
                copy_or_symlink(src_file, dst_file, use_copy=args.copy)
                stats['train_files'] += 1
        
        # Process test files
        for src_file in test_files:
            base_name = os.path.basename(src_file)
            name_without_ext = os.path.splitext(base_name)[0]
            
            if args.resample:
                # Resample and save as WAV
                dst_file = os.path.join(species_test_dir, f"test_{name_without_ext}.wav")
                if resample_audio(src_file, dst_file):
                    stats['test_files'] += 1
            else:
                # Keep original format
                ext = os.path.splitext(src_file)[1]
                dst_file = os.path.join(species_test_dir, f"test_{name_without_ext}{ext}")
                copy_or_symlink(src_file, dst_file, use_copy=args.copy)
                stats['test_files'] += 1
        
        # Store species details
        stats['species_details'].append({
            'name': species,
            'total': len(files),
            'train': len(train_files),
            'test': len(test_files)
        })
    
    # Verify train/test counts match
    expected_train = stats['total_files'] - int(stats['total_files'] * args.test_split)
    print(f"\n{'='*60}")
    print("DATASET PREPARATION COMPLETE")
    print("="*60)
    print(f"Total species processed: {stats['total_species']}")
    print(f"Total files processed: {stats['total_files']}")
    print(f"Training files: {stats['train_files']} (expected ~{expected_train})")
    print(f"Test files: {stats['test_files']} (expected ~{stats['total_files'] * args.test_split:.0f})")
    
    if stats['train_files'] + stats['test_files'] != stats['total_files']:
        print(f"⚠️ Warning: Some files may have failed during resampling")
    
    # Save metadata
    metadata = {
        'source': args.source,
        'output': args.output,
        'test_split': args.test_split,
        'seed': args.seed,
        'resampled': args.resample,
        'format': args.format,
        'total_species': stats['total_species'],
        'total_files': stats['total_files'],
        'train_files': stats['train_files'],
        'test_files': stats['test_files'],
        'species': stats['species_details']
    }
    
    import json
    with open(os.path.join(args.output, 'dataset_metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nMetadata saved to: {os.path.join(args.output, 'dataset_metadata.json')}")
    
    # Show sample of species
    print(f"\nSample of processed species (first 10):")
    for species in stats['species_details'][:10]:
        print(f"  - {species['name']}: {species['train']} train, {species['test']} test")
    
    if len(stats['species_details']) > 10:
        print(f"  ... and {len(stats['species_details']) - 10} more")
    
    print(f"\n✅ Dataset ready for training!")
    print(f"   Train directory: {train_dir}")
    print(f"   Test directory: {test_dir}")
    print(f"\nNext step: Run the training script:")
    print(f"   python train_perch.py --dataset {args.output} --output wildsound_model")

def main():
    args = parse_arguments()
    
    # Validate source directory
    if not os.path.exists(args.source):
        print(f"❌ Source directory '{args.source}' does not exist!")
        return
    
    # Confirm with user
    response = input(f"\nThis will create a prepared dataset in '{args.output}'. Continue? (y/n): ")
    if response.lower() != 'y':
        print("Exiting.")
        return
    
    prepare_dataset(args)

if __name__ == "__main__":
    main()