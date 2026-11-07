"""Reusable, immutable-composition teams. DEV ONLY until Owner auth is added."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.operations import models as m, schemas as s
from app.operations.team_service import (
    combination_hash, deactivate_team, ensure_assignable,
    get_permanent_team, sync_inactive_teams, team_members, validate_active_people,
)

router = APIRouter(prefix='/operations', tags=['Operations Teams (development)'])


def as_out(team):
    return s.PermanentTeamOut(
        id=team.id, team_name=team.team_name,
        leader_person_id=team.leader_person_id,
        member_person_ids=team_members(team),
        is_active=team.is_active,
        inactive_reason=team.inactive_reason, notes=team.notes,
    )


@router.get('/permanent-teams', response_model=list[s.PermanentTeamOut])
def list_teams(include_inactive: bool = False, db: Session = Depends(get_db)):
    query = db.query(m.OperationsTeam).options(selectinload(m.OperationsTeam.members))
    if not include_inactive:
        query = query.filter(m.OperationsTeam.is_active.is_(True))
    return [as_out(t) for t in query.order_by(m.OperationsTeam.team_name, m.OperationsTeam.id).all()]


@router.post('/permanent-teams/sync-inactive')
def sync_inactive(db: Session = Depends(get_db)):
    changed = sync_inactive_teams(db)
    db.commit()
    # Future events are deliberately kept and will be flagged as needing reassignment.
    return {'deactivated_team_ids': changed, 'count': len(changed)}


@router.get('/permanent-teams/{team_id}', response_model=s.PermanentTeamOut)
def team_detail(team_id: int, db: Session = Depends(get_db)):
    return as_out(get_permanent_team(db, team_id))


@router.post('/permanent-teams', response_model=s.PermanentTeamOut,
             status_code=status.HTTP_201_CREATED)
def create_team(payload: s.PermanentTeamCreate, db: Session = Depends(get_db)):
    validate_active_people(db, payload.member_person_ids)
    key = combination_hash(payload.member_person_ids)
    candidates = db.query(m.OperationsTeam).options(selectinload(m.OperationsTeam.members)).filter(
        m.OperationsTeam.combination_hash == key, m.OperationsTeam.is_active.is_(True)
    ).all()
    if any(team_members(t) == sorted(payload.member_person_ids) for t in candidates):
        raise HTTPException(409, 'An active team with this combination already exists')
    team = m.OperationsTeam(
        team_name=payload.team_name.strip(),
        leader_person_id=payload.leader_person_id,
        combination_hash=key,
        notes=payload.notes,
        members=[m.OperationsTeamMember(person_id=i) for i in payload.member_person_ids],
    )
    db.add(team)
    try:
        db.commit()
        return as_out(get_permanent_team(db, team.id))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'Team could not be created') from exc


@router.patch('/permanent-teams/{team_id}', response_model=s.PermanentTeamOut)
def rename_team(team_id: int, payload: s.PermanentTeamRename, db: Session = Depends(get_db)):
    team = get_permanent_team(db, team_id)
    if not team.is_active:
        raise HTTPException(409, 'Inactive teams are immutable')
    team.team_name = payload.team_name.strip()
    team.notes = payload.notes
    db.commit()
    return as_out(get_permanent_team(db, team_id))


@router.post('/permanent-teams/{team_id}/deactivate', response_model=s.PermanentTeamOut)
def inactivate(team_id: int, payload: s.InactivateTeamRequest, db: Session = Depends(get_db)):
    team = get_permanent_team(db, team_id)
    if team.is_active:
        deactivate_team(team, payload.reason)
        db.commit()
    return as_out(get_permanent_team(db, team_id))


