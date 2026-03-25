# fix_all_audio.py
"""
Fix all corrupted MP3 files in your dataset by converting them to WAV
Run this once and it will fix all your audio files
"""

import os
import subprocess
import shutil
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

def convert_mp3_to_wav(mp3_path):
    """Convert MP3 to WAV using ffmpeg"""
    wav_path = mp3_path.replace('.mp3', '.wav')
    try:
        # Use ffmpeg to convert, ignoring errors
        cmd = [
            'ffmpeg', '-i', mp3_path, 
            '-acodec', 'pcm_s16le', 
            '-ar', '32000',  # 32kHz for Perch
            '-ac', '1',      # mono
            '-y',            # overwrite
            wav_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if result.returncode == 0 and os.path.exists(wav_path):
            # Remove original MP3
            os.remove(mp3_path)
            return True
        return False
    except Exception as e:
        return False

def fix_dataset(dataset_path):
    """Convert all MP3 files in dataset to WAV"""
    
    total_fixed = 0
    total_failed = 0
    
    # Find all MP3 files
    mp3_files = []
    for root, dirs, files in os.walk(dataset_path):
        for file in files:
            if file.endswith('.mp3'):
                mp3_files.append(os.path.join(root, file))
    
    print(f"Found {len(mp3_files)} MP3 files to convert")
    
    for mp3_path in tqdm(mp3_files, desc="Converting MP3 to WAV"):
        if convert_mp3_to_wav(mp3_path):
            total_fixed += 1
        else:
            total_failed += 1
    
    print(f"\n✅ Fixed: {total_fixed}")
    print(f"❌ Failed: {total_failed}")
    
    return total_fixed, total_failed

# Run on both train and test
print("=" * 60)
print("FIXING TRAINING SET")
print("=" * 60)
fix_dataset('dataset/train')

print("\n" + "=" * 60)
print("FIXING TEST SET")
print("=" * 60)
fix_dataset('dataset/test')

print("\n✅ All files converted!")
print("Now run the embedding builder again.")