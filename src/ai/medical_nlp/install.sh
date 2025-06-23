#!/bin/bash

# Medical NLP Installation Script

echo "Installing Medical NLP Libraries..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Upgrade pip
pip install --upgrade pip

# Install PyTorch (CPU version by default, modify for GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install core requirements
pip install -r requirements.txt

# Download spaCy models
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_md

# Download NLTK data
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"

# Create necessary directories
mkdir -p models/biobert
mkdir -p models/scibert
mkdir -p models/clinical
mkdir -p data/medical_kb
mkdir -p data/terminologies

echo "Medical NLP libraries installation complete!"
echo ""
echo "Next steps:"
echo "1. Download BioBERT models from: https://github.com/dmis-lab/biobert"
echo "2. Download SciBERT models from: https://github.com/allenai/scibert"
echo "3. Configure UMLS API credentials in .env file"
echo "4. Download medical terminologies (ICD-10, SNOMED CT, RxNorm)"
