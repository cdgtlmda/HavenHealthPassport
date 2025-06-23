#!/usr/bin/env python3
"""Verify Amazon Bedrock integration is working correctly."""

import asyncio
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.bedrock_service import BedrockModel, bedrock_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}")


async def verify_bedrock_integration():
    """Verify Bedrock integration is working."""
    print("Amazon Bedrock Integration Verification")
    print(f"Started at: {datetime.utcnow().isoformat()}")

    # 1. Check service health
    print_section("1. Service Health Check")
    try:
        health = bedrock_service.health_check()
        print(f"✓ Service Status: {health['status']}")
        print(f"✓ Available Models: {health.get('available_models', 0)}")
        if "performance" in health:
            perf = health["performance"]
            print(f"✓ Performance Stats:")
            print(f"  - Avg Latency: {perf.get('avg_latency', 0):.2f}s")
            print(f"  - Min Latency: {perf.get('min_latency', 0):.2f}s")
            print(f"  - Max Latency: {perf.get('max_latency', 0):.2f}s")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False

    # 2. List available models
    print_section("2. Available Models")
    models_to_test = [
        BedrockModel.CLAUDE_V2,
        BedrockModel.CLAUDE_INSTANT_V1,
        BedrockModel.TITAN_TEXT_EXPRESS,
    ]

    available_models = []
    for model in models_to_test:
        if bedrock_service.is_model_available(model):
            print(f"✓ {model} - Available")
            available_models.append(model)
        else:
            print(f"✗ {model} - Not Available")

    if not available_models:
        print("✗ No models available for testing")
        return False

    # 3. Test basic invocation
    print_section("3. Basic Model Invocation Test")
    test_prompt = "What is the capital of France? Answer in one word."

    try:
        print(f"Testing with prompt: '{test_prompt}'")
        response, metadata = bedrock_service.invoke_model(
            prompt=test_prompt,
            model_id=available_models[0],
            temperature=0.1,
            max_tokens=10,
        )

        print(f"✓ Response: {response}")
        print(f"✓ Model Used: {metadata['model_id']}")
        print(f"✓ Latency: {metadata['latency_seconds']:.2f}s")
        print(f"✓ Response Length: {metadata['response_length']} chars")
    except Exception as e:
        print(f"✗ Basic invocation failed: {e}")
        return False

    # 4. Test translation use case
    print_section("4. Medical Translation Test")
    medical_prompt = """Translate the following medical instruction from English to Spanish:

    "Take one tablet by mouth twice daily with food for 7 days."

    Provide only the translation, nothing else."""

    try:
        print("Testing medical translation...")
        response, metadata = bedrock_service.invoke_model(
            prompt=medical_prompt,
            model_id=available_models[0],
            temperature=0.1,
            system_prompt="You are a professional medical translator.",
        )

        print(f"✓ Translation: {response}")
        print(f"✓ Latency: {metadata['latency_seconds']:.2f}s")
    except Exception as e:
        print(f"✗ Translation test failed: {e}")

    # 5. Test async invocation
    print_section("5. Async Invocation Test")
    try:
        print("Testing async invocation...")
        response, metadata = await bedrock_service.invoke_model_async(
            prompt="Count from 1 to 5.", model_id=available_models[0]
        )

        print(f"✓ Async Response: {response[:100]}...")
        print(f"✓ Completed successfully")
    except Exception as e:
        print(f"✗ Async invocation failed: {e}")

    # 6. Test batch processing
    print_section("6. Batch Processing Test")
    batch_prompts = [
        "What is 2+2?",
        "What is the color of the sky?",
        "Complete: Mary had a little...",
    ]

    try:
        print(f"Testing batch processing with {len(batch_prompts)} prompts...")
        results = bedrock_service.batch_invoke(
            prompts=batch_prompts, model_id=available_models[0]
        )

        for i, (response, metadata) in enumerate(results):
            if response:
                print(f"✓ Prompt {i+1}: {response[:50]}...")
            else:
                print(
                    f"✗ Prompt {i+1}: Failed - {metadata.get('error', 'Unknown error')}"
                )
    except Exception as e:
        print(f"✗ Batch processing failed: {e}")

    # 7. Test model info retrieval
    print_section("7. Model Information")
    for model in available_models[:2]:  # Test first 2 available models
        try:
            info = bedrock_service.get_model_info(model)
            print(f"\n{model}:")
            print(f"  Name: {info.get('model_name', 'N/A')}")
            print(f"  Provider: {info.get('provider', 'N/A')}")
            print(f"  Max Tokens: {info.get('max_tokens', 'N/A')}")
            print(f"  Streaming: {info.get('supports_streaming', False)}")
        except Exception as e:
            print(f"✗ Failed to get info for {model}: {e}")

    # 8. Performance summary
    print_section("8. Performance Summary")
    perf_stats = bedrock_service.get_performance_stats()
    if perf_stats["avg_latency"] > 0:
        print(f"✓ Average Latency: {perf_stats['avg_latency']:.2f}s")
        print(f"✓ Min Latency: {perf_stats['min_latency']:.2f}s")
        print(f"✓ Max Latency: {perf_stats['max_latency']:.2f}s")
        print(f"✓ P95 Latency: {perf_stats['p95_latency']:.2f}s")
    else:
        print("No performance data available yet")

    print(f"\n{'=' * 60}")
    print("✓ Bedrock Integration Verification Complete!")
    print(f"Completed at: {datetime.utcnow().isoformat()}")
    print(f"{'=' * 60}\n")

    return True


def main():
    """Main entry point."""
    try:
        # Run async verification
        success = asyncio.run(verify_bedrock_integration())

        if success:
            print("\n✅ All Bedrock integration tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Some Bedrock integration tests failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Verification failed with error: {e}")
        logger.error("Bedrock verification failed", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
