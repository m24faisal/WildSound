#!/usr/bin/env python3
"""
Wild Sound - Perch 2.0 Embedding Builder
Builds species-level embeddings from your dataset
"""

import os
import sys
import numpy as np
import soundfile as sf
import resampy
import pickle
import argparse
from tqdm import tqdm
import warnings
import logging

# Silence warnings
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger('tensorflow').setLevel(logging.ERROR)

print("Loading Perch 2.0 model...")
from perch_hoplite.zoo import model_configs
model = model_configs.load_model_by_name('perch_v2')
print("✅ Perch 2.0 loaded successfully")

# Audio configuration for Perch
SR = 32000  # Perch expects 32kHz
LENGTH = 5 * SR  # 5 seconds

def load_audio(path):
    """Load and preprocess audio for Perch"""
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
        return audio.astype(np.float32), True
    except Exception as e:
        return np.zeros(LENGTH, dtype=np.float32), False

def get_embedding(audio):
    """Get Perch 2.0 embedding"""
    result = model.embed(audio)
    if hasattr(result, 'embeddings') and result.embeddings is not None:
        emb = result.embeddings
    else:
        return np.zeros(1536, dtype=np.float32)
    
    # Flatten to 1D (1536,)
    if len(emb.shape) > 1:
        emb = emb.flatten()
    return emb.astype(np.float32)

def build_class_embeddings(train_path):
    """Build average embedding for each class from training set"""
    
    classes = sorted([d for d in os.listdir(train_path) 
                     if os.path.isdir(os.path.join(train_path, d))])
    
    class_embeddings = {}
    class_samples = {}
    
    print(f"\n{'='*60}")
    print(f"BUILDING PERCH 2.0 EMBEDDINGS")
    print(f"{'='*60}")
    print(f"Classes: {len(classes)}")
    print(f"Training path: {train_path}")
    
    for class_name in tqdm(classes, desc="Processing training data"):
        class_dir = os.path.join(train_path, class_name)
        embeddings = []
        skipped = 0
        
        for file in os.listdir(class_dir):
            if file.endswith(('.wav', '.mp3', '.m4a')):
                file_path = os.path.join(class_dir, file)
                audio, success = load_audio(file_path)
                if success:
                    emb = get_embedding(audio)
                    embeddings.append(emb)
                else:
                    skipped += 1
        
        if embeddings:
            class_embeddings[class_name] = np.mean(embeddings, axis=0)
            class_samples[class_name] = len(embeddings)
        else:
            print(f"⚠️ No valid files for: {class_name}")
    
    print(f"\n✅ Built embeddings for {len(class_embeddings)} classes")
    print(f"Total training samples processed: {sum(class_samples.values())}")
    
    return class_embeddings, classes

def evaluate_on_test_set(test_path, class_embeddings, classes):
    """Evaluate accuracy on test set"""
    
    print(f"\n{'='*60}")
    print("EVALUATING ON TEST SET")
    print(f"{'='*60}")
    
    true_labels = []
    predicted_labels = []
    confidences = []
    failed_files = 0
    
    for class_name in tqdm(classes, desc="Processing test data"):
        class_dir = os.path.join(test_path, class_name)
        if not os.path.exists(class_dir):
            continue
            
        for file in os.listdir(class_dir):
            if file.endswith(('.wav', '.mp3', '.m4a')):
                file_path = os.path.join(class_dir, file)
                audio, success = load_audio(file_path)
                
                if not success:
                    failed_files += 1
                    continue
                
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
    from sklearn.metrics import accuracy_score
    accuracy = accuracy_score(true_labels, predicted_labels)
    
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Overall Accuracy: {accuracy:.2%}")
    print(f"Test samples processed: {len(true_labels)}")
    if failed_files > 0:
        print(f"Failed files (skipped): {failed_files}")
    print(f"Average confidence: {np.mean(confidences):.2%}")
    
    return accuracy

def identify_sound(audio_file, class_embeddings, top_k=5):
    """Identify a single sound file"""
    audio, success = load_audio(audio_file)
    
    if not success:
        return "Error: Could not load audio file", 0.0, []
    
    recording_emb = get_embedding(audio)
    
    all_scores = []
    
    for class_name, class_emb in class_embeddings.items():
        similarity = np.dot(recording_emb, class_emb) / (np.linalg.norm(recording_emb) * np.linalg.norm(class_emb))
        all_scores.append((class_name, similarity))
    
    all_scores.sort(key=lambda x: x[1], reverse=True)
    
    best_match = all_scores[0][0]
    best_score = all_scores[0][1]
    top_matches = all_scores[:top_k]
    
    return best_match, best_score, top_matches

def main():
    parser = argparse.ArgumentParser(description='Perch 2.0 Animal Sound Identifier')
    parser.add_argument('--build', action='store_true', help='Build class embeddings from training set')
    parser.add_argument('--train', default='dataset/train', help='Path to training data')
    parser.add_argument('--test', default='dataset/test', help='Path to test data')
    parser.add_argument('--output', default='perch_embeddings.pkl', help='Output file for embeddings')
    parser.add_argument('--identify', type=str, help='Identify a sound file')
    parser.add_argument('--top', type=int, default=5, help='Show top N matches')
    args = parser.parse_args()
    
    if args.build:
        print("\n" + "="*60)
        print("WILD SOUND - PERCH 2.0 IDENTIFIER")
        print("="*60)
        
        if not os.path.exists(args.train):
            print(f"❌ Error: Training path not found: {args.train}")
            sys.exit(1)
        
        # Build embeddings
        class_embeddings, classes = build_class_embeddings(args.train)
        
        # Save embeddings
        with open(args.output, 'wb') as f:
            pickle.dump((class_embeddings, classes), f)
        print(f"\n✅ Saved embeddings to: {args.output}")
        
        # Evaluate on test set
        if os.path.exists(args.test):
            evaluate_on_test_set(args.test, class_embeddings, classes)
        else:
            print(f"\n⚠️ Test set not found at {args.test}")
        
        print("\n" + "="*60)
        print("To identify a sound file, run:")
        print(f"  python {sys.argv[0]} --identify your_sound.wav")
        print("="*60)
        
    elif args.identify:
        if not os.path.exists(args.output):
            print(f"❌ Error: {args.output} not found. Run with --build first.")
            sys.exit(1)
        
        if not os.path.exists(args.identify):
            print(f"❌ Error: Audio file not found: {args.identify}")
            sys.exit(1)
        
        with open(args.output, 'rb') as f:
            class_embeddings, classes = pickle.load(f)
        
        print(f"\n{'='*60}")
        print(f"Identifying: {args.identify}")
        print(f"{'='*60}")
        
        best_match, confidence, top_matches = identify_sound(args.identify, class_embeddings, args.top)
        
        if best_match.startswith("Error"):
            print(f"❌ {best_match}")
        else:
            print(f"\n🎵 Identified: {best_match}")
            print(f"Confidence: {confidence:.2%}")
            
            if args.top > 1:
                print(f"\nTop {args.top} matches:")
                for i, (name, score) in enumerate(top_matches):
                    print(f"  {i+1}. {name} ({score:.2%})")
        
        print("="*60)
        
    else:
        print("="*60)
        print("WILD SOUND - PERCH 2.0 IDENTIFIER")
        print("="*60)
        print("\nUsage:")
        print("  Build embeddings and evaluate:")
        print(f"    python {sys.argv[0]} --build --train dataset/train --test dataset/test")
        print("\n  Identify a sound file:")
        print(f"    python {sys.argv[0]} --identify recording.wav")
        print("="*60)

if __name__ == "__main__":
    main()