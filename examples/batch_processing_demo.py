"""
Batch Processing Demo for Medical Audio Transcription

This demonstrates batch processing of multiple medical audio files.
"""

import asyncio
from datetime import datetime
from pathlib import Path

from src.voice.batch_processing import BatchConfig, BatchProcessor, ProcessingPriority
from src.voice.transcribe_integration import TranscribeConfig


class BatchProcessingDemo:
    """Demo application for batch processing medical audio files."""

    def __init__(self):
        """Initialize the demo."""
        # Configure batch processing
        self.batch_config = BatchConfig(
            max_concurrent_jobs=3,
            num_workers=4,
            use_multiprocessing=False,
            min_confidence_threshold=0.75,
            save_intermediate_results=True,
            export_confidence_report=True,
        )

        # Configure transcription
        self.transcribe_config = TranscribeConfig(
            region="us-east-1",
            language_code="en-US",
            medical_specialty="PRIMARYCARE",
            enable_noise_reduction=True,
            enable_speaker_identification=True,
        )

        # Initialize processor
        self.processor = BatchProcessor(self.batch_config)

    async def on_progress(self, job_id: str, progress: float):
        """Handle progress updates."""
        print(f"[PROGRESS] Job {job_id}: {progress*100:.1f}% complete")

    async def on_file_complete(self, job_id: str, file_path: Path, result):
        """Handle file completion."""
        if result.success:
            print(
                f"[COMPLETE] {file_path.name} - Confidence: {result.confidence_score:.2f}"
            )
        else:
            print(f"[FAILED] {file_path.name} - Error: {result.error_message}")

    async def on_error(self, job_id: str, file_path: Path, error: Exception):
        """Handle errors."""
        print(f"[ERROR] {file_path.name}: {str(error)}")

    async def process_clinic_recordings(self):
        """Process a batch of clinic recordings."""
        print("Batch Processing Demo - Medical Clinic Recordings")
        print("=" * 50)

        # Simulate input files (in real use, these would be actual audio files)
        input_directory = Path("audio_files/clinic_recordings")
        output_directory = Path("transcripts/batch_output")

        # Create simulated file list
        input_files = [
            input_directory / "consultation_001.wav",
            input_directory / "consultation_002.wav",
            input_directory / "consultation_003.wav",
            input_directory / "patient_interview_001.wav",
            input_directory / "patient_interview_002.wav",
        ]

        # Submit batch job
        print(f"\nSubmitting batch job with {len(input_files)} files...")

        job_id = await self.processor.submit_job(
            input_files=input_files,
            output_directory=output_directory,
            transcribe_config=self.transcribe_config,
            priority=ProcessingPriority.NORMAL,
            callbacks={
                "on_progress": self.on_progress,
                "on_file_complete": self.on_file_complete,
                "on_error": self.on_error,
            },
        )
        print(f"Job ID: {job_id}")

        # Start processing (in a real scenario, this would run in background)
        processor_task = asyncio.create_task(self.processor.start_processing())

        # Monitor job status
        print("\nMonitoring job status...")
        while True:
            status = await self.processor.get_job_status(job_id)

            if status and status["status"] not in ["queued", "processing"]:
                break

            await asyncio.sleep(2)

        # Wait for processor to finish
        await processor_task

        # Show final status
        final_status = await self.processor.get_job_status(job_id)

        print(f"\n{'='*50}")
        print("Batch Processing Complete!")
        print(f"Status: {final_status['status']}")
        print(f"Processed: {final_status['processed_files']} files")
        print(f"Failed: {final_status['failed_files']} files")
        print(
            f"Success Rate: {(1 - final_status['failed_files']/final_status['total_files'])*100:.1f}%"
        )
        print(f"\nResults saved to: {output_directory}")

    async def process_emergency_recordings(self):
        """Process urgent recordings with high priority."""
        print("\nProcessing Emergency Department Recordings (HIGH PRIORITY)")
        print("=" * 50)

        # Submit high-priority job
        emergency_files = [
            Path("audio_files/emergency/trauma_001.wav"),
            Path("audio_files/emergency/cardiac_event_001.wav"),
        ]

        job_id = await self.processor.submit_job(
            input_files=emergency_files,
            output_directory=Path("transcripts/emergency"),
            transcribe_config=self.transcribe_config,
            priority=ProcessingPriority.URGENT,
        )

        print(f"Urgent job submitted: {job_id}")


async def main():
    """Run the batch processing demo."""
    demo = BatchProcessingDemo()

    print("Medical Audio Batch Processing Demo")
    print("===================================\n")
    print("Note: This demo simulates batch processing.")
    print("In production, it would process actual audio files.\n")

    # Run clinic recordings batch
    await demo.process_clinic_recordings()

    # Shutdown processor
    demo.processor.shutdown()

    print("\nDemo completed!")


if __name__ == "__main__":
    asyncio.run(main())
