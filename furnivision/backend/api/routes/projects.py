"""FurniVision AI -- Project management routes."""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.project import Project, ProjectBrief
from pipeline.state import StateManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

_state = StateManager()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class CreateProjectRequest(BaseModel):
    name: str = "Untitled Project"
    brief: ProjectBrief | None = None


class CreateProjectResponse(BaseModel):
    project_id: str
    name: str
    status: str
    upload_urls: dict  # pre-signed or path hints for the frontend


class ProjectDetailResponse(BaseModel):
    id: str
    name: str
    status: str
    rooms: list[dict]
    brief: dict
    floorplan_gcs_path: str
    furniture_gcs_paths: list[dict]
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=CreateProjectResponse, status_code=201)
async def create_project(body: CreateProjectRequest):
    """Create a new project and return its id along with upload path hints."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name=body.name,
        status="uploading",
        brief=body.brief or ProjectBrief(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    try:
        await _state.create_project(project)
    except Exception:
        logger.exception("Failed to create project")
        raise HTTPException(status_code=500, detail="Failed to create project")

    logger.info("Created project %s (%s)", project_id, body.name)

    return CreateProjectResponse(
        project_id=project_id,
        name=project.name,
        status=project.status,
        upload_urls={
            "floorplan": f"/api/v1/projects/{project_id}/upload/floorplan",
            "furniture": f"/api/v1/projects/{project_id}/upload/furniture",
        },
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: str):
    """Retrieve full project details by id."""
    try:
        project = await _state.get_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    except Exception:
        logger.exception("Failed to load project %s", project_id)
        raise HTTPException(status_code=500, detail="Failed to load project")

    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        status=project.status,
        rooms=[r.model_dump() for r in project.rooms],
        brief=project.brief.model_dump(),
        floorplan_gcs_path=project.floorplan_gcs_path,
        furniture_gcs_paths=project.furniture_gcs_paths,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )
