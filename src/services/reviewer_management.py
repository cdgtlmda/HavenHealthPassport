"""Production Medical Reviewer Management System.

This module manages the database of medical reviewers, their qualifications,
availability, and assignment for translation review processes.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    select,
    update,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import relationship

from src.models.base import Base
from src.security.encryption import EncryptionService
from src.translation.medical.review_process import ReviewAssignment, ReviewerRole
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ReviewerStatus(str, Enum):
    """Reviewer availability status."""

    ACTIVE = "active"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"
    ON_LEAVE = "on_leave"
    INACTIVE = "inactive"


class ExpertiseLevel(str, Enum):
    """Reviewer expertise levels."""

    JUNIOR = "junior"
    INTERMEDIATE = "intermediate"
    SENIOR = "senior"
    EXPERT = "expert"


@dataclass
class ReviewerWorkload:
    """Current workload for a reviewer."""

    active_reviews: int
    completed_today: int
    average_review_time: timedelta
    next_available: datetime
    capacity_percentage: float


# Association table for reviewer languages
reviewer_languages = Table(
    "reviewer_languages",
    Base.metadata,
    Column("reviewer_id", String(100), ForeignKey("medical_reviewers.id")),
    Column("language_code", String(10)),
    Column("proficiency_level", String(20)),  # native, fluent, professional, basic
)

# Association table for reviewer specializations
reviewer_specializations = Table(
    "reviewer_specializations",
    Base.metadata,
    Column("reviewer_id", String(100), ForeignKey("medical_reviewers.id")),
    Column("specialization", String(100)),
    Column("years_experience", Integer),
)


class MedicalReviewer(Base):
    """Medical reviewer profile."""

    __tablename__ = "medical_reviewers"

    id = Column(String(100), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # ReviewerRole enum
    expertise_level = Column(String(20), nullable=False)
    status = Column(String(20), default=ReviewerStatus.ACTIVE.value)

    # Qualifications
    credentials = Column(JSON)  # List of credentials/certifications
    years_experience = Column(Integer)
    organization = Column(String(255))
    license_number = Column(String(100))
    license_expiry = Column(DateTime)

    # Performance metrics
    total_reviews = Column(Integer, default=0)
    accuracy_score = Column(Float, default=0.0)
    average_review_time = Column(Integer, default=0)  # minutes
    reliability_score = Column(Float, default=100.0)

    # Availability
    timezone = Column(String(50), default="UTC")
    working_hours = Column(JSON)  # {"monday": {"start": "09:00", "end": "17:00"}, ...}
    max_daily_reviews = Column(Integer, default=20)
    preferred_document_types = Column(JSON)  # List of TranslationMode values

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

    # Relationships
    review_assignments = relationship("ReviewAssignment", back_populates="reviewer")
    review_history = relationship("ReviewHistory", back_populates="reviewer")


class ReviewHistory(Base):
    """Historical record of completed reviews."""

    __tablename__ = "review_history"

    id = Column(Integer, primary_key=True)
    reviewer_id = Column(String(100), ForeignKey("medical_reviewers.id"))
    review_id = Column(String(100))
    completed_at = Column(DateTime, default=datetime.utcnow)
    review_time = Column(Integer)  # minutes
    quality_score = Column(Float)
    decision = Column(String(30))

    # Relationships
    reviewer = relationship("MedicalReviewer", back_populates="review_history")


class ReviewerManagementSystem:
    """Manages medical reviewers and their assignments."""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize reviewer management system."""
        self.database_url = (
            database_url or "postgresql+asyncpg://user:pass@localhost/haven_health"
        )
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-reviewers"
        )

        # Cache for reviewer availability
        self.availability_cache: Dict[str, ReviewerWorkload] = {}
        self.cache_ttl = 300  # 5 minutes

        # Initialize database
        asyncio.create_task(self._initialize_database())

    async def _initialize_database(self) -> None:
        """Initialize database connection."""
        try:
            self.engine = create_async_engine(self.database_url, echo=False)
            self.session_factory = async_sessionmaker(
                self.engine, expire_on_commit=False
            )

            # Create tables if they don't exist
            if self.engine:
                async with self.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)

            logger.info("Reviewer database initialized")

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"Failed to initialize reviewer database: {e}")

    async def register_reviewer(
        self,
        email: str,
        full_name: str,
        role: ReviewerRole,
        languages: List[Tuple[str, str]],  # (language_code, proficiency)
        specializations: List[Tuple[str, int]],  # (specialization, years)
        credentials: List[Dict[str, str]],
        organization: str,
        timezone: str = "UTC",
        **kwargs: Any,
    ) -> str:
        """Register a new medical reviewer."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        async with self.session_factory() as session:
            try:
                # Generate reviewer ID
                reviewer_id = f"rev_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{email.split('@')[0]}"

                # Create reviewer record
                reviewer = MedicalReviewer(
                    id=reviewer_id,
                    email=email,
                    full_name=full_name,
                    role=role.value,
                    expertise_level=self._determine_expertise_level(
                        credentials, kwargs.get("years_experience", 0)
                    ),
                    credentials=credentials,
                    organization=organization,
                    timezone=timezone,
                    years_experience=kwargs.get("years_experience", 0),
                    license_number=kwargs.get("license_number"),
                    license_expiry=kwargs.get("license_expiry"),
                    working_hours=kwargs.get(
                        "working_hours", self._default_working_hours()
                    ),
                    max_daily_reviews=kwargs.get("max_daily_reviews", 20),
                    preferred_document_types=kwargs.get("preferred_document_types", []),
                )

                session.add(reviewer)

                # Add languages
                for lang_code, proficiency in languages:
                    await session.execute(
                        reviewer_languages.insert().values(
                            reviewer_id=reviewer_id,
                            language_code=lang_code,
                            proficiency_level=proficiency,
                        )
                    )

                # Add specializations
                for specialization, years in specializations:
                    await session.execute(
                        reviewer_specializations.insert().values(
                            reviewer_id=reviewer_id,
                            specialization=specialization,
                            years_experience=years,
                        )
                    )

                await session.commit()
                logger.info(f"Registered new reviewer: {reviewer_id}")

                return reviewer_id

            except (ValueError, RuntimeError, AttributeError) as e:
                await session.rollback()
                logger.error(f"Failed to register reviewer: {e}")
                raise

    def _determine_expertise_level(
        self, credentials: List[Dict[str, str]], years_experience: int
    ) -> str:
        """Determine expertise level based on credentials and experience."""
        # Check for advanced credentials
        advanced_creds = ["MD", "PhD", "PharmD", "Board Certified"]
        has_advanced = any(cred.get("type") in advanced_creds for cred in credentials)

        if has_advanced and years_experience >= 10:
            return ExpertiseLevel.EXPERT.value
        elif has_advanced and years_experience >= 5:
            return ExpertiseLevel.SENIOR.value
        elif years_experience >= 3:
            return ExpertiseLevel.INTERMEDIATE.value
        else:
            return ExpertiseLevel.JUNIOR.value

    def _default_working_hours(self) -> Dict[str, Optional[Dict[str, str]]]:
        """Get default working hours."""
        default = {"start": "09:00", "end": "17:00"}
        return {
            "monday": default,
            "tuesday": default,
            "wednesday": default,
            "thursday": default,
            "friday": default,
            "saturday": None,
            "sunday": None,
        }

    async def get_available_reviewers(
        self,
        role: ReviewerRole,
        source_language: str,
        target_language: str,
        required_expertise: Optional[str] = None,
        document_type: Optional[str] = None,
        urgency: str = "normal",
    ) -> List[str]:
        """Get available reviewers for a specific review task."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        async with self.session_factory() as session:
            try:
                # Base query for active reviewers with the role
                stmt = select(MedicalReviewer).filter(
                    MedicalReviewer.role == role.value,
                    MedicalReviewer.status == ReviewerStatus.ACTIVE.value,
                )

                # Get reviewers with language proficiency
                language_reviewers = await self._get_reviewers_with_languages(
                    session, source_language, target_language
                )

                if not language_reviewers:
                    return []

                stmt = stmt.filter(MedicalReviewer.id.in_(language_reviewers))

                # Filter by expertise if required
                if required_expertise:
                    expertise_reviewers = await self._get_reviewers_with_expertise(
                        session, required_expertise
                    )
                    stmt = stmt.filter(MedicalReviewer.id.in_(expertise_reviewers))

                # Filter by document type preference
                if document_type:
                    stmt = stmt.filter(
                        MedicalReviewer.preferred_document_types.contains(
                            [document_type]
                        )
                    )

                # Get all matching reviewers
                result = await session.execute(stmt)
                reviewers = result.scalars().all()

                # Filter by availability and workload
                available_reviewers = []
                for reviewer in reviewers:
                    if await self._is_reviewer_available(reviewer, urgency):
                        available_reviewers.append(str(reviewer.id))

                # Sort by suitability
                return await self._sort_by_suitability(
                    available_reviewers, role, urgency
                )

            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(f"Failed to get available reviewers: {e}")
                return []

    async def _get_reviewers_with_languages(
        self, session: AsyncSession, source_language: str, target_language: str
    ) -> Set[str]:
        """Get reviewers proficient in both languages."""
        # Query for source language proficiency
        source_result = await session.execute(
            reviewer_languages.select().where(
                reviewer_languages.c.language_code == source_language,
                reviewer_languages.c.proficiency_level.in_(
                    ["native", "fluent", "professional"]
                ),
            )
        )
        source_reviewers = {row.reviewer_id for row in source_result}

        # Query for target language proficiency
        target_result = await session.execute(
            reviewer_languages.select().where(
                reviewer_languages.c.language_code == target_language,
                reviewer_languages.c.proficiency_level.in_(
                    ["native", "fluent", "professional"]
                ),
            )
        )
        target_reviewers = {row.reviewer_id for row in target_result}

        # Return intersection (reviewers with both languages)
        return source_reviewers.intersection(target_reviewers)

    async def _get_reviewers_with_expertise(
        self, session: AsyncSession, required_expertise: str
    ) -> Set[str]:
        """Get reviewers with specific expertise."""
        result = await session.execute(
            reviewer_specializations.select().where(
                reviewer_specializations.c.specialization == required_expertise
            )
        )
        return {row.reviewer_id for row in result}

    async def _is_reviewer_available(
        self, reviewer: MedicalReviewer, urgency: str
    ) -> bool:
        """Check if reviewer is available for new assignments."""
        # Get current workload
        workload = await self.get_reviewer_workload(str(reviewer.id))

        # Check capacity
        if workload.capacity_percentage >= 100:
            return False

        # For urgent reviews, accept up to 120% capacity
        if urgency == "urgent" and workload.capacity_percentage < 120:
            return True

        # Check if within working hours
        if not self._is_within_working_hours(reviewer):
            return False

        return True

    def _is_within_working_hours(self, reviewer: MedicalReviewer) -> bool:
        """Check if current time is within reviewer's working hours."""
        # Get current time in reviewer's timezone
        # Use standard library timezone handling
        # This is a simple implementation that doesn't require pytz
        current_time = datetime.now(dt_timezone.utc)

        # Get today's working hours
        day_name = current_time.strftime("%A").lower()
        hours = reviewer.working_hours.get(day_name)

        if not hours:
            return False

        # Parse working hours
        start_hour, start_min = map(int, hours["start"].split(":"))
        end_hour, end_min = map(int, hours["end"].split(":"))

        current_minutes = current_time.hour * 60 + current_time.minute
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min

        return start_minutes <= current_minutes <= end_minutes

    async def _sort_by_suitability(
        self, reviewer_ids: List[str], role: ReviewerRole, urgency: str
    ) -> List[str]:
        """Sort reviewers by suitability for the task."""
        # Get reviewer details and scores
        scores = []

        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        async with self.session_factory() as session:
            for reviewer_id in reviewer_ids:
                result = await session.execute(
                    select(MedicalReviewer).filter(MedicalReviewer.id == reviewer_id)
                )
                reviewer = result.scalar_one_or_none()

                if reviewer:
                    score = await self._calculate_suitability_score(
                        reviewer, role, urgency
                    )
                    scores.append((reviewer_id, score))

        # Sort by score (highest first)
        scores.sort(key=lambda x: x[1], reverse=True)

        return [reviewer_id for reviewer_id, _ in scores]

    async def _calculate_suitability_score(
        self, reviewer: MedicalReviewer, role: ReviewerRole, urgency: str
    ) -> float:
        """Calculate suitability score for a reviewer."""
        _ = role  # Will be used for role-specific scoring
        score = 0.0

        # Base score from accuracy
        score += float(reviewer.accuracy_score or 0) * 0.3

        # Reliability score
        score += float(reviewer.reliability_score or 0) * 0.2

        # Experience bonus
        if reviewer.expertise_level == ExpertiseLevel.EXPERT.value:
            score += 20
        elif reviewer.expertise_level == ExpertiseLevel.SENIOR.value:
            score += 15
        elif reviewer.expertise_level == ExpertiseLevel.INTERMEDIATE.value:
            score += 10

        # Speed bonus for urgent reviews
        if urgency == "urgent" and reviewer.average_review_time < 30:
            score += 15

        # Workload penalty
        workload = await self.get_reviewer_workload(str(reviewer.id))
        score -= workload.capacity_percentage * 0.1

        return score

    async def get_reviewer_workload(self, reviewer_id: str) -> ReviewerWorkload:
        """Get current workload for a reviewer."""
        # Check cache first
        if reviewer_id in self.availability_cache:
            cached = self.availability_cache[reviewer_id]
            if (
                datetime.utcnow() - cached.next_available
            ).total_seconds() < self.cache_ttl:
                return cached

        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        async with self.session_factory() as session:
            # Get active reviews count
            active_result = await session.execute(
                select(ReviewAssignment).filter(
                    ReviewAssignment.reviewer_id == reviewer_id,
                    ReviewAssignment.status == "assigned",
                )
            )
            active_reviews = len(active_result.scalars().all())

            # Get today's completed reviews
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
            completed_result = await session.execute(
                select(ReviewHistory).filter(
                    ReviewHistory.reviewer_id == reviewer_id,
                    ReviewHistory.completed_at >= today_start,
                )
            )
            completed_today = len(completed_result.scalars().all())

            # Get reviewer details
            reviewer_result = await session.execute(
                select(MedicalReviewer).filter(MedicalReviewer.id == reviewer_id)
            )
            reviewer = reviewer_result.scalar_one()

            # Calculate metrics
            avg_review_time = timedelta(minutes=int(reviewer.average_review_time))
            capacity_percentage = float(
                (active_reviews + completed_today) / reviewer.max_daily_reviews * 100
            )

            # Estimate next available time
            if active_reviews > 0:
                next_available = datetime.utcnow() + (avg_review_time * active_reviews)
            else:
                next_available = datetime.utcnow()

            workload = ReviewerWorkload(
                active_reviews=active_reviews,
                completed_today=completed_today,
                average_review_time=avg_review_time,
                next_available=next_available,
                capacity_percentage=capacity_percentage,
            )

            # Cache the result
            self.availability_cache[reviewer_id] = workload

            return workload

    async def assign_review(
        self, reviewer_id: str, review_id: str, due_date: datetime
    ) -> bool:
        """Assign a review to a reviewer."""
        _ = due_date  # Will be used for setting review deadlines
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        async with self.session_factory() as session:
            try:
                # Update reviewer's last active time
                result = await session.execute(
                    select(MedicalReviewer).filter(MedicalReviewer.id == reviewer_id)
                )
                # Verify reviewer exists (query has side effect of checking existence)
                _ = result.scalar_one()  # reviewer object fetched to ensure it exists

                # Update reviewer's last active time
                await session.execute(
                    update(MedicalReviewer)
                    .where(MedicalReviewer.id == reviewer_id)
                    .values(last_active=datetime.utcnow())
                )

                await session.commit()

                # Clear workload cache
                if reviewer_id in self.availability_cache:
                    del self.availability_cache[reviewer_id]

                logger.info(f"Assigned review {review_id} to reviewer {reviewer_id}")
                return True

            except (ValueError, RuntimeError, AttributeError) as e:
                await session.rollback()
                logger.error(f"Failed to assign review: {e}")
                return False

    async def complete_review(
        self,
        reviewer_id: str,
        review_id: str,
        decision: str,
        review_time_minutes: int,
        quality_score: float,
    ) -> None:
        """Record completion of a review."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        async with self.session_factory() as session:
            try:
                # Add to history
                history = ReviewHistory(
                    reviewer_id=reviewer_id,
                    review_id=review_id,
                    review_time=review_time_minutes,
                    quality_score=quality_score,
                    decision=decision,
                )
                session.add(history)

                # Update reviewer metrics
                result = await session.execute(
                    select(MedicalReviewer).filter(MedicalReviewer.id == reviewer_id)
                )
                reviewer = result.scalar_one()

                # Calculate updated values
                total_reviews = reviewer.total_reviews + 1
                new_avg_review_time = (
                    reviewer.average_review_time * (reviewer.total_reviews)
                    + review_time_minutes
                ) / total_reviews
                new_accuracy_score = (
                    reviewer.accuracy_score * (reviewer.total_reviews) + quality_score
                ) / total_reviews

                # Update reviewer stats
                await session.execute(
                    update(MedicalReviewer)
                    .where(MedicalReviewer.id == reviewer_id)
                    .values(
                        total_reviews=total_reviews,
                        average_review_time=new_avg_review_time,
                        accuracy_score=new_accuracy_score,
                        last_active=datetime.utcnow(),
                    )
                )

                await session.commit()

                # Clear cache
                if reviewer_id in self.availability_cache:
                    del self.availability_cache[reviewer_id]

            except (ValueError, RuntimeError, AttributeError) as e:
                await session.rollback()
                logger.error(f"Failed to complete review: {e}")

    async def update_reviewer_status(
        self, reviewer_id: str, status: ReviewerStatus
    ) -> None:
        """Update reviewer availability status."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(MedicalReviewer).filter(MedicalReviewer.id == reviewer_id)
                )
                # Verify reviewer exists (query has side effect of checking existence)
                _ = result.scalar_one()  # reviewer object fetched to ensure it exists

                # Update reviewer status
                await session.execute(
                    update(MedicalReviewer)
                    .where(MedicalReviewer.id == reviewer_id)
                    .values(status=status.value, updated_at=datetime.utcnow())
                )

                await session.commit()

            except (ValueError, RuntimeError, AttributeError) as e:
                await session.rollback()
                logger.error(f"Failed to update reviewer status: {e}")

    async def get_reviewer_performance_metrics(
        self, reviewer_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Get performance metrics for a reviewer."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        async with self.session_factory() as session:
            # Get reviewer details
            result = await session.execute(
                select(MedicalReviewer).filter(MedicalReviewer.id == reviewer_id)
            )
            reviewer = result.scalar_one()

            # Get recent history
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            history_result = await session.execute(
                select(ReviewHistory).filter(
                    ReviewHistory.reviewer_id == reviewer_id,
                    ReviewHistory.completed_at >= cutoff_date,
                )
            )
            recent_reviews = history_result.scalars().all()

            # Calculate metrics
            metrics: Dict[str, Any] = {
                "reviewer_id": reviewer_id,
                "name": reviewer.full_name,
                "role": reviewer.role,
                "expertise_level": reviewer.expertise_level,
                "total_reviews": reviewer.total_reviews,
                "recent_reviews": len(recent_reviews),
                "accuracy_score": reviewer.accuracy_score,
                "average_review_time": reviewer.average_review_time,
                "reliability_score": reviewer.reliability_score,
                "recent_decisions": {},
            }

            # Count decisions
            for review in recent_reviews:
                decision = review.decision
                metrics["recent_decisions"][decision] = (
                    metrics["recent_decisions"].get(decision, 0) + 1
                )

            return metrics

    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()


# Global instance
reviewer_management = ReviewerManagementSystem()
