# Text Splitters for Haven Health Passport

## Overview

This module provides specialized text splitting strategies for medical documents that preserve context, maintain semantic coherence, and respect medical terminology. Each splitter is optimized for different types of medical content.

## Features

### Medical-Aware Splitting
- **Preserve Medical Context**: Keeps related medical information together
- **Code Preservation**: ICD-10, CPT codes stay with their descriptions
- **Section Awareness**: Respects document structure (Chief Complaint, HPI, etc.)
- **List Handling**: Keeps medical lists (medications, diagnoses) intact
- **Abbreviation Handling**: Doesn't split on medical abbreviations

### Intelligent Overlap
- **Semantic Overlap**: Maintains context between chunks
- **Configurable Strategies**: Fixed, sentence-based, or paragraph-based
- **Relationship Tracking**: Links between sequential chunks

### Quality Metrics
- **Completeness Scoring**: How complete each chunk is
- **Coherence Scoring**: Semantic coherence within chunks
- **Medical Code Detection**: Tracks codes in each chunk

## Available Splitters

### 1. Sentence Medical Splitter
Best for: General medical text, clinical notes

```python
from haven_health_passport.ai.llamaindex.text_splitters import SentenceMedicalSplitter

splitter = SentenceMedicalSplitter()
result = splitter.split(text)
```

Features:
- Intelligent sentence boundary detection
- Medical abbreviation protection
- Dosage and measurement preservation

### 2. Section-Aware Splitter
Best for: Structured documents (discharge summaries, H&P notes)

```python
from haven_health_passport.ai.llamaindex.text_splitters import SectionAwareSplitter

splitter = SectionAwareSplitter()
result = splitter.split(text)
```

Features:
- Recognizes standard medical sections
- Keeps sections intact when possible
- Hierarchical section handling

### 3. Semantic Medical Splitter
Best for: Long documents, research papers

```python
from haven_health_passport.ai.llamaindex.text_splitters import SemanticMedicalSplitter

splitter = SemanticMedicalSplitter()
result = splitter.split(text)
```

Features:
- Uses embeddings for semantic similarity
- Groups related concepts together
- Maintains topic coherence

### 4. Medical Code Splitter
Best for: Documents with many medical codes

```python
from haven_health_passport.ai.llamaindex.text_splitters import MedicalCodeSplitter

splitter = MedicalCodeSplitter()
result = splitter.split(text)
```

Features:
- Keeps medical codes with context
- Expands context around codes
- Prevents code/description separation

### 5. Paragraph Medical Splitter
Best for: Reports, educational materials

```python
from haven_health_passport.ai.llamaindex.text_splitters import ParagraphMedicalSplitter

splitter = ParagraphMedicalSplitter()
result = splitter.split(text)
```

Features:
- Respects paragraph boundaries
- Handles medical lists properly
- Keeps related paragraphs together

### 6. Sliding Window Splitter
Best for: Maximum context preservation

```python
from haven_health_passport.ai.llamaindex.text_splitters import SlidingWindowSplitter

splitter = SlidingWindowSplitter()
result = splitter.split(text)
```

Features:
- Configurable overlap percentage
- No information loss at boundaries
- Consistent chunk sizes

## Configuration

```python
from haven_health_passport.ai.llamaindex.text_splitters import TextSplitterConfig

config = TextSplitterConfig(
    # Size constraints
    chunk_size=1000,              # Target size in tokens
    chunk_overlap=200,            # Overlap between chunks
    min_chunk_size=100,           # Minimum chunk size
    max_chunk_size=2000,          # Maximum chunk size

    # Splitting strategy
    split_strategy="sentence",     # sentence, paragraph, section, semantic
    overlap_strategy="sentence",   # none, fixed, sentence, paragraph, semantic

    # Medical-specific settings
    preserve_medical_terms=True,   # Keep medical terms intact
    preserve_medical_codes=True,   # Keep codes with context
    section_aware=True,           # Respect document sections
    maintain_lists=True,          # Keep lists together

    # Quality settings
    ensure_complete_sentences=True,
    ensure_complete_paragraphs=False,
    semantic_coherence_threshold=0.7,

    # Performance settings
    use_tokenizer=True,           # Use accurate token counting
    tokenizer_model="gpt2",       # Tokenizer to use
)

splitter = SentenceMedicalSplitter(config)
```

