#!/usr/bin/env python3
"""
Wild Sound Model Trainer for Perch 2.0
Fine-tunes a linear classifier on top of Perch 2.0 embeddings for your 667 species.
Outputs: animal_classifier.tflite and labels.txt for Android integration.
"""

import os
import sys
import shutil
import random
import glob
import numpy as np
import tensorflow as tf
import soundfile as sf
import resampy
from pathlib import Path
from sklearn.model_selection import train_test_split
import argparse

print(f"TensorFlow Version: {tf.__version__}")

# ===================== CONFIGURATION =====================
DATASET_PATH = "animal_sounds"          # Path to your downloaded dataset
OUTPUT_DIR = "trained_perch_model"      # Where to save the final model
TEST_SPLIT = 0.2                         # 20% for testing
BATCH_SIZE = 32                           # Adjust based on your GPU memory
EPOCHS = 50                               # Start with 50 epochs
PERCH_INPUT_SR = 32000                    # Perch expects 32kHz audio
PERCH_INPUT_LENGTH = 5 * PERCH_INPUT_SR   # 5 seconds of audio
# ==========================================================

def prepare_dataset(audio_root, output_dir, test_size=0.2):
    """
    Prepare the dataset by:
    1. Organizing files by species
    2. Resampling audio to 32kHz
    3. Splitting into train/test sets
    """
    print("\n" + "="*60)
    print("STEP 1: PREPARING DATASET FOR PERCH 2.0")
    print("="*60)
    
    # Create output directories
    train_dir = os.path.join(output_dir, "train")
    test_dir = os.path.join(output_dir, "test")
    os.makedirs(train_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)
    
    # Collect all audio files and their species labels
    species_files = {}
    total_files = 0
    
    for root, dirs, files in os.walk(audio_root):
        if "metadata.json" in files:
            continue
        for file in files:
            if file.endswith(('.mp3', '.wav', '.m4a', '.3gp')):
                # Extract species name from path
                # Path format: .../continent/category/scientific_name/audio_file
                path_parts = Path(root).parts
                if len(path_parts) >= 2:
                    species_name = path_parts[-1].replace("_", " ")
                    file_path = os.path.join(root, file)
                    
                    if species_name not in species_files:
                        species_files[species_name] = []
                    species_files[species_name].append(file_path)
                    total_files += 1
    
    print(f"Found {len(species_files)} species with {total_files} total files")
    
    # Process each species
    species_list = sorted(species_files.keys())
    successful_species = 0
    
    for idx, species in enumerate(species_list):
        files = species_files[species]
        
        # Skip species with too few files
        if len(files) < 2:
            print(f"  Skipping {species}: only {len(files)} file(s)")
            continue
            
        # Create species directories
        species_train_dir = os.path.join(train_dir, species)
        species_test_dir = os.path.join(test_dir, species)
        os.makedirs(species_train_dir, exist_ok=True)
        os.makedirs(species_test_dir, exist_ok=True)
        
        # Split files
        train_files, test_files = train_test_split(
            files, test_size=test_size, random_state=42
        )
        
        # Process training files
        for src_file in train_files:
            dst_file = os.path.join(
                species_train_dir, 
                f"train_{os.path.basename(src_file).split('.')[0]}.wav"
            )
            try:
                # Load and resample audio
                audio, sr = sf.read(src_file)
                if len(audio.shape) > 1:
                    audio = audio.mean(axis=1)  # Convert to mono
                
                # Resample to 32kHz
                if sr != PERCH_INPUT_SR:
                    audio = resampy.resample(audio, sr, PERCH_INPUT_SR)
                
                # Ensure exactly 5 seconds (pad or truncate)
                if len(audio) < PERCH_INPUT_LENGTH:
                    audio = np.pad(audio, (0, PERCH_INPUT_LENGTH - len(audio)))
                else:
                    audio = audio[:PERCH_INPUT_LENGTH]
                
                # Save as WAV
                sf.write(dst_file, audio, PERCH_INPUT_SR)
                
            except Exception as e:
                print(f"    Error processing {src_file}: {e}")
        
        # Process test files (same logic)
        for src_file in test_files:
            dst_file = os.path.join(
                species_test_dir, 
                f"test_{os.path.basename(src_file).split('.')[0]}.wav"
            )
            try:
                audio, sr = sf.read(src_file)
                if len(audio.shape) > 1:
                    audio = audio.mean(axis=1)
                if sr != PERCH_INPUT_SR:
                    audio = resampy.resample(audio, sr, PERCH_INPUT_SR)
                if len(audio) < PERCH_INPUT_LENGTH:
                    audio = np.pad(audio, (0, PERCH_INPUT_LENGTH - len(audio)))
                else:
                    audio = audio[:PERCH_INPUT_LENGTH]
                sf.write(dst_file, audio, PERCH_INPUT_SR)
            except Exception as e:
                print(f"    Error processing {src_file}: {e}")
        
        successful_species += 1
        if (idx + 1) % 50 == 0:
            print(f"  Processed {idx + 1}/{len(species_list)} species...")
    
    print(f"\n✅ Dataset prepared: {successful_species} species")
    print(f"   Train: {train_dir}")
    print(f"   Test: {test_dir}")
    
    return train_dir, test_dir, successful_species

