"""Operations tables. Completely separate from the legacy payroll/write paths.
Import this module once during application startup to register with Base.metadata.
"""
from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index,
    Integer, Numeric, String, Text, Time, UniqueConstraint,
)
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base


class OperationsPerson(Base):
    __tablename__ = "operations_people"
    id = Column(Integer, primary_key=True, autoincrement=True)
    helper_id = Column(INTEGER(unsigned=True), ForeignKey("helpers.id"), nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100))
    person_type = Column(String(20), nullable=False, server_default="Helper")
    is_active = Column(Boolean, nullable=False, server_default="1")
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    __table_args__ = (
        UniqueConstraint("helper_id", name="uq_operations_people_helper"),
        CheckConstraint("person_type IN ('Owner','Helper')", name="chk_operations_person_type"),
    )


class OperationsDailyTeam(Base):
    __tablename__ = "operations_daily_teams"
    id = Column(Integer, primary_key=True, autoincrement=True)
    work_date = Column(Date, nullable=False)
    team_name = Column(String(100), nullable=False)
    leader_person_id = Column(Integer, ForeignKey("operations_people.id"))
    planning_status = Column(String(20), nullable=False, server_default="Draft")
    notes = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    leader = relationship("OperationsPerson", foreign_keys=[leader_person_id])
    members = relationship("OperationsDailyTeamMember", back_populates="team", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("work_date", "team_name", name="uq_operations_team_date_name"),
        Index("idx_operations_daily_teams_leader", "leader_person_id"),
        CheckConstraint("planning_status IN ('Draft','Ready')", name="chk_operations_daily_team_status"),
    )


class OperationsDailyTeamMember(Base):
    __tablename__ = "operations_daily_team_members"
    id = Column(Integer, primary_key=True, autoincrement=True)
    daily_team_id = Column(Integer, ForeignKey("operations_daily_teams.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("operations_people.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    team = relationship("OperationsDailyTeam", back_populates="members")
    person = relationship("OperationsPerson")
    __table_args__ = (
        UniqueConstraint("daily_team_id", "person_id", name="uq_operations_daily_team_person"),
        Index("idx_operations_daily_team_member_person", "person_id"),
    )


class OperationsPlannedEvent(Base):
    __tablename__ = "operations_planned_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    work_event_id = Column(Integer, ForeignKey("helper_work_events.id"))
    client_id = Column(Integer, ForeignKey("clients.id"))
    location_id = Column(Integer, ForeignKey("client_locations.id"))
    work_date = Column(Date, nullable=False)
    scheduled_start = Column(Time)
    scheduled_end = Column(Time)
    daily_team_id = Column(Integer, ForeignKey("operations_daily_teams.id"))
    team_id = Column(Integer, ForeignKey("operations_teams.id"), nullable=True)
    service_type = Column(String(30))
    estimated_amount = Column(Numeric(10, 2))
    planning_status = Column(String(20), nullable=False, server_default="Draft")
    execution_status = Column(String(20), nullable=False, server_default="Not Started")
    notes = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    daily_team = relationship("OperationsDailyTeam")
    team = relationship("OperationsTeam", foreign_keys=[team_id])
    assignments = relationship("OperationsEventAssignment", back_populates="event", cascade="all, delete-orphan")
    status_history = relationship("OperationsEventStatusHistory", back_populates="event", order_by="OperationsEventStatusHistory.id")
    __table_args__ = (
        UniqueConstraint("work_event_id", name="uq_operations_planned_work_event"),
        Index("idx_operations_planned_day_time", "work_date", "scheduled_start"),
        Index("idx_operations_planned_team", "daily_team_id"),
        Index("idx_operations_planned_client", "client_id"),
        Index("idx_operations_planned_location", "location_id"),
        CheckConstraint("planning_status IN ('Draft','Tentative','Confirmed','Cancelled')", name="chk_operations_planning_status"),
        CheckConstraint("execution_status IN ('Not Started','En Route','Arrived','Completed')", name="chk_operations_execution_status"),
        CheckConstraint("scheduled_start IS NULL OR scheduled_end IS NULL OR scheduled_end > scheduled_start", name="chk_operations_planned_time"),
    )


class OperationsEventAssignment(Base):
    __tablename__ = "operations_event_assignments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    planned_event_id = Column(Integer, ForeignKey("operations_planned_events.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("operations_people.id"), nullable=False)
    assignment_role = Column(String(20), nullable=False, server_default="Member")
    planned_join_at = Column(DateTime)
    planned_leave_at = Column(DateTime)
    actual_join_at = Column(DateTime)
    actual_leave_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    event = relationship("OperationsPlannedEvent", back_populates="assignments")
    person = relationship("OperationsPerson")
    __table_args__ = (
        UniqueConstraint("planned_event_id", "person_id", name="uq_operations_event_person"),
        Index("idx_operations_assignment_person", "person_id"),
        CheckConstraint("assignment_role IN ('Leader','Member')", name="chk_operations_assignment_role"),
        CheckConstraint("planned_join_at IS NULL OR planned_leave_at IS NULL OR planned_leave_at > planned_join_at", name="chk_operations_assignment_planned_time"),
        CheckConstraint("actual_join_at IS NULL OR actual_leave_at IS NULL OR actual_leave_at >= actual_join_at", name="chk_operations_assignment_actual_time"),
    )


class OperationsEventStatusHistory(Base):
    __tablename__ = "operations_event_status_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    planned_event_id = Column(Integer, ForeignKey("operations_planned_events.id"), nullable=False)
    status_from = Column(String(20))
    status_to = Column(String(20), nullable=False)
    changed_by_person_id = Column(Integer, ForeignKey("operations_people.id"))
    changed_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    notes = Column(Text)
    event = relationship("OperationsPlannedEvent", back_populates="status_history")
    changed_by = relationship("OperationsPerson")
    __table_args__ = (
        Index("idx_operations_status_event_time", "planned_event_id", "changed_at"),
        Index("idx_operations_status_actor", "changed_by_person_id"),
        CheckConstraint("status_to IN ('Not Started','En Route','Arrived','Completed')", name="chk_operations_status_to"),
    )


class OperationsTeam(Base):
    """Permanent immutable combination: names/status can change, membership cannot."""
    __tablename__ = "operations_teams"
    id = Column(Integer, primary_key=True, autoincrement=True)
    team_name = Column(String(100), nullable=False)
    leader_person_id = Column(Integer, ForeignKey("operations_people.id"), nullable=False)
    combination_hash = Column(String(64), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="1")
    inactive_reason = Column(String(255))
    deactivated_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    leader = relationship("OperationsPerson", foreign_keys=[leader_person_id])
    members = relationship("OperationsTeamMember", back_populates="team")
    __table_args__ = (
        Index("idx_operations_team_active", "is_active"),
        Index("idx_operations_team_hash", "combination_hash"),
        Index("idx_operations_team_leader", "leader_person_id"),
    )


class OperationsTeamMember(Base):
    __tablename__ = "operations_team_members"
    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("operations_teams.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("operations_people.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    team = relationship("OperationsTeam", back_populates="members")
    person = relationship("OperationsPerson")
    __table_args__ = (
        UniqueConstraint("team_id", "person_id", name="uq_operations_permanent_team_person"),
        Index("idx_operations_perm_member_person", "person_id"),
    )
