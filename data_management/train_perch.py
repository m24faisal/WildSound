#!/usr/bin/env python3
"""
Wild Sound - Animal Sound Identifier using YAMNet Embeddings
Builds embeddings from training set, validates on test set
"""

import os
import numpy as np
import tensorflow_hub as hub
import soundfile as sf
import resampy
from tqdm import tqdm
import pickle
import argparse
from sklearn.metrics import classification_report, accuracy_score

print("Loading YAMNet model...")
model = hub.load('https://tfhub.dev/google/yamnet/1')
print("✅ YAMNet loaded")

SR = 16000  # YAMNet expects 16kHz
LENGTH = 5 * SR

def load_audio(path):
    """Load and preprocess audio"""
    try:
        audio, sr = sf.read(path)
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        if sr != SR:
            audio = resampy.resample(audio, sr, SR)
        if len(audio) < LENGTH:
            audio = np.pad(audio, (0, LENGTH - len(audio)))
        else:
            audio = audio[:LENGTH]
        return audio.astype(np.float32)
    except:
        return np.zeros(LENGTH, dtype=np.float32)

def get_embedding(audio):
    """Get YAMNet embedding"""
    waveform = np.expand_dims(audio, axis=0)
    scores, embeddings, spectrogram = model(waveform)
    return embeddings.numpy()[0]

def build_class_embeddings(train_path):
    """Build average embedding for each class from training set"""
    
    classes = sorted([d for d in os.listdir(train_path) 
                     if os.path.isdir(os.path.join(train_path, d))])
    
    class_embeddings = {}
    class_samples = {}
    
    print(f"\nBuilding embeddings from {len(classes)} classes...")
    
    for class_name in tqdm(classes, desc="Processing training data"):
        class_dir = os.path.join(train_path, class_name)
        embeddings = []
        
        for file in os.listdir(class_dir):
            if file.endswith(('.wav', '.mp3')):
                file_path = os.path.join(class_dir, file)
                audio = load_audio(file_path)
                emb = get_embedding(audio)
                embeddings.append(emb)
        
        if embeddings:
            class_embeddings[class_name] = np.mean(embeddings, axis=0)
            class_samples[class_name] = len(embeddings)
    
    print(f"\n✅ Built embeddings for {len(class_embeddings)} classes")
    print(f"Total training samples: {sum(class_samples.values())}")
    
    return class_embeddings, classes

def evaluate_on_test_set(test_path, class_embeddings, classes):
    """Evaluate accuracy on test set"""
    
    print(f"\n{'='*60}")
    print("EVALUATING ON TEST SET")
    print(f"{'='*60}")
    
    true_labels = []
    predicted_labels = []
    confidences = []
    
    # Process each test file
    for class_name in tqdm(classes, desc="Processing test data"):
        class_dir = os.path.join(test_path, class_name)
        if not os.path.exists(class_dir):
            continue
            
        for file in os.listdir(class_dir):
            if file.endswith(('.wav', '.mp3')):
                file_path = os.path.join(class_dir, file)
                audio = load_audio(file_path)
                recording_emb = get_embedding(audio)
                
                # Find best match
                best_match = None
                best_score = -1
                
                for ref_class, ref_emb in class_embeddings.items():
                    similarity = np.dot(recording_emb, ref_emb) / (np.linalg.norm(recording_emb) * np.linalg.norm(ref_emb))
                    if similarity > best_score:
                        best_score = similarity
                        best_match = ref_class
                
                true_labels.append(class_name)
                predicted_labels.append(best_match)
                confidences.append(best_score)
    
    # Calculate accuracy
    accuracy = accuracy_score(true_labels, predicted_labels)
    
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Overall Accuracy: {accuracy:.2%}")
    print(f"Test samples: {len(true_labels)}")
    print(f"\nClassification Report (top 20 classes):")
    
    # Show report for top classes (limit to avoid huge output)
    unique_classes = np.unique(true_labels)
    if len(unique_classes) > 20:
        # Show only classes with most samples
        from collections import Counter
        top_classes = [c for c, _ in Counter(true_labels).most_common(20)]
        # Filter to top classes
        filtered_true = [t for t in true_labels if t in top_classes]
        filtered_pred = [p for p, t in zip(predicted_labels, true_labels) if t in top_classes]
        print(classification_report(filtered_true, filtered_pred, zero_division=0))
    else:
        print(classification_report(true_labels, predicted_labels, zero_division=0))
    
    print(f"\nAverage confidence: {np.mean(confidences):.2%}")
    
    return accuracy

def identify_sound(audio_file, class_embeddings):
    """Identify a single sound file"""
    audio = load_audio(audio_file)
    recording_emb = get_embedding(audio)
    
    best_match = None
    best_score = -1
    
    for class_name, class_emb in class_embeddings.items():
        similarity = np.dot(recording_emb, class_emb) / (np.linalg.norm(recording_emb) * np.linalg.norm(class_emb))
        if similarity > best_score:
            best_score = similarity
            best_match = class_name
    
    return best_match, best_score

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true', help='Build class embeddings')
    parser.add_argument('--train', default='dataset/train', help='Training data path')
    parser.add_argument('--test', default='dataset/test', help='Test data path')
    parser.add_argument('--output', default='class_embeddings.pkl', help='Output file')
    parser.add_argument('--identify', type=str, help='Identify a sound file')
    args = parser.parse_args()
    
    if args.build:
        # Build embeddings from training set
        class_embeddings, classes = build_class_embeddings(args.train)
        
        # Save embeddings
        with open(args.output, 'wb') as f:
            pickle.dump((class_embeddings, classes), f)
        print(f"✅ Saved to {args.output}")
        
        # Evaluate on test set
        if os.path.exists(args.test):
            evaluate_on_test_set(args.test, class_embeddings, classes)
        else:
            print(f"\n⚠️ Test set not found at {args.test}")
        
    elif args.identify:
        # Load embeddings
        if not os.path.exists(args.output):
            print(f"Error: {args.output} not found. Run --build first.")
            return
        
        with open(args.output, 'rb') as f:
            class_embeddings, classes = pickle.load(f)
        
        # Identify the sound
        match, confidence = identify_sound(args.identify, class_embeddings)
        print(f"\n🎵 Identified: {match}")
        print(f"Confidence: {confidence:.2%}")
        
    else:
        print("Usage:")
        print("  python identify.py --build               # Build embeddings and evaluate")
        print("  python identify.py --identify sound.wav  # Identify a sound file")

if __name__ == "__main__":
    main()