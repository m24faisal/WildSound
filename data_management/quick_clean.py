# quick_clean.py
"""
Quick script to delete all corrupted audio files
"""

import os
import shutil
from pathlib import Path

def quick_clean(dataset_path="dataset"):
    """Delete all audio files and start fresh"""
    
    print("⚠️ WARNING: This will delete ALL audio files in the dataset!")
    response = input("Type 'DELETE ALL' to confirm: ")
    
    if response != "DELETE ALL":
        print("Operation cancelled.")
        return
    
    # Delete all audio files
    audio_extensions = ['.wav', '.mp3', '.m4a', '.ogg', '.flac']
    deleted_count = 0
    
    for root, dirs, files in os.walk(dataset_path):
        for file in files:
            if any(file.lower().endswith(ext) for ext in audio_extensions):
                filepath = os.path.join(root, file)
                os.remove(filepath)
                deleted_count += 1
    
    print(f"✅ Deleted {deleted_count} audio files")
    
    # Remove empty directories
    for root, dirs, files in os.walk(dataset_path, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    print(f"  Removed empty directory: {dir_path}")
            except:
                pass

if __name__ == "__main__":
    quick_clean()