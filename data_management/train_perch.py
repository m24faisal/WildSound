#!/usr/bin/env python3
"""
Wild Sound - Pre-compute embeddings then train
Step 1: Compute Perch embeddings for all audio files
Step 2: Train classifier on embeddings
"""

import os
import sys
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim.adam import Adam
import soundfile as sf
import resampy
import argparse
from tqdm import tqdm
import json
import pickle
import warnings
warnings.filterwarnings('ignore')

print(f"Python: {sys.version}")
print(f"PyTorch: {torch.__version__}")

# Set device
device = None
try:
    import torch_directml
    device = torch_directml.device()
    print(f"✅ Using AMD GPU: {device}")
except ImportError:
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"✅ Using device: {device}")

# Load Perch model
print("\nLoading Perch 2.0 model...")
from perch_hoplite.zoo import model_configs
base_model = model_configs.load_model_by_name('perch_v2')
print("✅ Perch 2.0 loaded successfully")

# ===================== CONFIGURATION =====================
PERCH_INPUT_SR = 32000
PERCH_INPUT_LENGTH = 5 * PERCH_INPUT_SR
NUM_WORKERS = 0
# ==========================================================

def load_audio(path):
    """Load and preprocess audio file for Perch"""
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
        return np.zeros(PERCH_INPUT_LENGTH, dtype=np.float32)

def get_embedding(waveform):
    """Get embedding from Perch"""
    # Convert to numpy if needed
    if isinstance(waveform, torch.Tensor):
        waveform = waveform.cpu().numpy()
    
    # Call Perch embed
    result = base_model.embed(waveform)
    
    # Perch returns a tuple (embeddings, logits)
    # Let's try to get the first element safely
    try:
        emb = result[0]
    except:
        emb = result
    
    # Convert to numpy array if needed
    if hasattr(emb, 'numpy'):
        emb = emb.numpy()
    
    # Ensure 1D array
    if hasattr(emb, 'flatten'):
        emb = emb.flatten()
    elif isinstance(emb, (list, tuple)):
        emb = np.array(emb).flatten()
    else:
        emb = np.array(emb).flatten()
    
    return emb.astype(np.float32)

def compute_embeddings_for_split(split_dir, split_name, cache_file):
    """Compute embeddings for all files in a split"""
    if os.path.exists(cache_file):
        print(f"Loading cached embeddings from {cache_file}")
        with open(cache_file, 'rb') as f:
            return pickle.load(f)
    
    print(f"\nComputing embeddings for {split_name} split...")
    
    # Get all files
    class_names = sorted([d for d in os.listdir(split_dir) 
                          if os.path.isdir(os.path.join(split_dir, d))])
    class_to_idx = {name: i for i, name in enumerate(class_names)}
    
    samples = []
    for class_name in class_names:
        class_dir = os.path.join(split_dir, class_name)
        for file in os.listdir(class_dir):
            if file.endswith(('.wav', '.mp3', '.m4a')):
                samples.append((os.path.join(class_dir, file), class_to_idx[class_name]))
    
    print(f"Found {len(samples)} samples in {len(class_names)} classes")
    
    # Compute embeddings
    embeddings = []
    labels = []
    
    for file_path, label in tqdm(samples, desc=f"Computing embeddings for {split_name}"):
        audio = load_audio(file_path)
        emb = get_embedding(audio)
        embeddings.append(emb)
        labels.append(label)
    
    embeddings = np.array(embeddings, dtype=np.float32)
    labels = np.array(labels, dtype=np.int64)
    
    print(f"Embeddings shape: {embeddings.shape}")
    
    # Save cache
    with open(cache_file, 'wb') as f:
        pickle.dump((embeddings, labels, class_names), f)
    
    return embeddings, labels, class_names

class EmbeddingDataset(Dataset):
    def __init__(self, embeddings, labels):
        self.embeddings = torch.FloatTensor(embeddings)
        self.labels = torch.LongTensor(labels)
    
    def __len__(self):
        return len(self.labels)
    
    def __getitem__(self, idx):
        return self.embeddings[idx], self.labels[idx]

