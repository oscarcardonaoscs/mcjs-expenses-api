"""Development-only planning routes.

SECURITY: Do NOT mount on production until authenticated Owner-level authorization
is installed. Operations contains employee schedules and client associations.
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app import models as legacy
from app.operations import models as m, schemas as s
from app.operations.team_service import ensure_assignable, validate_active_people, team_members, get_permanent_team

router = APIRouter(prefix='/operations', tags=['Operations (development)'])


def fail_if_duplicate(error: IntegrityError):
    raise HTTPException(status_code=409, detail='Duplicate or conflicting record') from error


def check_people(db: Session, ids: list[int]):
    if not ids:
        return
    found = {r.id for r in db.query(m.OperationsPerson).filter(
        m.OperationsPerson.id.in_(ids), m.OperationsPerson.is_active.is_(True)
    ).all()}
    missing = set(ids) - found
    if missing:
        raise HTTPException(400, f'Unknown or inactive person ids: {sorted(missing)}')


def get_team(db: Session, team_id: int):
    team = db.query(m.OperationsDailyTeam).options(
        selectinload(m.OperationsDailyTeam.members)
    ).filter(m.OperationsDailyTeam.id == team_id).first()
    if not team:
        raise HTTPException(404, 'Team not found')
    return team


@router.get('/people', response_model=list[s.PersonOut])
def people(db: Session = Depends(get_db)):
    return db.query(m.OperationsPerson).order_by(m.OperationsPerson.first_name).all()


@router.post('/people', response_model=s.PersonOut, status_code=status.HTTP_201_CREATED)
def create_person(payload: s.PersonCreate, db: Session = Depends(get_db)):
    if payload.helper_id is not None:
        helper = db.query(legacy.Helper).filter(legacy.Helper.id == payload.helper_id).first()
        if helper is None:
            raise HTTPException(400, 'helper_id does not exist')
        if payload.person_type != 'Helper':
            raise HTTPException(400, 'A linked helper must have person_type Helper')
    person = m.OperationsPerson(**payload.model_dump())
    try:
        db.add(person)
        db.commit()
        db.refresh(person)
    except IntegrityError as e:
        db.rollback()
        fail_if_duplicate(e)
    return person


@router.get('/teams', response_model=list[s.TeamOut])
def teams(work_date: date = Query(...), db: Session = Depends(get_db)):
    return db.query(m.OperationsDailyTeam).options(
        selectinload(m.OperationsDailyTeam.members)
    ).filter(m.OperationsDailyTeam.work_date == work_date).order_by(m.OperationsDailyTeam.team_name).all()


@router.post('/teams', response_model=s.TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(payload: s.TeamCreate, db: Session = Depends(get_db)):
    check_people(db, payload.member_person_ids)
    team = m.OperationsDailyTeam(
        work_date=payload.work_date, team_name=payload.team_name,
        leader_person_id=payload.leader_person_id, notes=payload.notes,
        members=[m.OperationsDailyTeamMember(person_id=p) for p in payload.member_person_ids],
    )
    try:
        db.add(team)
        db.commit()
        return get_team(db, team.id)
    except IntegrityError as e:
        db.rollback()
        fail_if_duplicate(e)


@router.put('/teams/{team_id}/members', response_model=s.TeamOut)
def replace_team_members(team_id: int, payload: s.TeamMembersReplace, db: Session = Depends(get_db)):
    team = get_team(db, team_id)
    if team.planning_status != 'Draft':
        raise HTTPException(409, 'Change team to Draft before editing membership')
    check_people(db, payload.member_person_ids)
    # Do not mutate a historical executed plan or a plan already in execution.
    already_running = db.query(m.OperationsPlannedEvent.id).filter(
        m.OperationsPlannedEvent.daily_team_id == team_id,
        m.OperationsPlannedEvent.execution_status != 'Not Started',
    ).first()
    if already_running:
        raise HTTPException(409, 'Cannot change a team after execution has begun')
    team.leader_person_id = payload.leader_person_id
    team.members = [m.OperationsDailyTeamMember(person_id=p) for p in payload.member_person_ids]
    try:
        db.commit()
        return get_team(db, team_id)
    except IntegrityError as e:
        db.rollback()
        fail_if_duplicate(e)


@router.post('/teams/copy', response_model=list[s.TeamOut])
def copy_teams(payload: s.CopyTeamsRequest, db: Session = Depends(get_db)):
    source = db.query(m.OperationsDailyTeam).options(selectinload(m.OperationsDailyTeam.members)).filter(
        m.OperationsDailyTeam.work_date == payload.source_date).all()
    if not source:
        raise HTTPException(404, 'No teams on source date')
    existing = db.query(m.OperationsDailyTeam.id).filter(
        m.OperationsDailyTeam.work_date == payload.target_date).first()
    if existing:
        raise HTTPException(409, 'Target date already has teams; nothing copied')
    check_people(db, list({member.person_id for t in source for member in t.members}))
    new = []
    for team in source:
        clone = m.OperationsDailyTeam(
            work_date=payload.target_date, team_name=team.team_name,
            leader_person_id=team.leader_person_id, planning_status='Draft',
            notes=team.notes,
            members=[m.OperationsDailyTeamMember(person_id=x.person_id) for x in team.members],
        )
        db.add(clone)
        new.append(clone)
    try:
        db.commit()
        return [get_team(db, t.id) for t in new]
    except IntegrityError as e:
        db.rollback()
        fail_if_duplicate(e)


def validate_event_refs(db: Session, payload: s.PlannedEventCreate):
    if payload.client_id is not None:
        client = db.query(legacy.Client).filter(legacy.Client.id == payload.client_id).first()
        if client is None:
            raise HTTPException(400, 'Client not found')
    if payload.location_id is not None:
        loc = db.query(legacy.ClientLocation).filter(legacy.ClientLocation.id == payload.location_id).first()
        if loc is None:
            raise HTTPException(400, 'Location not found')
        if payload.client_id is None or loc.client_id != payload.client_id:
            raise HTTPException(400, 'Location must belong to selected client')
    if payload.daily_team_id is not None:
        raise HTTPException(400, 'daily_team_id is legacy; use permanent team_id')
    if payload.team_id is not None:
        ensure_assignable(db, payload.team_id)


@router.get('/planned-events', response_model=list[s.PlannedEventOut])
def planned_events(date_from: date, date_to: date, db: Session = Depends(get_db)):
    if date_to < date_from or (date_to - date_from).days > 45:
        raise HTTPException(400, 'Date range must be 0 to 45 days')
    return db.query(m.OperationsPlannedEvent).filter(
        m.OperationsPlannedEvent.work_date.between(date_from, date_to)
    ).order_by(m.OperationsPlannedEvent.work_date, m.OperationsPlannedEvent.scheduled_start).all()


@router.post('/planned-events', response_model=s.PlannedEventOut, status_code=status.HTTP_201_CREATED)
def create_planned_event(payload: s.PlannedEventCreate, db: Session = Depends(get_db)):
    validate_event_refs(db, payload)
    event = m.OperationsPlannedEvent(**payload.model_dump(), execution_status='Not Started')
    try:
        db.add(event)
        db.commit()
        db.refresh(event)
    except IntegrityError as e:
        db.rollback()
        fail_if_duplicate(e)
    return event


@router.put('/planned-events/{event_id}', response_model=s.PlannedEventOut)
def update_planned_event(event_id: int, payload: s.PlannedEventCreate, db: Session = Depends(get_db)):
    event = db.get(m.OperationsPlannedEvent, event_id)
    if event is None:
        raise HTTPException(404, 'Planned event not found')
    if event.execution_status != 'Not Started':
        raise HTTPException(409, 'Cannot reschedule an event after execution began')
    validate_event_refs(db, payload)
    for k, v in payload.model_dump().items():
        setattr(event, k, v)
    try:
        db.commit()
        db.refresh(event)
    except IntegrityError as e:
        db.rollback()
        fail_if_duplicate(e)
    return event


@router.get('/planned-events/{event_id}/assignments', response_model=list[s.AssignmentOut])
def list_assignments(event_id: int, db: Session = Depends(get_db)):
    if db.get(m.OperationsPlannedEvent, event_id) is None:
        raise HTTPException(404, 'Planned event not found')
    return db.query(m.OperationsEventAssignment).filter(
        m.OperationsEventAssignment.planned_event_id == event_id
    ).order_by(m.OperationsEventAssignment.id).all()


@router.put('/planned-events/{event_id}/assignments', response_model=list[s.AssignmentOut])
def replace_assignments(event_id: int, payload: s.AssignmentReplace, db: Session = Depends(get_db)):
    event = db.get(m.OperationsPlannedEvent, event_id)
    if event is None:
        raise HTTPException(404, 'Planned event not found')
    if event.execution_status != 'Not Started':
        raise HTTPException(409, 'Cannot replace participants after execution started')
    if event.team_id is not None:
        ensure_assignable(db, event.team_id)
    validate_active_people(db, payload.person_ids) if payload.person_ids else None
    leader_id = None
    if event.team_id is not None:
        team = get_permanent_team(db, event.team_id)
        leader_id = team.leader_person_id if team.leader_person_id in payload.person_ids else None
    elif event.daily_team_id is not None:
        team = get_team(db, event.daily_team_id)
        leader_id = team.leader_person_id if team.leader_person_id in payload.person_ids else None
    db.query(m.OperationsEventAssignment).filter(
        m.OperationsEventAssignment.planned_event_id == event_id
    ).delete(synchronize_session=False)
    db.flush()
    for person_id in payload.person_ids:
        db.add(m.OperationsEventAssignment(
            planned_event_id=event_id, person_id=person_id,
            assignment_role='Leader' if person_id == leader_id else 'Member'
        ))
    db.commit()
    return list_assignments(event_id, db)
