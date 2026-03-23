#!/usr/bin/env python3
"""
Wild Sound - Perch 2.0 Embedding Extraction
Using the correct method from Perch Hoplite examples
"""

import numpy as np
from perch_hoplite.zoo import model_configs
import soundfile as sf
import resampy
import os

print("Loading Perch 2.0 model...")
base_model = model_configs.load_model_by_name('perch_v2')
print("✅ Model loaded")

PERCH_INPUT_SR = 32000
PERCH_INPUT_LENGTH = 5 * PERCH_INPUT_SR

def load_audio(path):
    """Load and preprocess audio file"""
    try:
        audio, sr = sf.read(path)
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        if sr != PERCH_INPUT_SR:
            audio = resampy.resample(audio, sr, PERCH_INPUT_SR)
        if len(audio) < PERCH_INPUT_LENGTH:
            audio = np.pad(audio, (0, PERCH_INPUT_LENGTH - len(audio)))
        else:
            audio = audio[:PERCH_INPUT_LENGTH]
        audio = audio / (np.max(np.abs(audio)) + 1e-8)
        return audio.astype(np.float32)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return np.zeros(PERCH_INPUT_LENGTH, dtype=np.float32)

def get_embedding(audio):
    """Get embedding from Perch using the official method"""
    # According to Perch Hoplite docs, we need to use .embed() and then .numpy()
    # But since that's not working, let's try to use the model directly as a function
    try:
        # Method 1: Try calling as a function
        result = base_model(audio)
        emb = np.array(result)
    except:
        # Method 2: Try .embed() and then convert
        result = base_model.embed(audio)
        # The result might be a tensor that we need to evaluate
        emb = np.array(result)
    
    # Ensure it's flat
    if len(emb.shape) > 1:
        emb = emb.flatten()
    
    return emb.astype(np.float32)

# Test on a real file
test_path = "dataset/train/Domestic Dog"
if os.path.exists(test_path):
    for file in os.listdir(test_path)[:1]:
        if file.endswith(('.wav', '.mp3')):
            file_path = os.path.join(test_path, file)
            print(f"\nTesting on: {file_path}")
            
            audio = load_audio(file_path)
            print(f"Audio shape: {audio.shape}")
            
            emb = get_embedding(audio)
            print(f"Embedding shape: {emb.shape}")
            print(f"Embedding dtype: {emb.dtype}")
            print(f"First 10 values: {emb[:10]}")
            print("✅ Success!")
else:
    print(f"Test path not found: {test_path}")
    print("Please make sure your dataset is in the 'dataset' folder")