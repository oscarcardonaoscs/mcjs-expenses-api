"""Contracts for the isolated Operations planning API (Pydantic v2)."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator

PlanningStatus = Literal['Draft', 'Tentative', 'Confirmed', 'Cancelled']
TeamStatus = Literal['Draft', 'Ready']

class PersonCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    helper_id: Optional[int] = Field(default=None, gt=0)
    person_type: Literal['Owner', 'Helper'] = 'Helper'

class PersonOut(PersonCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool

class TeamCreate(BaseModel):
    work_date: date
    team_name: str = Field(min_length=1, max_length=100)
    leader_person_id: Optional[int] = Field(default=None, gt=0)
    member_person_ids: list[int] = Field(default_factory=list)
    notes: Optional[str] = None

    @model_validator(mode='after')
    def valid_members(self):
        if len(self.member_person_ids) != len(set(self.member_person_ids)):
            raise ValueError('Duplicate team members')
        if self.leader_person_id is not None and self.leader_person_id not in self.member_person_ids:
            raise ValueError('Leader must also be included in member_person_ids')
        return self

class TeamMembersReplace(BaseModel):
    leader_person_id: Optional[int] = Field(default=None, gt=0)
    member_person_ids: list[int]

    @model_validator(mode='after')
    def valid_members(self):
        if len(self.member_person_ids) != len(set(self.member_person_ids)):
            raise ValueError('Duplicate team members')
        if self.leader_person_id is not None and self.leader_person_id not in self.member_person_ids:
            raise ValueError('Leader must also be included in member_person_ids')
        return self

class TeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    person_id: int

class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    work_date: date
    team_name: str
    leader_person_id: Optional[int]
    planning_status: TeamStatus
    notes: Optional[str]
    members: list[TeamMemberOut] = Field(default_factory=list)

class CopyTeamsRequest(BaseModel):
    source_date: date
    target_date: date

    @model_validator(mode='after')
    def check_dates(self):
        if self.source_date == self.target_date:
            raise ValueError('Source and target dates must differ')
        return self

class PlannedEventCreate(BaseModel):
    client_id: Optional[int] = Field(default=None, gt=0)
    location_id: Optional[int] = Field(default=None, gt=0)
    work_date: date
    scheduled_start: Optional[time] = None
    scheduled_end: Optional[time] = None
    daily_team_id: Optional[int] = Field(default=None, gt=0)  # legacy read-only on new writes
    team_id: Optional[int] = Field(default=None, gt=0)
    service_type: Optional[str] = Field(default=None, max_length=30)
    estimated_amount: Optional[Decimal] = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    planning_status: PlanningStatus = 'Draft'
    notes: Optional[str] = None

    @model_validator(mode='after')
    def check_times(self):
        if self.scheduled_start and self.scheduled_end and self.scheduled_end <= self.scheduled_start:
            raise ValueError('scheduled_end must be later than scheduled_start')
        return self

class PlannedEventOut(PlannedEventCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    execution_status: str
    work_event_id: Optional[int] = None

class AssignmentReplace(BaseModel):
    person_ids: list[int]

    @model_validator(mode='after')
    def unique_people(self):
        if len(self.person_ids) != len(set(self.person_ids)):
            raise ValueError('Duplicate assigned people')
        return self

class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    planned_event_id: int
    person_id: int
    assignment_role: str
    planned_join_at: Optional[datetime]
    planned_leave_at: Optional[datetime]


class PermanentTeamCreate(BaseModel):
    team_name: str = Field(min_length=1, max_length=100)
    leader_person_id: int = Field(gt=0)
    member_person_ids: list[int] = Field(min_length=1)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_members(self):
        if len(set(self.member_person_ids)) != len(self.member_person_ids):
            raise ValueError("Duplicate team members")
        if self.leader_person_id not in self.member_person_ids:
            raise ValueError("Leader must be included in member_person_ids")
        return self


class PermanentTeamOut(BaseModel):
    id: int
    team_name: str
    leader_person_id: int
    member_person_ids: list[int]
    is_active: bool
    inactive_reason: Optional[str] = None
    notes: Optional[str] = None


class PermanentTeamRename(BaseModel):
    team_name: str = Field(min_length=1, max_length=100)
    notes: Optional[str] = None


class InactivateTeamRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=255)
