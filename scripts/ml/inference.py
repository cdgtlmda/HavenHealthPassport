#!/usr/bin/env python3
"""
Inference script for cultural adaptation model.
This script is used by SageMaker for real-time inference.
"""

import json
import logging
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

logger = logging.getLogger(__name__)


def model_fn(model_dir):
    """Load the model for inference."""
    logger.info(f"Loading model from {model_dir}")
    
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.eval()
    
    return {'model': model, 'tokenizer': tokenizer}


def input_fn(request_body, content_type='application/json'):
    """Process input data."""
    if content_type == 'application/json':
        input_data = json.loads(request_body)
        return input_data
    else:
        raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(input_data, model_dict):
    """Make predictions."""
    model = model_dict['model']
    tokenizer = model_dict['tokenizer']
    
    # Extract input fields
    text = input_data.get('text', '')
    target_culture = input_data.get('target_culture', '')
    context = input_data.get('context', '')
    
    # Format input text
    formatted_text = f"[CONTEXT: {context}] [REGION: {target_culture}] {text}"
    
    # Tokenize
    inputs = tokenizer(
        formatted_text,
        return_tensors='pt',
        truncation=True,
        padding=True,
        max_length=512
    )
    
    # Run inference
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        probabilities = torch.softmax(logits, dim=-1)
        prediction = torch.argmax(logits, dim=-1)
    
    # Cultural adaptations based on region
    cultural_adaptations = {
        'middle_east': {
            'greeting': 'Peace be upon you',
            'closing': 'May God grant you health',
            'formal': True
        },
        'east_asia': {
            'greeting': 'I hope this message finds you well',
            'closing': 'Thank you for your understanding',
            'formal': True
        },
        'sub_saharan_africa': {
            'greeting': 'Greetings to you and your family',
            'closing': 'Stay well',
            'formal': False
        },
        'latin_america': {
            'greeting': 'I hope you are well',
            'closing': 'Take care',
            'formal': False
        }
    }
    
    # Get cultural elements
    culture_info = cultural_adaptations.get(target_culture, {})
    
    # Adapt the text
    adapted_text = text
    if culture_info.get('formal'):
        adapted_text = adapted_text.replace("you need to", "it would be beneficial if you could")
        adapted_text = adapted_text.replace("you must", "it is important that you")
    
    # Add cultural elements
    if culture_info.get('greeting'):
        adapted_text = f"{culture_info['greeting']}. {adapted_text}"
    if culture_info.get('closing'):
        adapted_text = f"{adapted_text}. {culture_info['closing']}"
    
    return {
        'original_text': text,
        'adapted_text': adapted_text,
        'cultural_appropriateness_score': float(probabilities[0][1]),
        'is_appropriate': bool(prediction[0] == 1),
        'target_culture': target_culture,
        'context': context
    }


def output_fn(prediction, content_type='application/json'):
    """Format the output."""
    if content_type == 'application/json':
        return json.dumps(prediction)
    else:
        raise ValueError(f"Unsupported content type: {content_type}")