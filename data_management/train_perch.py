#!/usr/bin/env python3
"""
Wild Sound - Perch 2.0 Fine-Tuning Script
Trains a linear classifier on top of Perch 2.0 embeddings for 667 animal species.
SIMPLIFIED VERSION - Better error handling and Perch verification
"""

import os
import sys
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import soundfile as sf
import resampy
import argparse
from tqdm import tqdm
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report
import json
import warnings
warnings.filterwarnings('ignore')

print(f"Python: {sys.version}")
print(f"PyTorch: {torch.__version__}")

# First, verify Perch installation
print("\nVerifying Perch Hoplite installation...")
try:
    import perch_hoplite
    print(f"✅ Perch Hoplite found at: {perch_hoplite.__file__}")
    
    from perch_hoplite.zoo import model_configs
    print("✅ Successfully imported model_configs")
    
    # Try to load the model (this will download if needed)
    print("Attempting to load Perch 2.0 model...")
    test_model = model_configs.load_model_by_name('perch_v2')
    print("✅ Perch 2.0 model loaded successfully!")
    
except ImportError as e:
    print(f"❌ Failed to import Perch Hoplite: {e}")
    print("\nPlease install it with:")
    print("pip install git+https://github.com/google-research/perch-hoplite.git")
    sys.exit(1)
except Exception as e:
    print(f"❌ Failed to load Perch model: {e}")
    print("\nMake sure you have Kaggle API credentials set up.")
    print("1. Go to https://www.kaggle.com/account")
    print("2. Create API token")
    print("3. Place kaggle.json in C:\\Users\\Mahir\\.kaggle\\")
    sys.exit(1)

# Set device
device = None
try:
    import torch_directml
    device = torch_directml.device()
    print(f"\nUsing DirectML device: {device}")
except ImportError:
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\nUsing device: {device}")

# ===================== CONFIGURATION =====================
DATASET_PATH = "dataset"                    # Path to prepared dataset
OUTPUT_DIR = "wildsound_model"               # Where to save the trained model
BATCH_SIZE = 16                              # Reduced for stability
EPOCHS = 50                                  # Training epochs
LEARNING_RATE = 0.001                        # Initial learning rate
PERCH_INPUT_SR = 32000                       # Perch expects 32kHz audio
PERCH_INPUT_LENGTH = 5 * PERCH_INPUT_SR      # 5 seconds of audio
NUM_WORKERS = 0                              # Set to 0 for Windows
# ==========================================================

class AnimalSoundDataset(Dataset):
    """Custom dataset for animal sounds compatible with Perch 2.0."""
    
    def __init__(self, root_dir):
        self.samples = []
        self.labels = []
        self.class_names = sorted([d for d in os.listdir(root_dir) 
                                   if os.path.isdir(os.path.join(root_dir, d))])
        self.class_to_idx = {cls_name: i for i, cls_name in enumerate(self.class_names)}
        
        print(f"\nLoading dataset from {root_dir}")
        print(f"Found {len(self.class_names)} classes")
        
        # Collect all audio files
        for class_name in self.class_names:
            class_dir = os.path.join(root_dir, class_name)
            if not os.path.exists(class_dir):
                continue
            for file in os.listdir(class_dir):
                if file.endswith(('.wav', '.mp3', '.m4a', '.3gp')):
                    file_path = os.path.join(class_dir, file)
                    self.samples.append((file_path, self.class_to_idx[class_name]))
        
        print(f"Total samples: {len(self.samples)}")
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        path, label = self.samples[idx]
        
        try:
            # Load audio file
            audio, sr = sf.read(path)
            
            # Convert to mono if stereo
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)
            
            # Resample if needed
            if sr != PERCH_INPUT_SR:
                audio = resampy.resample(audio, sr, PERCH_INPUT_SR)
            
            # Ensure exactly 5 seconds (pad or truncate)
            if len(audio) < PERCH_INPUT_LENGTH:
                audio = np.pad(audio, (0, PERCH_INPUT_LENGTH - len(audio)))
            else:
                audio = audio[:PERCH_INPUT_LENGTH]
            
            # Normalize audio
            audio = audio / (np.max(np.abs(audio)) + 1e-8)
            
            return torch.FloatTensor(audio), label
            
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return torch.zeros(PERCH_INPUT_LENGTH), label