def build_perch_model(num_classes):
    """
    Build a model using Perch 2.0 embeddings + a new classification head.
    """
    print("\n" + "="*60)
    print("STEP 2: BUILDING PERCH 2.0 MODEL")
    print("="*60)
    
    try:
        # Install perch_hoplite if not already installed
        import perch_hoplite
    except ImportError:
        print("Installing perch_hoplite from GitHub...")
        os.system("pip install git+https://github.com/google-research/perch-hoplite.git")
        import perch_hoplite
    
    from perch_hoplite.zoo import model_configs
    
    print("Loading Perch 2.0 base model...")
    # This downloads the model from Kaggle (requires Kaggle API credentials)
    base_model = model_configs.load_model_by_name('perch_v2')
    
    # Perch 2.0 uses an EfficientNet-B3 backbone and outputs 1536-dim embeddings [citation:1][citation:4]
    # We'll create a new model that uses Perch's embedding output
    
    # Create a Keras model that uses Perch's embedding function
    input_layer = tf.keras.layers.Input(shape=(PERCH_INPUT_LENGTH,), name="audio_waveform")
    
    # Wrap the Perch embedding function in a Lambda layer
    def perch_embedding_fn(waveform):
        # waveform shape: (batch, 160000)
        # Convert to list of numpy arrays for Perch's embed method
        embeddings = tf.numpy_function(
            lambda x: np.array([base_model.embed(w)[0] for w in x]),
            [waveform],
            tf.float32
        )
        embeddings.set_shape((None, 1536))  # Perch outputs 1536-dim embeddings [citation:1]
        return embeddings
    
    embeddings = tf.keras.layers.Lambda(perch_embedding_fn)(input_layer)
    
    # Add a simple classification head on top of the frozen embeddings
    x = tf.keras.layers.Dense(512, activation='relu')(embeddings)
    x = tf.keras.layers.Dropout(0.3)(x)
    x = tf.keras.layers.Dense(256, activation='relu')(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation='softmax')(x)
    
    model = tf.keras.Model(inputs=input_layer, outputs=outputs)
    
    # Freeze the Perch embedding layers (only train the new classification head)
    # The Lambda layer doesn't have trainable weights, so we're good
    
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    
    model.summary()
    print(f"✅ Perch 2.0 model built with {num_classes} output classes")
    
    return model

def train_model(model, train_dir, test_dir):
    """
    Train the classification head using the prepared dataset.
    """
    print("\n" + "="*60)
    print("STEP 3: TRAINING CLASSIFICATION HEAD")
    print("="*60)
    
    # Create TensorFlow datasets
    train_ds = tf.keras.preprocessing.image_dataset_from_directory(
        train_dir,
        labels='inferred',
        label_mode='int',  # Sparse labels
        batch_size=BATCH_SIZE,
        shuffle=True,
        seed=42,
        validation_split=None
    )
    
    test_ds = tf.keras.preprocessing.image_dataset_from_directory(
        test_dir,
        labels='inferred',
        label_mode='int',
        batch_size=BATCH_SIZE,
        shuffle=False,
        seed=42,
        validation_split=None
    )
    
    # Get class names
    class_names = train_ds.class_names
    print(f"Training on {len(class_names)} classes")
    
    # Save class names for later
    with open(os.path.join(OUTPUT_DIR, "labels.txt"), 'w') as f:
        for name in class_names:
            f.write(f"{name}\n")
    
    # Train the model
    print(f"\nStarting training for {EPOCHS} epochs...")
    print(f"Estimated time on RX 6600: 2-4 hours")
    
    history = model.fit(
        train_ds,
        validation_data=test_ds,
        epochs=EPOCHS,
        callbacks=[
            tf.keras.callbacks.ModelCheckpoint(
                os.path.join(OUTPUT_DIR, 'best_model.h5'),
                save_best_only=True,
                monitor='val_accuracy',
                mode='max'
            ),
            tf.keras.callbacks.EarlyStopping(
                monitor='val_accuracy',
                patience=10,
                restore_best_weights=True
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5,
                min_lr=1e-6
            )
        ]
    )
    
    # Evaluate final model
    print("\n" + "="*60)
    print("EVALUATION RESULTS")
    print("="*60)
    test_loss, test_acc = model.evaluate(test_ds)
    print(f"Test accuracy: {test_acc:.4f}")
    print(f"Test loss: {test_loss:.4f}")
    
    return model, class_names, history