class Classifier(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.classifier = nn.Sequential(
            nn.Linear(1536, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes)
        )
    
    def forward(self, x):
        return self.classifier(x)

def train_epoch(model, loader, criterion, optimizer, device, epoch):
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    pbar = tqdm(loader, desc=f'Epoch {epoch}')
    for inputs, labels in pbar:
        inputs, labels = inputs.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        running_loss += loss.item()
        _, pred = torch.max(outputs, 1)
        total += labels.size(0)
        correct += (pred == labels).sum().item()
        
        pbar.set_postfix({'loss': f'{running_loss/len(pbar):.4f}', 
                         'acc': f'{100.*correct/total:.2f}%'})
    
    return running_loss/len(loader), 100.*correct/total

def validate(model, loader, criterion, device):
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    
    with torch.no_grad():
        for inputs, labels in tqdm(loader, desc='Validation'):
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            
            running_loss += loss.item()
            _, pred = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (pred == labels).sum().item()
    
    return running_loss/len(loader), 100.*correct/total

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', default='dataset', help='Path to dataset')
    parser.add_argument('--output', default='wildsound_model', help='Output directory')
    parser.add_argument('--epochs', type=int, default=50, help='Number of epochs')
    parser.add_argument('--batch_size', type=int, default=32, help='Batch size')
    parser.add_argument('--lr', type=float, default=0.001, help='Learning rate')
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"WILD SOUND - EMBEDDING-BASED TRAINING")
    print(f"Device: {device}")
    print(f"Dataset: {args.dataset}")
    print(f"Output: {args.output}")
    print(f"{'='*60}\n")
    
    # Compute embeddings for train and test
    train_emb, train_labels, class_names = compute_embeddings_for_split(
        os.path.join(args.dataset, 'train'),
        'train',
        os.path.join(args.output, 'train_embeddings.pkl')
    )
    
    test_emb, test_labels, _ = compute_embeddings_for_split(
        os.path.join(args.dataset, 'test'),
        'test',
        os.path.join(args.output, 'test_embeddings.pkl')
    )
    
    # Create datasets
    train_dataset = EmbeddingDataset(train_emb, train_labels)
    test_dataset = EmbeddingDataset(test_emb, test_labels)
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)
    
    # Save labels
    with open(os.path.join(args.output, 'labels.txt'), 'w') as f:
        for name in class_names:
            f.write(f"{name}\n")
    
    print(f"\n{'='*60}")
    print(f"Training on {len(class_names)} classes")
    print(f"Train samples: {len(train_dataset)}")
    print(f"Test samples: {len(test_dataset)}")
    print(f"Embedding dim: 1536")
    print(f"{'='*60}\n")
    
    # Model
    model = Classifier(len(class_names)).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = Adam(model.parameters(), lr=args.lr)
    
    best_acc = 0.0
    
    print(f"Starting training for {args.epochs} epochs...\n")
    
    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device, epoch)
        val_loss, val_acc = validate(model, test_loader, criterion, device)
        
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), os.path.join(args.output, 'best_model.pt'))
            print(f"\n✅ Saved best model with accuracy: {val_acc:.2f}%")
        
        print(f"Epoch {epoch}: Train Loss={train_loss:.4f}, Train Acc={train_acc:.2f}%, "
              f"Val Loss={val_loss:.4f}, Val Acc={val_acc:.2f}%\n")
    
    # Save final model
    torch.save(model.state_dict(), os.path.join(args.output, 'final_model.pt'))
    
    # Save stats
    stats = {'best_acc': float(best_acc)}
    with open(os.path.join(args.output, 'training_stats.json'), 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"\n{'='*60}")
    print("TRAINING COMPLETE!")
    print(f"{'='*60}")
    print(f"Best validation accuracy: {best_acc:.2f}%")
    print(f"Model saved to: {args.output}/")
    print(f"  - best_model.pt")
    print(f"  - final_model.pt")
    print(f"  - labels.txt")
    print("="*60)

if __name__ == "__main__":
    main()