## Using the Factory

### Automatic Selection

```python
from haven_health_passport.ai.llamaindex.text_splitters import TextSplitterFactory

# Auto-select based on content
splitter = TextSplitterFactory.create_for_content(text)

# Select based on document type
splitter = TextSplitterFactory.create_for_document_type("discharge_summary")

# Manual selection
splitter = TextSplitterFactory.create_splitter("section")
```

### Document Type Mapping

| Document Type | Recommended Splitter |
|--------------|---------------------|
| Clinical Note | Section-Aware |
| Discharge Summary | Section-Aware |
| Lab Report | Paragraph |
| Radiology Report | Paragraph |
| Prescription | Sentence |
| Progress Note | Section-Aware |
| Consultation Report | Section-Aware |
| Medical Record | Medical Code |
| Research Paper | Semantic |
| Patient Education | Paragraph |

## Output Format

```python
result = splitter.split(text)

# Access chunks
for chunk in result.chunks:
    print(f"Text: {chunk.text}")
    print(f"Metadata: {chunk.metadata}")

# Access metadata
for meta in result.metadata:
    print(f"Chunk {meta.chunk_index}/{meta.total_chunks}")
    print(f"Section: {meta.section_name}")
    print(f"Medical codes: {meta.medical_codes}")
    print(f"Quality: {meta.completeness_score}")

# Statistics
print(f"Total chunks: {result.total_chunks}")
print(f"Average chunk size: {result.avg_chunk_size}")
print(f"Average coherence: {result.avg_coherence}")
```

## Advanced Usage

### Custom Splitting Logic

```python
class CustomMedicalSplitter(BaseMedicalSplitter):
    def split(self, text: str, metadata: Optional[Dict] = None) -> SplitResult:
        # Implement custom splitting logic
        chunks = self._custom_split_logic(text)

        # Create nodes
        nodes = []
        for i, chunk in enumerate(chunks):
            node = TextNode(
                text=chunk,
                metadata={"chunk_index": i}
            )
            nodes.append(node)

        return SplitResult(
            chunks=nodes,
            metadata=[],
            total_chunks=len(chunks)
        )
```

### Combining Splitters

```python
# Use section splitter first, then sentence splitter for large sections
section_splitter = SectionAwareSplitter()
sentence_splitter = SentenceMedicalSplitter()

# Split by sections
section_result = section_splitter.split(text)

# Further split large sections
final_chunks = []
for section_chunk in section_result.chunks:
    if len(section_chunk.text) > 2000:
        # Split large section into sentences
        sub_result = sentence_splitter.split(section_chunk.text)
        final_chunks.extend(sub_result.chunks)
    else:
        final_chunks.append(section_chunk)
```

## Performance Considerations

1. **Token Counting**: Use tokenizer for accurate sizes (slower but precise)
2. **Semantic Splitting**: Requires embeddings (more computationally intensive)
3. **Large Documents**: Consider chunking in batches for memory efficiency
4. **Caching**: Reuse splitters for multiple documents of same type

## Best Practices

1. **Choose the Right Splitter**
   - Structured documents → Section-Aware
   - Code-heavy documents → Medical Code
   - Long documents → Semantic
   - General text → Sentence

2. **Configure Overlap Appropriately**
   - More overlap = better context preservation
   - Less overlap = more efficient storage
   - Medical codes need higher overlap

3. **Monitor Quality Metrics**
   - Check completeness scores
   - Verify coherence scores
   - Ensure medical codes aren't split

4. **Test with Sample Documents**
   - Verify splitting behavior
   - Check chunk sizes
   - Ensure medical context preserved

## Future Enhancements

- [ ] ML-based optimal split point detection
- [ ] Custom medical entity recognition
- [ ] Adaptive chunk sizing based on content
- [ ] Multi-document relationship preservation
- [ ] Streaming support for large documents
