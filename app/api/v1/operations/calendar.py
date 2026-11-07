"""Read-only calendar. Permanent teams with legacy daily-team fallback.
Python 3.10 compatible. Does not create payroll or legacy events.
"""
from collections import defaultdict
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app import models as legacy
from app.db import get_db
from app.operations import models as ops

router = APIRouter(prefix='/operations/calendar', tags=['Operations Calendar (development)'])


class CalendarPerson(BaseModel):
    person_id: int
    name: str
    assignment_role: str = 'Member'


class CalendarTeam(BaseModel):
    id: int
    team_name: str
    planning_status: str = 'Ready'
    leader_person_id: Optional[int] = None
    is_active: bool = True
    members: List[CalendarPerson] = Field(default_factory=list)


class CalendarEvent(BaseModel):
    id: int
    work_date: date
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None
    team_id: Optional[int] = None
    daily_team_id: Optional[int] = None  # legacy compatibility
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    service_type: Optional[str] = None
    estimated_amount: Optional[str] = None
    planning_status: str
    execution_status: str
    notes: Optional[str] = None
    participants: List[CalendarPerson] = Field(default_factory=list)
    participants_source: str = 'Unassigned'


class CalendarWarning(BaseModel):
    code: str
    severity: str = 'warning'
    work_date: date
    description: str
    event_ids: List[int] = Field(default_factory=list)
    person_id: Optional[int] = None
    team_id: Optional[int] = None


class CalendarDay(BaseModel):
    work_date: date
    teams: List[CalendarTeam] = Field(default_factory=list)
    events: List[CalendarEvent] = Field(default_factory=list)
    warnings: List[CalendarWarning] = Field(default_factory=list)


class CalendarWeek(BaseModel):
    week_start: date
    week_end: date
    days: List[CalendarDay]
    total_events: int
    confirmed_events: int
    tentative_events: int
    draft_events: int
    cancelled_events: int


def _name(p):
    return ' '.join(x for x in (p.first_name, p.last_name) if x)


def _members(team):
    return [CalendarPerson(person_id=x.person_id, name=_name(x.person),
                           assignment_role='Leader' if x.person_id == team.leader_person_id else 'Member')
            for x in team.members]


