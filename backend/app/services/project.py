import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.core.logging import logger


class ProjectService:
    """Service handling business logic and persistence for Projects."""

    @staticmethod
    async def create_project(session: AsyncSession, data: ProjectCreate) -> Project:
        """Creates and persists a new Project entity."""
        project = Project(
            name=data.name,
            description=data.description,
            target_crs=data.target_crs,
            status=data.status,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        logger.info("Created project id=%s name='%s'", project.id, project.name)
        return project

    @staticmethod
    async def get_project(session: AsyncSession, project_id: uuid.UUID) -> Optional[Project]:
        """Retrieves a single project by primary key ID."""
        stmt = select(Project).where(Project.id == project_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_projects(
        session: AsyncSession, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Project], int]:
        """Returns paginated list of projects and total count."""
        # Total count query
        count_stmt = select(func.count(Project.id))
        count_res = await session.execute(count_stmt)
        total = count_res.scalar_one() or 0

        # Paginated items
        items_stmt = (
            select(Project)
            .order_by(Project.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items_res = await session.execute(items_stmt)
        items = list(items_res.scalars().all())

        return items, total

    @staticmethod
    async def update_project(
        session: AsyncSession, project_id: uuid.UUID, data: ProjectUpdate
    ) -> Optional[Project]:
        """Updates attributes of an existing project."""
        project = await ProjectService.get_project(session, project_id)
        if not project:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(project, key, value)

        await session.commit()
        await session.refresh(project)
        logger.info("Updated project id=%s", project.id)
        return project

    @staticmethod
    async def delete_project(session: AsyncSession, project_id: uuid.UUID) -> bool:
        """Deletes a project by ID."""
        project = await ProjectService.get_project(session, project_id)
        if not project:
            return False

        await session.delete(project)
        await session.commit()
        logger.info("Deleted project id=%s", project_id)
        return True
