# step1_slice_audio.py
"""
STEP 1: DATA PREPARATION FOR AI TRAINING
- Reads the youtube_smart_db folder.
- Slices all MP3s into exactly 3-second WAV chunks.
- Groups them by class for AI training (Hugging Face / Teachable Machine).
"""

import librosa
import soundfile as sf
from pathlib import Path
import random
import shutil

# ==========================================
# CONFIGURATION
# ==========================================
SOURCE_DIR = Path("youtube_smart_db")     # Where your downloaded MP3s are
OUTPUT_DIR = Path("ai_training_dataset")  # Where the sliced WAVs will go

CHUNK_DURATION = 3.0   # Length of each audio slice in seconds
SAMPLE_RATE = 16000    # Standard sample rate for Audio Spectrogram Transformers (AST)

# Mapping to clean up your folder names into standard AI labels
# Everything that isn't Domestic gets grouped into its broader animal class
CLASS_MAPPING = {
    "Aves": "Bird",
    "Amphibia": "Reptile_Amphibian",
    "Reptilia": "Reptile_Amphibian",
    "Mammalia": "Mammal",
    "Domestic": "Domestic",
    "Unknown": "Unknown"
}

def process_audio_file(mp3_path, output_folder):
    """Loads an MP3, slices it, and saves the chunks as WAV files."""
    
    # Load audio. sr=SAMPLE_RATE forces it to 16kHz (required by AST models)
    # We suppress the verbose librosa output using a try/except block workaround
    try:
        y, sr = librosa.load(mp3_path, sr=SAMPLE_RATE, mono=True)
    except Exception as e:
        print(f"         ⚠️ Corrupt MP3 skipped: {mp3_path.name}")
        return 0

    # Calculate how many samples are in 3 seconds
    chunk_samples = int(CHUNK_DURATION * sr)
    total_samples = len(y)
    
    chunks_saved = 0

    # Iterate through the audio in 3-second steps
    for i in range(0, total_samples, chunk_samples):
        chunk = y[i : i + chunk_samples]
        
        # Discard the very last chunk if it's less than 3 seconds (prevents AI errors)
        if len(chunk) < chunk_samples:
            continue

        # Create a unique filename based on original name and chunk number
        safe_name = mp3_path.stem.replace(" ", "_")
        out_path = output_folder / f"{safe_name}_chunk{chunks_saved}.wav"
        
        # Save as 16-bit WAV (standard for AI training)
        sf.write(out_path, chunk, sr, subtype='PCM_16')
        chunks_saved += 1

    return chunks_saved

def main():
    print("============================================================")
    print("STEP 1: SLICING AUDIO FOR AI TRAINING")
    print("============================================================\n")
    
    if not SOURCE_DIR.exists():
        print(f"❌ ERROR: Source directory '{SOURCE_DIR}' not found!")
        print("   Please run your download script first.")
        return

    # Create fresh output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_chunks = 0
    total_files_processed = 0

    # Find all MP3 files in the downloaded database
    all_mp3s = list(SOURCE_DIR.rglob("*.mp3"))
    print(f"📁 Found {len(all_mp3s)} total MP3 files to slice.\n")

    for mp3_path in all_mp3s:
        # Figure out the class based on the parent folder name
        raw_class = mp3_path.parent.name
        clean_class = CLASS_MAPPING.get(raw_class, "Unknown")
        
        # Create the output folder for this class
        class_output_folder = OUTPUT_DIR / clean_class
        class_output_folder.mkdir(parents=True, exist_ok=True)

        # Process the file
        chunks = process_audio_file(mp3_path, class_output_folder)
        total_chunks += chunks
        total_files_processed += 1

        # Print progress
        animal_name = mp3_path.stem.split("_")[0] # Get just the animal name
        print(f"  [{total_files_processed}/{len(all_mp3s)}] {animal_name:20} | {raw_class:15} -> {clean_class:20} | ✂️ {chunks} chunks")

    print("\n============================================================")
    print(f"✅ COMPLETE!")
    print(f"   Processed {total_files_processed} MP3s into {total_chunks} training chunks.")
    print(f"   Output saved to: ./{OUTPUT_DIR}/")
    print("============================================================")
    
    # Print final folder stats
    print("\n📊 Dataset Summary:")
    for class_folder in sorted(OUTPUT_DIR.iterdir()):
        count = len(list(class_folder.glob("*.wav")))
        print(f"   {class_folder.name}: {count} files")

if __name__ == "__main__":
    main()