class PerchClassifier(nn.Module):
    """
    Perch 2.0-based classifier with linear probing.
    """
    
    def __init__(self, num_classes, device):
        super().__init__()
        self.device = device
        self.num_classes = num_classes
        
        # Load Perch model (already verified in the verification step)
        from perch_hoplite.zoo import model_configs
        print("\nLoading Perch 2.0 base model...")
        self.base_model = model_configs.load_model_by_name('perch_v2')
        print("✅ Perch 2.0 loaded successfully")
        
        # Perch 2.0 outputs 1536-dim embeddings
        self.embedding_dim = 1536
        
        # Simple linear classifier on top of frozen embeddings
        self.classifier = nn.Sequential(
            nn.Linear(self.embedding_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes)
        ).to(device)
    
    def get_embeddings(self, waveforms):
        """
        Extract Perch 2.0 embeddings from audio waveforms.
        """
        embeddings = []
        
        # Process each sample in the batch
        for i in range(waveforms.shape[0]):
            # Get the numpy array for this sample
            waveform_np = waveforms[i].cpu().numpy()
            
            # Get embedding from Perch
            # Perch returns (embeddings, logits) tuple
            result = self.base_model.embed(waveform_np)
            
            if isinstance(result, tuple):
                # If it's a tuple, take the first element (embeddings)
                emb = result[0]
                if isinstance(emb, np.ndarray):
                    if len(emb.shape) > 1:
                        embeddings.append(emb[0])
                    else:
                        embeddings.append(emb)
                else:
                    embeddings.append(np.array(emb))
            else:
                # If it's not a tuple, assume it's the embedding
                if isinstance(result, np.ndarray):
                    if len(result.shape) > 1:
                        embeddings.append(result[0])
                    else:
                        embeddings.append(result)
                else:
                    embeddings.append(np.array(result))
        
        # Stack all embeddings into a batch
        embeddings = np.stack(embeddings, axis=0).astype(np.float32)
        return torch.FloatTensor(embeddings).to(self.device)
    
    def forward(self, waveforms):
        """Forward pass: waveforms -> embeddings -> logits."""
        with torch.no_grad():  # Freeze Perch base model
            embeddings = self.get_embeddings(waveforms)
        
        return self.classifier(embeddings)

