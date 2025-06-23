#\!/usr/bin/env python3
"""Check specific errors from error_chunk_01.txt"""

import subprocess
import sys

# List of errors to check with file and line number
errors_to_check = [
    ("src/ai/translation/glossaries/glossary_manager.py", 145, "type mismatch"),
    ("src/ai/translation/glossaries/glossary_manager.py", 230, "returning Any"),
    ("src/ai/medical_nlp/negation_detector.py", 157, "unreachable"),
    ("src/security/backup_encryption.py", 89, "incompatible dict type"),
    ("src/utils/retry.py", 50, "returning Any"),
    ("src/security/phi_protection.py", 74, "type annotation needed"),
    ("src/sagemaker/preprocessing.py", 67, "type annotation needed"),
    ("src/healthcare/hipaa_access_control.py", 31, "unused type ignore"),
    ("src/certification/reporting/report_generator.py", 129, "Path | BaseException issue"),
    ("src/ai/medical_nlp/terminology/icd10_mapper.py", 511, "unreachable statement"),
    ("src/ai/llamaindex/embeddings/integration_example.py", 95, "no return expected"),
    ("src/ai/llamaindex/embeddings/integration_example.py", 135, "returning Any from None"),
    ("src/ai/llamaindex/embeddings/integration_example.py", 167, "returning Any from None"),
    ("src/ai/document_processing/textract_config.py", 522, "s3_client attribute"),
    ("src/ai/document_processing/textract_config.py", 557, "s3_client attribute"),
    ("src/ai/document_processing/textract_config.py", 571, "s3_client attribute"),
    ("src/voice/interface/examples/voice_feedback_example.py", 35, "type annotation needed"),
    ("src/security/backup_policy.py", 209, "Collection[str] has no append"),
    ("src/healthcare/data_quality/data_standardization.py", 14, "missing pytz stubs"),
    ("src/certification/reporting/report_scheduler.py", 97, "unreachable"),
    ("src/ai/medical_nlp/temporal_reasoning.py", 18, "dateutil import stubs"),
    ("src/ai/medical_nlp/temporal_reasoning.py", 19, "dateutil import stubs"),
    ("src/ai/medical_nlp/temporal_reasoning.py", 340, "returning Any"),
    ("src/ai/medical_nlp/temporal_reasoning.py", 401, "returning Any"),
    ("src/ai/medical_nlp/temporal_reasoning.py", 403, "returning Any"),
    ("src/ai/medical_nlp/temporal_reasoning.py", 410, "returning Any"),
    ("src/ai/medical_nlp/temporal_reasoning.py", 412, "returning Any"),
    ("src/ai/medical_nlp/nlp_processor.py", 22, "type annotation needed"),
    ("src/ai/langchain/retry/medical_retry.py", 159, "returning Any"),
    ("src/ai/langchain/memory/entity.py", 256, "append type mismatch"),
    ("src/ai/langchain/memory/entity.py", 262, "append type mismatch"),
    ("src/voice/volume_normalization.py", 556, "returning Any"),
    ("src/voice/volume_normalization.py", 771, "returning Any"),
    ("src/voice/urgency_detection.py", 544, "returning Any"),
    ("src/voice/urgency_detection.py", 577, "returning Any"),
    ("src/voice/urgency_detection.py", 885, "float type issues"),
    ("src/voice/timestamp_alignment.py", 308, "unreachable"),
    ("src/voice/timestamp_alignment.py", 294, "attribute error"),
    ("src/voice/timestamp_alignment.py", 533, "missing return type"),
]

# Check each error
results = []
for file_path, line_num, description in errors_to_check:
    # Run mypy on the specific file and check for the specific line
    cmd = f"mypy {file_path} 2>&1 | grep -E ':{line_num}:' | head -1"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.stdout.strip():
        # Error still present
        results.append(f"✗ {file_path}:{line_num} - {description}")
    else:
        # Error fixed
        results.append(f"✓ {file_path}:{line_num} - {description}")

# Print results
print("\n=== Error Verification Results ===\n")
for result in results:
    print(result)

# Summary
fixed = sum(1 for r in results if r.startswith("✓"))
still_present = sum(1 for r in results if r.startswith("✗"))
print(f"\nSummary: {fixed} Fixed ✓ | {still_present} Still Present ✗")
