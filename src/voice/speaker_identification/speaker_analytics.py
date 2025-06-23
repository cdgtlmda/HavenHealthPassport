"""Speaker Analytics for Medical Conversations.

This module provides analytics and insights for speaker identification
in medical transcriptions.

IMPORTANT: This module handles PHI (Protected Health Information).
- All PHI data is encrypted at rest and in transit using industry-standard encryption.
- Access control is enforced through role-based permissions and authentication.
"""

import logging
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List

from .speaker_config import ConversationType, SpeakerRole
from .speaker_manager import ConversationAnalysis

logger = logging.getLogger(__name__)


class InteractionPattern(Enum):
    """Types of interaction patterns in conversations."""

    QUESTION_ANSWER = "question_answer"
    INFORMATION_GIVING = "information_giving"
    ACTIVE_LISTENING = "active_listening"
    CLARIFICATION = "clarification"
    EMPATHETIC_RESPONSE = "empathetic_response"
    INSTRUCTION_GIVING = "instruction_giving"
    NEGOTIATION = "negotiation"


@dataclass
class ConversationMetrics:
    """Comprehensive metrics for a medical conversation."""

    conversation_id: str
    patient_engagement_score: float  # 0-1
    provider_communication_score: float  # 0-1
    information_exchange_quality: float  # 0-1
    emotional_rapport: float  # 0-1
    clinical_efficiency: float  # 0-1
    patient_satisfaction_indicators: Dict[str, float] = field(default_factory=dict)
    communication_barriers: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class SpeakerTurnAnalysis:
    """Analysis of speaker turn-taking patterns."""

    speaker_id: str
    total_turns: int
    avg_turn_duration: float
    interruption_count: int
    pause_patterns: List[float]  # Pause durations between turns
    response_latency: float  # Average time to respond
    dominance_score: float  # 0-1, speaking time proportion


