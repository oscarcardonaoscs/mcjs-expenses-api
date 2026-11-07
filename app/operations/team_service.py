"""Permanent team business rules. Python 3.10 compatible.

Never remove members from a team: create a new combination instead.
"""
from datetime import datetime
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app import models as legacy
from app.operations import models as m


def combination_hash(person_ids):
    key = ','.join(str(i) for i in sorted(set(person_ids)))
    return sha256(key.encode('ascii')).hexdigest()


def team_members(team):
    return sorted(member.person_id for member in team.members)


def validate_active_people(db: Session, person_ids):
    ids = set(person_ids)
    if not ids:
        raise HTTPException(400, 'Team needs at least one member')
    people = db.query(m.OperationsPerson).filter(m.OperationsPerson.id.in_(ids)).all()
    if len(people) != len(ids):
        raise HTTPException(400, 'One or more people do not exist')
    helper_ids = {p.helper_id for p in people if p.helper_id is not None}
    active_helpers = set()
    if helper_ids:
        active_helpers = {h.id for h in db.query(legacy.Helper).filter(
            legacy.Helper.id.in_(helper_ids), legacy.Helper.is_active.is_(True)
        ).all()}
    bad = [p.id for p in people if not p.is_active or
           (p.person_type == 'Helper' and (p.helper_id is None or p.helper_id not in active_helpers))]
    if bad:
        raise HTTPException(409, 'Inactive/missing helper in team: {}'.format(sorted(bad)))


def get_permanent_team(db: Session, team_id: int):
    team = db.query(m.OperationsTeam).options(
        selectinload(m.OperationsTeam.members)
    ).filter(m.OperationsTeam.id == team_id).first()
    if team is None:
        raise HTTPException(404, 'Permanent team not found')
    return team


def ensure_assignable(db: Session, team_id: int):
    team = get_permanent_team(db, team_id)
    if not team.is_active:
        raise HTTPException(409, 'Team is inactive')
    validate_active_people(db, team_members(team))
    if team.leader_person_id not in team_members(team):
        raise HTTPException(409, 'Team leader must be a member')
    return team


def deactivate_team(team, reason):
    team.is_active = False
    team.inactive_reason = reason[:255]
    team.deactivated_at = datetime.now()


def sync_inactive_teams(db: Session):
    """Idempotent explicit sync; caller owns commit. Never edits future/historical events."""
    teams = db.query(m.OperationsTeam).options(
        selectinload(m.OperationsTeam.members)
    ).filter(m.OperationsTeam.is_active.is_(True)).all()
    changed = []
    for team in teams:
        try:
            validate_active_people(db, team_members(team))
        except HTTPException:
            deactivate_team(team, 'A member or leader is no longer active')
            changed.append(team.id)
    return changed
