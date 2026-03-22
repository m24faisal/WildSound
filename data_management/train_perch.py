#!/usr/bin/env python3
"""
Wild Sound - Perch 2.0 Fine-Tuning Script
Trains a linear classifier on top of Perch 2.0 embeddings for animal species.
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

class AnimalSoundDataset(Dataset):
    def __init__(self, root_dir):
        self.samples = []
        self.class_names = sorted([d for d in os.listdir(root_dir) 
                                   if os.path.isdir(os.path.join(root_dir, d))])
        self.class_to_idx = {name: i for i, name in enumerate(self.class_names)}
        
        print(f"\nLoading from {root_dir}")
        print(f"Found {len(self.class_names)} classes")
        
        for class_name in self.class_names:
            class_dir = os.path.join(root_dir, class_name)
            for file in os.listdir(class_dir):
                if file.endswith(('.wav', '.mp3', '.m4a')):
                    self.samples.append((os.path.join(class_dir, file), self.class_to_idx[class_name]))
        
        print(f"Total samples: {len(self.samples)}")
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        path, label = self.samples[idx]
        
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
            return torch.FloatTensor(audio), label
        except:
            return torch.zeros(PERCH_INPUT_LENGTH), label

class PerchClassifier(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.num_classes = num_classes
        self.embedding_dim = 1536
        
        self.classifier = nn.Sequential(
            nn.Linear(self.embedding_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes)
        )
    
    def get_embeddings(self, waveforms):
        embeddings = []
        for i in range(waveforms.shape[0]):
            result = base_model.embed(waveforms[i].cpu().numpy())
            if isinstance(result, tuple):
                emb = result[0]
                if isinstance(emb, np.ndarray):
                    embeddings.append(emb[0] if len(emb.shape) > 1 else emb)
                else:
                    embeddings.append(np.array(emb))
            else:
                if isinstance(result, np.ndarray):
                    embeddings.append(result[0] if len(result.shape) > 1 else result)
                else:
                    embeddings.append(np.array(result))
        embeddings = np.stack(embeddings, axis=0).astype(np.float32)
        return torch.FloatTensor(embeddings).to(waveforms.device)
    
    def forward(self, waveforms):
        with torch.no_grad():
            embeddings = self.get_embeddings(waveforms)
        return self.classifier(embeddings)

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
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for inputs, labels in tqdm(loader, desc='Validation'):
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            
            running_loss += loss.item()
            _, pred = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (pred == labels).sum().item()
            all_preds.extend(pred.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
    
    return running_loss/len(loader), 100.*correct/total, np.array(all_labels), np.array(all_preds)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', default='dataset', help='Path to dataset')
    parser.add_argument('--output', default='wildsound_model', help='Output directory')
    parser.add_argument('--epochs', type=int, default=50, help='Number of epochs')
    parser.add_argument('--batch_size', type=int, default=16, help='Batch size')
    parser.add_argument('--lr', type=float, default=0.001, help='Learning rate')
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"WILD SOUND - PERCH 2.0 TRAINING")
    print(f"Device: {device}")
    print(f"Dataset: {args.dataset}")
    print(f"Output: {args.output}")
    print(f"Epochs: {args.epochs}")
    print(f"Batch size: {args.batch_size}")
    print(f"{'='*60}\n")
    
    # Load data
    train_path = os.path.join(args.dataset, 'train')
    test_path = os.path.join(args.dataset, 'test')
    
    if not os.path.exists(train_path):
        print(f"Error: Training directory not found at {train_path}")
        print("Run prepare_dataset.py first")
        sys.exit(1)
    
    print("Loading training data...")
    train_dataset = AnimalSoundDataset(train_path)
    print("Loading test data...")
    test_dataset = AnimalSoundDataset(test_path)
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=NUM_WORKERS)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=NUM_WORKERS)
    
    # Save labels
    with open(os.path.join(args.output, 'labels.txt'), 'w') as f:
        for name in train_dataset.class_names:
            f.write(f"{name}\n")
    
    print(f"\n{'='*60}")
    print(f"Training on {len(train_dataset.class_names)} classes")
    print(f"Train samples: {len(train_dataset)}")
    print(f"Test samples: {len(test_dataset)}")
    print(f"{'='*60}\n")
    
    # Model
    model = PerchClassifier(len(train_dataset.class_names)).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = Adam(model.classifier.parameters(), lr=args.lr)
    
    train_losses, train_accs = [], []
    val_losses, val_accs = [], []
    best_acc = 0.0
    
    print(f"Starting training for {args.epochs} epochs...\n")
    
    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device, epoch)
        val_loss, val_acc, _, _ = validate(model, test_loader, criterion, device)
        
        train_losses.append(train_loss)
        train_accs.append(train_acc)
        val_losses.append(val_loss)
        val_accs.append(val_acc)
        
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), os.path.join(args.output, 'best_model.pt'))
            print(f"\n✅ Saved best model with accuracy: {val_acc:.2f}%")
        
        print(f"Epoch {epoch}: Train Loss={train_loss:.4f}, Train Acc={train_acc:.2f}%, "
              f"Val Loss={val_loss:.4f}, Val Acc={val_acc:.2f}%\n")
    
    # Save final model
    torch.save(model.state_dict(), os.path.join(args.output, 'final_model.pt'))
    
    # Save stats
    stats = {
        'best_acc': float(best_acc),
        'train_losses': [float(x) for x in train_losses],
        'train_accs': [float(x) for x in train_accs],
        'val_losses': [float(x) for x in val_losses],
        'val_accs': [float(x) for x in val_accs]
    }
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