def train_epoch(model, dataloader, criterion, optimizer, device, epoch):
    """Train for one epoch."""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    pbar = tqdm(dataloader, desc=f'Epoch {epoch}')
    for inputs, labels in pbar:
        inputs, labels = inputs.to(device), labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        running_loss += loss.item()
        _, predicted = torch.max(outputs, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()
        
        pbar.set_postfix({
            'loss': f'{running_loss/len(pbar):.4f}',
            'acc': f'{100.*correct/total:.2f}%'
        })
    
    return running_loss/len(dataloader), 100.*correct/total

def validate(model, dataloader, criterion, device):
    """Validate the model."""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for inputs, labels in tqdm(dataloader, desc='Validation'):
            inputs, labels = inputs.to(device), labels.to(device)
            
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            
            running_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            
            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
    
    return (running_loss/len(dataloader), 
            100.*correct/total,
            np.array(all_labels),
            np.array(all_preds))

def plot_training_history(train_losses, train_accs, val_losses, val_accs, output_dir):
    """Plot training curves."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    
    # Loss plot
    axes[0].plot(train_losses, label='Train Loss')
    axes[0].plot(val_losses, label='Val Loss')
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Loss')
    axes[0].set_title('Training and Validation Loss')
    axes[0].legend()
    axes[0].grid(True)
    
    # Accuracy plot
    axes[1].plot(train_accs, label='Train Acc')
    axes[1].plot(val_accs, label='Val Acc')
    axes[1].set_xlabel('Epoch')
    axes[1].set_ylabel('Accuracy (%)')
    axes[1].set_title('Training and Validation Accuracy')
    axes[1].legend()
    axes[1].grid(True)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'training_history.png'))
    plt.show()

def main():
    parser = argparse.ArgumentParser(description='Fine-tune Perch 2.0 on animal sounds')
    parser.add_argument('--dataset', default=DATASET_PATH, help='Path to dataset')
    parser.add_argument('--output', default=OUTPUT_DIR, help='Output directory')
    parser.add_argument('--epochs', type=int, default=EPOCHS, help='Number of epochs')
    parser.add_argument('--batch_size', type=int, default=BATCH_SIZE, help='Batch size')
    parser.add_argument('--lr', type=float, default=LEARNING_RATE, help='Learning rate')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"Using device: {device}")
    print(f"{'='*60}\n")
    
    # Load dataset
    train_path = os.path.join(args.dataset, 'train')
    test_path = os.path.join(args.dataset, 'test')
    
    if not os.path.exists(train_path):
        print(f"Error: Training directory not found at {train_path}")
        sys.exit(1)
    
    # Create datasets
    print("Loading training data...")
    train_dataset = AnimalSoundDataset(train_path)
    print("Loading test data...")
    test_dataset = AnimalSoundDataset(test_path)
    
    # Create data loaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=NUM_WORKERS,
        pin_memory=False
    )
    
    test_loader = DataLoader(
        test_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=NUM_WORKERS,
        pin_memory=False
    )
    
    # Save class labels
    with open(os.path.join(args.output, 'labels.txt'), 'w') as f:
        for class_name in train_dataset.class_names:
            f.write(f"{class_name}\n")
    
    print(f"\n{'='*60}")
    print(f"Training on {len(train_dataset.class_names)} classes")
    print(f"Train samples: {len(train_dataset)}")
    print(f"Test samples: {len(test_dataset)}")
    print(f"{'='*60}\n")
    
    # Initialize model
    model = PerchClassifier(len(train_dataset.class_names), device)
    
    # Loss and optimizer - Adam is correct, ignore IDE warning
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.classifier.parameters(), lr=args.lr)
    
    # Training history
    train_losses, train_accs = [], []
    val_losses, val_accs = [], []
    best_val_acc = 0.0
    
    print(f"\nStarting training for {args.epochs} epochs...")
    
    for epoch in range(1, args.epochs + 1):
        # Train
        train_loss, train_acc = train_epoch(
            model, train_loader, criterion, optimizer, device, epoch
        )
        train_losses.append(train_loss)
        train_accs.append(train_acc)
        
        # Validate
        val_loss, val_acc, _, _ = validate(model, test_loader, criterion, device)
        val_losses.append(val_loss)
        val_accs.append(val_acc)
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), os.path.join(args.output, 'best_model.pt'))
            print(f"✅ Saved best model with validation accuracy: {val_acc:.2f}%")
        
        print(f"Epoch {epoch}: Train Loss={train_loss:.4f}, Train Acc={train_acc:.2f}%, "
              f"Val Loss={val_loss:.4f}, Val Acc={val_acc:.2f}%\n")
    
    # Final evaluation
    print("\n" + "="*60)
    print("FINAL EVALUATION")
    print("="*60)
    
    # Load best model
    best_model_path = os.path.join(args.output, 'best_model.pt')
    if os.path.exists(best_model_path):
        model.load_state_dict(torch.load(best_model_path, map_location=device))
    
    val_loss, val_acc, all_labels, all_preds = validate(model, test_loader, criterion, device)
    
    print(f"\nBest validation accuracy: {best_val_acc:.2f}%")
    print(f"Final validation accuracy: {val_acc:.2f}%")
    
    # Save final model
    torch.save(model.state_dict(), os.path.join(args.output, 'final_model.pt'))
    
    # Plot training history
    plot_training_history(train_losses, train_accs, val_losses, val_accs, args.output)
    
    print(f"\n{'='*60}")
    print("TRAINING COMPLETE!")
    print("="*60)
    print(f"Model saved to: {args.output}/")
    print(f"  - best_model.pt")
    print(f"  - final_model.pt")
    print(f"  - labels.txt")
    print("="*60)

if __name__ == "__main__":
    main()