"""Team and department models for organizational hierarchy."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from src.models.base import Base


class Department(Base):
    """Department model for organizational structure."""

    __tablename__ = "departments"

    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    organization_id = Column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    parent_department_id = Column(
        PGUUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )

    # Basic information
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)  # Department code (e.g., "MED", "ADMIN")
    description = Column(String(1000))

    # Hierarchy
    level = Column(Integer, default=0)  # 0 = root department, 1+ = subdepartments
    path = Column(
        String(500)
    )  # Materialized path for efficient queries (e.g., "root.medical.emergency")

    # Status
    active = Column(Boolean, default=True)

    # Metadata
    meta_data = Column("metadata", JSON, default=dict)
    member_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    created_by = Column(PGUUID(as_uuid=True), nullable=True)
    updated_by = Column(PGUUID(as_uuid=True), nullable=True)

    # Relationships
    organization = relationship("Organization", backref="departments")
    parent_department = relationship(
        "Department", remote_side=[id], backref="subdepartments"
    )
    teams = relationship(
        "Team", back_populates="department", cascade="all, delete-orphan"
    )


class Team(Base):
    """Team model for organizational units."""

    __tablename__ = "teams"

    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    organization_id = Column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    department_id = Column(
        PGUUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )

    # Basic information
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)  # Team code (e.g., "TEAM-001")
    description = Column(String(1000))

    # Team type
    team_type = Column(
        String(50), default="general"
    )  # general, medical, administrative, etc.

    # Status
    active = Column(Boolean, default=True)

    # Metadata
    meta_data = Column("metadata", JSON, default=dict)
    member_count = Column(Integer, default=0)

    # Cost center information
    cost_center_code = Column(String(50), nullable=True)
    budget_allocated = Column(
        JSON, default=dict
    )  # {"currency": "USD", "amount": 10000}

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    created_by = Column(PGUUID(as_uuid=True), nullable=True)
    updated_by = Column(PGUUID(as_uuid=True), nullable=True)

    # Relationships
    organization = relationship("Organization", backref="teams")
    department = relationship("Department", back_populates="teams")
    members = relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan"
    )


class TeamMember(Base):
    """Team member association model."""

    __tablename__ = "team_members"

    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    team_id = Column(PGUUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("user_auth.id"), nullable=False)

    # Member information
    role = Column(String(50), default="member")  # member, lead, manager
    title = Column(String(255))  # Job title

    # Status
    active = Column(Boolean, default=True)

    # Timestamps
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    left_at = Column(DateTime, nullable=True)

    # Relationships
    team = relationship("Team", back_populates="members")
    user = relationship("UserAuth", backref="team_memberships")

    # Unique constraint to prevent duplicate memberships
    __table_args__ = ({"schema": None, "extend_existing": True},)
