"""
Real-time Medical Transcription Demo

This demonstrates real-time streaming transcription for medical consultations.
"""

import asyncio
from datetime import datetime

import numpy as np
import pyaudio  # For audio capture (would be installed separately)

from src.voice.realtime_streaming import (
    MedicalStreamingTranscriber,
    StreamingConfig,
    StreamingResult,
    StreamingState,
)


class MedicalTranscriptionDemo:
    """Demo application for real-time medical transcription."""

    def __init__(self):
        """Initialize the demo."""
        # Configure streaming
        self.config = StreamingConfig(
            region="us-east-1",
            language_code="en-US",
            medical_specialty="PRIMARYCARE",
            sample_rate=16000,
            enable_partial_results=True,
            enable_speaker_partitioning=True,
            enable_noise_reduction=True,
            noise_reduction_aggressiveness=0.7,
            # Set callbacks
            on_partial_result=self.handle_partial_result,
            on_final_result=self.handle_final_result,
            on_error=self.handle_error,
            on_state_change=self.handle_state_change,
        )

        # Initialize transcriber
        self.transcriber = MedicalStreamingTranscriber(self.config)

        # Audio capture setup (placeholder - would use actual audio library)
        self.audio_stream = None
        self.is_recording = False
        # UI state
        self.current_transcript = ""
        self.final_transcript = ""

    async def handle_partial_result(self, result: StreamingResult):
        """Handle partial transcription results."""
        self.current_transcript = result.transcript
        print(f"\r[PARTIAL] {result.transcript}", end="", flush=True)

    async def handle_final_result(self, result: StreamingResult):
        """Handle final transcription results."""
        self.final_transcript += result.transcript + " "
        print(f"\n[FINAL] {result.transcript}")

        # Show confidence for medical terms
        for word in result.words:
            if word.term_type:
                print(
                    f"  - Medical term: {word.text} "
                    f"(type: {word.term_type}, confidence: {word.confidence:.2f})"
                )

    async def handle_error(self, error: Exception):
        """Handle transcription errors."""
        print(f"\n[ERROR] {str(error)}")

    async def handle_state_change(
        self, old_state: StreamingState, new_state: StreamingState
    ):
        """Handle state changes."""
        print(f"\n[STATE] {old_state.value} -> {new_state.value}")

    async def start_consultation(self):
        """Start a medical consultation transcription."""
        print("Starting medical consultation transcription...")
        print("Speak clearly into your microphone. Press Ctrl+C to stop.\n")

        try:
            # Start the transcription stream
            await self.transcriber.start_stream()

            # Start audio capture
            await self.start_audio_capture()

            # Keep running until interrupted
            while self.is_recording:
                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\nStopping transcription...")
        finally:
            await self.stop_consultation()

    async def start_audio_capture(self):
        """Start capturing audio from microphone."""
        self.is_recording = True

        # Simulate audio capture (in real implementation, would use PyAudio)
        # This is a placeholder that generates synthetic audio
        asyncio.create_task(self.audio_capture_loop())

    async def audio_capture_loop(self):
        """Simulated audio capture loop."""
        chunk_duration = 0.1  # 100ms chunks
        chunk_size = int(self.config.sample_rate * chunk_duration)

        while self.is_recording:
            # Generate synthetic audio (in real app, capture from microphone)
            # Simulate speech with varying frequencies
            t = np.linspace(0, chunk_duration, chunk_size)
            frequency = 200 + np.random.rand() * 200  # Voice frequency range
            audio_chunk = 0.1 * np.sin(2 * np.pi * frequency * t)

            # Add some noise
            audio_chunk += 0.01 * np.random.randn(chunk_size)

            # Send to transcriber
            await self.transcriber.send_audio(audio_chunk)

            # Wait before next chunk
            await asyncio.sleep(chunk_duration)

    async def stop_consultation(self):
        """Stop the consultation and save results."""
        self.is_recording = False

        # Stop transcription
        await self.transcriber.stop_stream()

        # Get final transcript
        final_transcript = self.transcriber.get_session_transcript()

        # Save session
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"consultation_{timestamp}.json"
        await self.transcriber.export_session(filename)

        print(f"\n\nConsultation ended.")
        print(f"Final transcript: {final_transcript}")
        print(f"Session saved to: {filename}")
        # Show session statistics
        stats = self.transcriber._calculate_session_statistics()
        print(f"\nSession Statistics:")
        print(f"  Duration: {stats.get('duration_seconds', 0):.1f} seconds")
        print(f"  Words transcribed: {stats.get('total_words', 0)}")
        print(f"  Average confidence: {stats.get('average_confidence', 0):.2f}")
        print(f"  Speakers detected: {stats.get('number_of_speakers', 0)}")

    async def pause_resume_demo(self):
        """Demonstrate pause/resume functionality."""
        print("Starting transcription with pause/resume demo...")

        await self.transcriber.start_stream()
        await self.start_audio_capture()

        # Run for 5 seconds
        await asyncio.sleep(5)

        # Pause
        print("\n[DEMO] Pausing transcription...")
        await self.transcriber.pause_stream()

        # Wait 3 seconds
        await asyncio.sleep(3)

        # Resume
        print("[DEMO] Resuming transcription...")
        await self.transcriber.resume_stream()

        # Run for another 5 seconds
        await asyncio.sleep(5)

        # Stop
        await self.stop_consultation()


async def main():
    """Run the demo."""
    demo = MedicalTranscriptionDemo()

    print("Medical Real-time Transcription Demo")
    print("=====================================\n")
    print("Note: This demo simulates audio input.")
    print("In production, it would capture from your microphone.\n")

    # Run basic consultation demo
    await demo.start_consultation()


if __name__ == "__main__":
    asyncio.run(main())
