# quick_clean_animalsounds.py
"""
Quick script to delete all corrupted audio files from animal_sounds
"""

import os
import soundfile as sf
from tqdm import tqdm

def quick_clean_animalsounds(animalsounds_path="animal_sounds"):
    """Delete all corrupted audio files from animal_sounds"""
    
    print("⚠️ WARNING: This will delete ALL corrupted audio files!")
    response = input("Type 'DELETE CORRUPTED' to confirm: ")
    
    if response != "DELETE CORRUPTED":
        print("Operation cancelled.")
        return
    
    # Find all audio files
    audio_files = []
    for root, dirs, files in os.walk(animalsounds_path):
        for file in files:
            if file.lower().endswith(('.wav', '.mp3', '.m4a')):
                audio_files.append(os.path.join(root, file))
    
    print(f"Found {len(audio_files)} total audio files")
    
    deleted = 0
    valid = 0
    
    for filepath in tqdm(audio_files, desc="Checking files"):
        try:
            audio, sr = sf.read(filepath)
            if len(audio) > 0:
                valid += 1
            else:
                os.remove(filepath)
                deleted += 1
        except:
            os.remove(filepath)
            deleted += 1
    
    print(f"\n✅ Deleted {deleted} corrupted files")
    print(f"✅ Kept {valid} valid files")
    
    # Remove empty directories
    for root, dirs, files in os.walk(animalsounds_path, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    print(f"  Removed empty directory: {dir_path}")
            except:
                pass

if __name__ == "__main__":
    quick_clean_animalsounds()