def convert_to_tflite(model, class_names, output_dir):
    """
    Convert the trained Keras model to TensorFlow Lite format.
    """
    print("\n" + "="*60)
    print("STEP 4: CONVERTING TO TFLITE")
    print("="*60)
    
    # Convert the model to TFLite
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]  # Use FP16 for smaller size
    
    tflite_model = converter.convert()
    
    # Save the TFLite model
    tflite_path = os.path.join(output_dir, 'animal_classifier.tflite')
    with open(tflite_path, 'wb') as f:
        f.write(tflite_model)
    
    # Also save the full Keras model for reference
    model.save(os.path.join(output_dir, 'full_model.h5'))
    
    print(f"✅ TFLite model saved to: {tflite_path}")
    print(f"   Size: {os.path.getsize(tflite_path) / 1024 / 1024:.2f} MB")
    
    return tflite_path

def main():
    parser = argparse.ArgumentParser(description='Train Perch 2.0 model on animal sounds')
    parser.add_argument('--dataset', default=DATASET_PATH,
                        help='Path to animal_sounds dataset')
    parser.add_argument('--output', default=OUTPUT_DIR,
                        help='Output directory for trained model')
    parser.add_argument('--epochs', type=int, default=EPOCHS,
                        help='Number of training epochs')
    parser.add_argument('--batch_size', type=int, default=BATCH_SIZE,
                        help='Batch size for training')
    
    args = parser.parse_args()
    
    global DATASET_PATH, OUTPUT_DIR, EPOCHS, BATCH_SIZE
    DATASET_PATH = args.dataset
    OUTPUT_DIR = args.output
    EPOCHS = args.epochs
    BATCH_SIZE = args.batch_size
    
    print("="*60)
    print("WILD SOUND PERCH 2.0 TRAINER")
    print("="*60)
    print(f"Dataset: {DATASET_PATH}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Epochs: {EPOCHS}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Estimated time on RX 6600: {int(EPOCHS * 0.08)} minutes")
    print("="*60)
    
    # Confirm before starting
    response = input("\nStart training? This will take several hours. (y/n): ")
    if response.lower() != 'y':
        print("Exiting.")
        return
    
    # Step 1: Prepare dataset
    processed_dir = os.path.join(OUTPUT_DIR, "processed_audio")
    train_dir, test_dir, num_species = prepare_dataset(
        DATASET_PATH, processed_dir, test_size=TEST_SPLIT
    )
    
    if num_species == 0:
        print("Error: No valid species found in dataset")
        return
    
    # Step 2: Build model
    model = build_perch_model(num_species)
    
    # Step 3: Train model
    model, class_names, history = train_model(model, train_dir, test_dir)
    
    # Step 4: Convert to TFLite
    tflite_path = convert_to_tflite(model, class_names, OUTPUT_DIR)
    
    print("\n" + "="*60)
    print("TRAINING COMPLETE!")
    print("="*60)
    print(f"Model files saved to: {OUTPUT_DIR}/")
    print("   - animal_classifier.tflite (for Android)")
    print("   - labels.txt (class names in order)")
    print("   - full_model.h5 (Keras model for reference)")
    print("\nNext steps:")
    print("1. Copy animal_classifier.tflite to your Android app's assets folder")
    print("2. Copy labels.txt to your Android app's assets folder")
    print("3. Update your Android code to use the model")
    print("\nHappy coding! 🎉")

if __name__ == "__main__":
    main()