"""Team collaboration and invitation endpoints."""

from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_platform_user
from .. import crud, models, schemas

router = APIRouter(prefix="/team", tags=["Team Collaboration"])


def _require_company_membership(
    db: Session,
    *,
    company_id: uuid.UUID,
    user: models.PlatformUser,
) -> models.ClientCompany:
    """Ensure the current user is allowed to manage this company.

    For now, only the owning platform user or a global admin is allowed.
    Later this can be extended to use TeamMembership roles.
    """
    company = crud.get_client_company_by_id(db, company_id=company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client company not found",
        )

    if company.platform_user_id != user.id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this company",
        )
    return company


@router.post(
    "/companies/{company_id}/invites",
    response_model=schemas.TeamInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_team_member(
    company_id: uuid.UUID = Path(..., description="UUID of the client company"),
    invite: schemas.TeamInviteCreate = ...,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> schemas.TeamInviteResponse:
    """Invite a team member to collaborate on a client company.

    Returns the created/updated membership plus an invite token.
    """
    company = _require_company_membership(db, company_id=company_id, user=current_user)

    membership = crud.create_team_invitation(
        db,
        company=company,
        inviter=current_user,
        email=invite.email,
        role=invite.role.value,
    )

    return schemas.TeamInviteResponse(
        membership=schemas.TeamMembershipResponse.from_orm(membership),
        invite_token=membership.invite_token or "",
    )


@router.post("/invitations/accept", response_model=schemas.TeamMembershipResponse)
async def accept_team_invite(
    token: str,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> schemas.TeamMembershipResponse:
    """Accept a team invitation using the invitation token.

    The caller must already be authenticated on the platform.
    """
    try:
        membership = crud.accept_team_invitation(db, token=token, user=current_user)
    except ValueError as exc:  # invalid or expired token
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return schemas.TeamMembershipResponse.from_orm(membership)


@router.get(
    "/companies/{company_id}/members",
    response_model=List[schemas.TeamMembershipResponse],
)
async def list_company_team_members(
    company_id: uuid.UUID = Path(..., description="UUID of the client company"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> List[schemas.TeamMembershipResponse]:
    """List all team members for a company.

    Currently restricted to the owning user or a global admin.
    """
    _ = _require_company_membership(db, company_id=company_id, user=current_user)
    memberships = crud.list_team_members(db, company_id=company_id)
    return [schemas.TeamMembershipResponse.from_orm(m) for m in memberships]


@router.get(
    "/companies/{company_id}/activity",
    response_model=List[schemas.TeamActivityEntry],
)
async def list_company_team_activity(
    company_id: uuid.UUID = Path(..., description="UUID of the client company"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> List[schemas.TeamActivityEntry]:
    """List recent team activity for a company."""
    from sqlalchemy import desc

    _ = _require_company_membership(db, company_id=company_id, user=current_user)

    activities = (
        db.query(models.TeamActivityLog)
        .filter(models.TeamActivityLog.company_id == company_id)
        .order_by(desc(models.TeamActivityLog.created_at))
        .limit(200)
        .all()
    )
    return [schemas.TeamActivityEntry.from_orm(a) for a in activities]