class SpeakerAnalytics:
    """Analytics engine for medical conversation speaker data."""

    def __init__(self) -> None:
        """Initialize the analytics engine."""
        self.analyses_cache: Dict[str, ConversationAnalysis] = {}
        self.metrics_cache: Dict[str, ConversationMetrics] = {}

    def analyze_conversation(
        self, analysis: ConversationAnalysis
    ) -> ConversationMetrics:
        """Perform comprehensive analysis of a medical conversation."""
        # Cache the analysis
        self.analyses_cache[analysis.conversation_id] = analysis

        # Calculate various scores
        engagement_score = self._calculate_patient_engagement(analysis)
        communication_score = self._calculate_provider_communication(analysis)
        info_quality = self._calculate_information_exchange_quality(analysis)
        emotional_rapport = self._calculate_emotional_rapport(analysis)
        clinical_efficiency = self._calculate_clinical_efficiency(analysis)

        # Identify communication barriers
        barriers = self._identify_communication_barriers(analysis)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            analysis, engagement_score, communication_score
        )

        # Create metrics object
        metrics = ConversationMetrics(
            conversation_id=analysis.conversation_id,
            patient_engagement_score=engagement_score,
            provider_communication_score=communication_score,
            information_exchange_quality=info_quality,
            emotional_rapport=emotional_rapport,
            clinical_efficiency=clinical_efficiency,
            communication_barriers=barriers,
            recommendations=recommendations,
        )

        # Additional satisfaction indicators
        metrics.patient_satisfaction_indicators = {
            "question_answered_rate": self._calculate_question_answer_rate(analysis),
            "wait_time_acceptability": self._calculate_wait_time_score(analysis),
            "clarity_of_explanation": self._calculate_clarity_score(analysis),
        }

        # Cache the metrics
        self.metrics_cache[analysis.conversation_id] = metrics

        return metrics

    def _calculate_patient_engagement(self, analysis: ConversationAnalysis) -> float:
        """Calculate patient engagement score based on participation patterns."""
        score_components = []

        # Find patient segments
        patient_segments = [
            seg
            for seg in analysis.speaker_segments
            if seg.speaker_role == SpeakerRole.PATIENT
        ]

        if not patient_segments:
            return 0.0

        # Speaking time ratio
        patient_time = sum(seg.duration for seg in patient_segments)
        total_time = sum(seg.duration for seg in analysis.speaker_segments)
        speaking_ratio = patient_time / total_time if total_time > 0 else 0

        # Ideal patient speaking ratio is 30-40% in consultations
        if 0.3 <= speaking_ratio <= 0.4:
            score_components.append(1.0)
        elif 0.2 <= speaking_ratio <= 0.5:
            score_components.append(0.7)
        else:
            score_components.append(0.4)

        # Question asking frequency
        question_count = sum(1 for seg in patient_segments if "?" in seg.content)
        questions_per_minute = (
            (question_count * 60) / analysis.duration_seconds
            if analysis.duration_seconds > 0
            else 0
        )

        # Good engagement: 1-3 questions per minute
        if 1 <= questions_per_minute <= 3:
            score_components.append(1.0)
        elif 0.5 <= questions_per_minute <= 4:
            score_components.append(0.7)
        else:
            score_components.append(0.4)

        # Average segment length (longer = more engaged)
        avg_segment_length = (
            statistics.mean(seg.duration for seg in patient_segments)
            if patient_segments
            else 0
        )

        # Good engagement: segments of 5-15 seconds
        if 5 <= avg_segment_length <= 15:
            score_components.append(1.0)
        elif 3 <= avg_segment_length <= 20:
            score_components.append(0.7)
        else:
            score_components.append(0.4)

        return statistics.mean(score_components) if score_components else 0.0

    def _calculate_provider_communication(
        self, analysis: ConversationAnalysis
    ) -> float:
        """Calculate provider communication quality score."""
        score_components = []

        # Find provider segments
        provider_segments = [
            seg
            for seg in analysis.speaker_segments
            if seg.speaker_role in [SpeakerRole.PHYSICIAN, SpeakerRole.NURSE]
        ]

        if not provider_segments:
            return 0.0

        # Check for explanation markers
        explanation_keywords = [
            "because",
            "this means",
            "in other words",
            "let me explain",
        ]
        explanations = sum(
            1
            for seg in provider_segments
            if any(keyword in seg.content.lower() for keyword in explanation_keywords)
        )
        explanation_rate = (
            explanations / len(provider_segments) if provider_segments else 0
        )

        # Good communication: 20-40% segments contain explanations
        if 0.2 <= explanation_rate <= 0.4:
            score_components.append(1.0)
        elif 0.1 <= explanation_rate <= 0.5:
            score_components.append(0.7)
        else:
            score_components.append(0.4)

        # Check for empathy markers
        empathy_keywords = ["understand", "feel", "concern", "worry", "help"]
        empathy_count = sum(
            1
            for seg in provider_segments
            if any(keyword in seg.content.lower() for keyword in empathy_keywords)
        )

        if empathy_count >= 3:
            score_components.append(1.0)
        elif empathy_count >= 1:
            score_components.append(0.7)
        else:
            score_components.append(0.3)

        return statistics.mean(score_components) if score_components else 0.0

    def _calculate_information_exchange_quality(
        self, analysis: ConversationAnalysis
    ) -> float:
        """Calculate quality of information exchange."""
        # Simple heuristic based on turn-taking and balance
        turn_rate = (
            (analysis.turn_taking_count * 60) / analysis.duration_seconds
            if analysis.duration_seconds > 0
            else 0
        )

        # Optimal turn rate: 10-20 per minute
        if 10 <= turn_rate <= 20:
            turn_score = 1.0
        elif 5 <= turn_rate <= 30:
            turn_score = 0.7
        else:
            turn_score = 0.4

        # Check balance using quality metrics
        balance_score = analysis.quality_metrics.get("speaking_balance", 0.5)

        return (turn_score + balance_score) / 2

    def _calculate_emotional_rapport(self, analysis: ConversationAnalysis) -> float:
        """Calculate emotional rapport between speakers."""
        # Simple heuristic - would use sentiment analysis in production
        positive_markers = ["thank", "appreciate", "glad", "good", "great", "excellent"]

        positive_count = sum(
            1
            for seg in analysis.speaker_segments
            if any(marker in seg.content.lower() for marker in positive_markers)
        )

        segments_with_positive = (
            positive_count / len(analysis.speaker_segments)
            if analysis.speaker_segments
            else 0
        )

        if segments_with_positive >= 0.1:
            return 1.0
        elif segments_with_positive >= 0.05:
            return 0.7
        else:
            return 0.4

    def _calculate_clinical_efficiency(self, analysis: ConversationAnalysis) -> float:
        """Calculate clinical efficiency of the conversation."""
        # Efficiency based on conversation duration and type
        duration_minutes = analysis.duration_seconds / 60

        # Expected durations by conversation type
        expected_durations = {
            ConversationType.CONSULTATION: (15, 30),
            ConversationType.EXAMINATION: (20, 40),
            ConversationType.ROUTINE_CHECKUP: (10, 20),
            ConversationType.EMERGENCY: (5, 15),
            ConversationType.MEDICATION_REVIEW: (10, 20),
        }

        min_duration, max_duration = expected_durations.get(
            analysis.conversation_type, (15, 30)
        )

        if min_duration <= duration_minutes <= max_duration:
            return 1.0
        elif duration_minutes < min_duration:
            return 0.8  # Too short might miss important info
        else:
            # Decreases as it goes over expected time
            overtime = duration_minutes - max_duration
            return max(0.3, 1.0 - (overtime / max_duration))

    def _identify_communication_barriers(
        self, analysis: ConversationAnalysis
    ) -> List[str]:
        """Identify potential communication barriers."""
        barriers = []

        # Check for interruptions (overlapping segments)
        if len(analysis.overlap_segments) > 5:
            barriers.append("Frequent interruptions detected")

        # Check for very short segments (might indicate confusion)
        short_segments = [
            seg for seg in analysis.speaker_segments if seg.duration < 2.0
        ]
        if len(short_segments) / len(analysis.speaker_segments) > 0.3:
            barriers.append("Many short utterances - possible confusion or hesitation")

        # Check for imbalanced speaking time
        if analysis.quality_metrics.get("speaking_balance", 1.0) < 0.3:
            barriers.append("Highly imbalanced speaking time")

        # Check for low confidence scores
        low_confidence = [
            seg for seg in analysis.speaker_segments if seg.confidence < 0.7
        ]
        if len(low_confidence) / len(analysis.speaker_segments) > 0.2:
            barriers.append("Audio quality issues affecting transcription")

        return barriers

    def _generate_recommendations(
        self,
        analysis: ConversationAnalysis,
        engagement_score: float,
        communication_score: float,
    ) -> List[str]:
        """Generate recommendations for improving communication."""
        recommendations = []

        if engagement_score < 0.6:
            recommendations.append(
                "Encourage more patient participation with open-ended questions"
            )

        if communication_score < 0.6:
            recommendations.append(
                "Increase use of explanatory language and check patient understanding"
            )

        # Check turn-taking rate
        turn_rate = (
            (analysis.turn_taking_count * 60) / analysis.duration_seconds
            if analysis.duration_seconds > 0
            else 0
        )
        if turn_rate < 5:
            recommendations.append(
                "Increase interaction frequency to improve engagement"
            )
        elif turn_rate > 30:
            recommendations.append(
                "Allow for longer speaking turns to enable complete thoughts"
            )

        return recommendations

    def _calculate_question_answer_rate(self, analysis: ConversationAnalysis) -> float:
        """Calculate rate of questions being answered."""
        # Simple heuristic - count questions and following responses
        questions = 0
        answered = 0

        for i, segment in enumerate(analysis.speaker_segments[:-1]):
            if "?" in segment.content:
                questions += 1
                # Check if next segment is from different speaker
                if (
                    analysis.speaker_segments[i + 1].speaker_label
                    != segment.speaker_label
                ):
                    answered += 1

        return answered / questions if questions > 0 else 1.0

    def _calculate_wait_time_score(self, analysis: ConversationAnalysis) -> float:
        """Calculate acceptability of wait times between turns."""
        # Calculate gaps between segments
        gaps = []
        for i in range(len(analysis.speaker_segments) - 1):
            gap = (
                analysis.speaker_segments[i + 1].start_time
                - analysis.speaker_segments[i].end_time
            )
            if gap > 0:
                gaps.append(gap)

        if not gaps:
            return 1.0

        avg_gap = statistics.mean(gaps)

        # Ideal gap: 0.5-2 seconds
        if 0.5 <= avg_gap <= 2:
            return 1.0
        elif 0.2 <= avg_gap <= 3:
            return 0.7
        else:
            return 0.4

    def _calculate_clarity_score(self, analysis: ConversationAnalysis) -> float:
        """Calculate clarity of provider explanations."""
        provider_segments = [
            seg
            for seg in analysis.speaker_segments
            if seg.speaker_role in [SpeakerRole.PHYSICIAN, SpeakerRole.NURSE]
        ]

        if not provider_segments:
            return 0.5

        # Look for clarity indicators
        clarity_markers = ["specifically", "for example", "this means", "in summary"]
        jargon_markers = ["syndrome", "pathology", "etiology", "prognosis"]

        clarity_count = sum(
            1
            for seg in provider_segments
            if any(marker in seg.content.lower() for marker in clarity_markers)
        )

        jargon_count = sum(
            1
            for seg in provider_segments
            if any(marker in seg.content.lower() for marker in jargon_markers)
        )

        # More clarity markers and fewer jargon = better score
        clarity_ratio = (
            clarity_count / len(provider_segments) if provider_segments else 0
        )
        jargon_ratio = jargon_count / len(provider_segments) if provider_segments else 0

        score = clarity_ratio * 0.7 + (1 - jargon_ratio) * 0.3
        return min(1.0, score * 2)  # Scale up as these are rare
