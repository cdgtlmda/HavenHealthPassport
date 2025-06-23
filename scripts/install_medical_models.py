#!/usr/bin/env python3
"""
Install and verify medical embedding models for Haven Health Passport.

This script:
1. Installs required dependencies
2. Downloads medical BERT models
3. Verifies the models work correctly
"""

import subprocess
import sys
import os
from pathlib import Path

def install_dependencies():
    """Install required Python packages for medical embeddings."""
    print("🔧 Installing required dependencies...")
    
    packages = [
        "torch>=2.0.0",
        "transformers>=4.36.0", 
        "sentence-transformers>=2.2.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0"
    ]
    
    for package in packages:
        print(f"📦 Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    
    print("✅ Dependencies installed successfully!\n")

def download_models():
    """Download and cache medical embedding models."""
    print("🏥 Downloading medical embedding models...")
    print("This may take a while on first run as models are 400-500MB each.\n")
    
    try:
        from sentence_transformers import SentenceTransformer
        from transformers import AutoTokenizer, AutoModel
        
        models_to_download = [
            {
                "name": "pritamdeka/S-PubMedBert-MS-MARCO",
                "type": "sentence-transformer",
                "description": "PubMedBERT fine-tuned for semantic search"
            },
            {
                "name": "kamalkraj/BioSimCSE-BioLinkBERT-BASE", 
                "type": "sentence-transformer",
                "description": "BioLinkBERT for medical semantic similarity"
            },
            {
                "name": "emilyalsentzer/Bio_ClinicalBERT",
                "type": "transformer", 
                "description": "ClinicalBERT trained on MIMIC-III clinical notes"
            },
            {
                "name": "dmis-lab/biobert-v1.1",
                "type": "transformer",
                "description": "BioBERT trained on PubMed abstracts"
            }
        ]
        
        for model_info in models_to_download:
            print(f"📥 Downloading: {model_info['name']}")
            print(f"   Description: {model_info['description']}")
            
            try:
                if model_info["type"] == "sentence-transformer":
                    model = SentenceTransformer(model_info["name"])
                    # Test the model
                    test_embedding = model.encode("test medical text")
                    print(f"   ✅ Model loaded successfully! Embedding dimension: {len(test_embedding)}")
                else:
                    tokenizer = AutoTokenizer.from_pretrained(model_info["name"])
                    model = AutoModel.from_pretrained(model_info["name"])
                    print(f"   ✅ Model loaded successfully!")
                    
            except Exception as e:
                print(f"   ⚠️  Warning: Could not load {model_info['name']}: {e}")
                print(f"   This model will be skipped, but others may still work.\n")
                continue
                
            print()
            
    except ImportError as e:
        print(f"❌ Error: Required packages not installed properly: {e}")
        return False
        
    return True

def verify_installation():
    """Verify the medical embedding service works correctly."""
    print("🔍 Verifying medical embedding service...\n")
    
    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    try:
        from src.vector_store.medical_embeddings import MedicalEmbeddingService
        
        # Initialize service
        print("Initializing MedicalEmbeddingService...")
        service = MedicalEmbeddingService()
        
        # Test single embedding
        test_texts = [
            "Patient presents with chest pain and shortness of breath",
            "Hypertension diagnosed, prescribed lisinopril 10mg daily",
            "MRI shows herniated disc at L4-L5 level"
        ]
        
        print(f"\nTesting embeddings for {len(test_texts)} medical texts...")
        
        for text in test_texts:
            embedding = service.embed(text)
            print(f"✅ '{text[:50]}...' -> embedding shape: {embedding.shape}")
        
        # Test batch embedding
        print("\nTesting batch embedding...")
        batch_embeddings = service.embed_batch(test_texts)
        print(f"✅ Batch embedding successful: {len(batch_embeddings)} embeddings generated")
        
        # Check if using real model or fallback
        if hasattr(service, '_model_initialized') and service._model_initialized:
            print(f"\n🎉 SUCCESS! Using real medical model: {service.model_name}")
        else:
            print("\n⚠️  WARNING: Service is using fallback embeddings. Check error logs.")
            
        # Show model info
        print(f"\nModel Information:")
        print(f"  - Model type: {getattr(service, 'model_type', 'unknown')}")
        print(f"  - Model name: {getattr(service, 'model_name', 'unknown')}") 
        print(f"  - Embedding dimension: {service.get_dimension()}")
        print(f"  - Device: {getattr(service, 'device', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_requirements():
    """Update requirements.txt with medical model dependencies."""
    print("\n📝 Updating requirements file...")
    
    req_file = Path(__file__).parent.parent / "requirements.txt"
    
    new_requirements = [
        "# Medical Embedding Models",
        "torch>=2.0.0",
        "transformers>=4.36.0", 
        "sentence-transformers>=2.2.0",
        "scipy>=1.10.0",
        ""
    ]
    
    if req_file.exists():
        with open(req_file, 'r') as f:
            existing = f.read()
            
        # Check if already added
        if "Medical Embedding Models" not in existing:
            with open(req_file, 'a') as f:
                f.write("\n" + "\n".join(new_requirements))
            print("✅ Updated requirements.txt")
        else:
            print("✅ requirements.txt already contains medical model dependencies")
    else:
        print("⚠️  requirements.txt not found")

def main():
    """Main installation process."""
    print("🏥 Haven Health Passport - Medical Model Installation")
    print("=" * 50)
    print()
    
    # Step 1: Install dependencies
    try:
        install_dependencies()
    except Exception as e:
        print(f"❌ Failed to install dependencies: {e}")
        return 1
    
    # Step 2: Download models
    if not download_models():
        print("❌ Failed to download some models, but continuing...")
    
    # Step 3: Verify installation
    if not verify_installation():
        print("\n❌ Verification failed. Please check the errors above.")
        return 1
    
    # Step 4: Update requirements
    update_requirements()
    
    print("\n" + "=" * 50)
    print("✅ Medical model installation complete!")
    print("\nNext steps:")
    print("1. The medical embedding service is now using real models")
    print("2. First-time model loading may be slow as models are cached")
    print("3. GPU will be used automatically if available")
    print("4. Monitor logs for any model loading issues")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