def _build_days(db: Session, start: date, end: date):
    if end < start or (end - start).days > 31:
        raise HTTPException(400, 'Calendar range must be within 32 days')
    events = db.query(ops.OperationsPlannedEvent).options(
        selectinload(ops.OperationsPlannedEvent.assignments).selectinload(ops.OperationsEventAssignment.person)
    ).filter(ops.OperationsPlannedEvent.work_date.between(start, end)).order_by(
        ops.OperationsPlannedEvent.work_date, ops.OperationsPlannedEvent.scheduled_start,
        ops.OperationsPlannedEvent.id,
    ).all()
    team_ids = {e.team_id for e in events if e.team_id is not None}
    daily_ids = {e.daily_team_id for e in events if e.team_id is None and e.daily_team_id is not None}
    teams = {}
    legacy_teams = {}
    if team_ids:
        teams = {t.id: t for t in db.query(ops.OperationsTeam).options(
            selectinload(ops.OperationsTeam.members).selectinload(ops.OperationsTeamMember.person)
        ).filter(ops.OperationsTeam.id.in_(team_ids)).all()}
    if daily_ids:
        legacy_teams = {t.id: t for t in db.query(ops.OperationsDailyTeam).options(
            selectinload(ops.OperationsDailyTeam.members).selectinload(ops.OperationsDailyTeamMember.person)
        ).filter(ops.OperationsDailyTeam.id.in_(daily_ids)).all()}
    # A team can be inactive before sync-inactive is run; check the current helper status too.
    person_ids = {x.person_id for t in teams.values() for x in t.members}
    people = {}
    if person_ids:
        people = {p.id: p for p in db.query(ops.OperationsPerson).filter(ops.OperationsPerson.id.in_(person_ids)).all()}
    helper_ids = {p.helper_id for p in people.values() if p.helper_id is not None}
    active_helpers = set()
    if helper_ids:
        active_helpers = {h.id for h in db.query(legacy.Helper).filter(
            legacy.Helper.id.in_(helper_ids), legacy.Helper.is_active.is_(True)
        ).all()}
    def usable(team):
        if not team.is_active:
            return False
        for member in team.members:
            p = people.get(member.person_id)
            if not p or not p.is_active or (p.person_type == 'Helper' and p.helper_id not in active_helpers):
                return False
        return True

    client_ids = {e.client_id for e in events if e.client_id is not None}
    location_ids = {e.location_id for e in events if e.location_id is not None}
    clients = {c.id: c.name for c in db.query(legacy.Client).filter(legacy.Client.id.in_(client_ids)).all()} if client_ids else {}
    locations = {l.id: l.location_name for l in db.query(legacy.ClientLocation).filter(legacy.ClientLocation.id.in_(location_ids)).all()} if location_ids else {}
    days = {start + timedelta(days=i): CalendarDay(work_date=start + timedelta(days=i))
            for i in range((end - start).days + 1)}
    shown_teams = defaultdict(set)
    for e in events:
        day = days[e.work_date]
        permanent = teams.get(e.team_id) if e.team_id is not None else None
        old = legacy_teams.get(e.daily_team_id) if e.team_id is None and e.daily_team_id is not None else None
        team = permanent or old
        members = _members(team) if team else []
        if team and (type(team).__name__, team.id) not in shown_teams[e.work_date]:
            shown_teams[e.work_date].add((type(team).__name__, team.id))
            day.teams.append(CalendarTeam(
                id=team.id, team_name=team.team_name,
                planning_status=getattr(team, 'planning_status', 'Ready'),
                leader_person_id=team.leader_person_id,
                is_active=usable(team) if permanent else True,
                members=members,
            ))
        if e.assignments:
            participants = [CalendarPerson(person_id=a.person_id, name=_name(a.person),
                                           assignment_role=a.assignment_role) for a in e.assignments]
            source = 'Event'
        elif team:
            participants = members
            source = 'Team'
        else:
            participants = []
            source = 'Unassigned'
        day.events.append(CalendarEvent(
            id=e.id, work_date=e.work_date, team_id=e.team_id, daily_team_id=e.daily_team_id,
            scheduled_start=e.scheduled_start.isoformat(timespec='minutes') if e.scheduled_start else None,
            scheduled_end=e.scheduled_end.isoformat(timespec='minutes') if e.scheduled_end else None,
            client_id=e.client_id, client_name=clients.get(e.client_id),
            location_id=e.location_id, location_name=locations.get(e.location_id),
            service_type=e.service_type,
            estimated_amount=str(e.estimated_amount) if e.estimated_amount is not None else None,
            planning_status=e.planning_status, execution_status=e.execution_status,
            notes=e.notes, participants=participants, participants_source=source,
        ))
        if e.planning_status != 'Cancelled' and e.work_date >= date.today() and permanent is not None and not usable(permanent):
            day.warnings.append(CalendarWarning(
                code='INACTIVE_TEAM', work_date=e.work_date, event_ids=[e.id],
                team_id=permanent.id, description='Team is inactive or has an inactive member; reassign this future event',
            ))

    for work_date, day in days.items():
        active = [e for e in day.events if e.planning_status != 'Cancelled']
        for e in active:
            if e.scheduled_start is None or e.scheduled_end is None:
                day.warnings.append(CalendarWarning(code='MISSING_TIME', work_date=work_date,
                    event_ids=[e.id], description='Event has no complete planned time window'))
            if e.team_id is None and e.daily_team_id is None:
                day.warnings.append(CalendarWarning(code='NO_TEAM', work_date=work_date,
                    event_ids=[e.id], description='Event has no team assigned'))
            if not e.participants:
                day.warnings.append(CalendarWarning(code='NO_PARTICIPANTS', work_date=work_date,
                    event_ids=[e.id], description='Event has no assigned participants'))
        for i, e in enumerate(active):
            if not e.scheduled_start or not e.scheduled_end:
                continue
            for other in active[i + 1:]:
                if not other.scheduled_start or not other.scheduled_end:
                    continue
                if not (e.scheduled_start < other.scheduled_end and other.scheduled_start < e.scheduled_end):
                    continue
                shared = {p.person_id for p in e.participants} & {p.person_id for p in other.participants}
                for person_id in sorted(shared):
                    day.warnings.append(CalendarWarning(code='PERSON_TIME_OVERLAP', work_date=work_date,
                        event_ids=[e.id, other.id], person_id=person_id,
                        description='Person has overlapping planned service times'))
                if e.team_id is not None and e.team_id == other.team_id:
                    day.warnings.append(CalendarWarning(code='TEAM_TIME_OVERLAP', work_date=work_date,
                        event_ids=[e.id, other.id], team_id=e.team_id,
                        description='Permanent team has overlapping planned service times'))
        day.warnings.sort(key=lambda w: (w.code, w.event_ids))
    return [days[d] for d in sorted(days)]


@router.get('/day', response_model=CalendarDay)
def calendar_day(work_date: date = Query(...), db: Session = Depends(get_db)):
    return _build_days(db, work_date, work_date)[0]


@router.get('/week', response_model=CalendarWeek)
def calendar_week(week_start: date = Query(...), db: Session = Depends(get_db)):
    monday = week_start - timedelta(days=week_start.weekday())
    days = _build_days(db, monday, monday + timedelta(days=6))
    event_list = [e for day in days for e in day.events]
    return CalendarWeek(
        week_start=monday, week_end=monday + timedelta(days=6), days=days,
        total_events=len(event_list), confirmed_events=sum(e.planning_status == 'Confirmed' for e in event_list),
        tentative_events=sum(e.planning_status == 'Tentative' for e in event_list),
        draft_events=sum(e.planning_status == 'Draft' for e in event_list),
        cancelled_events=sum(e.planning_status == 'Cancelled' for e in event_list),
    )
