from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType]):
        self.model = model

    async def get_by_id(self, session: AsyncSession, id: int) -> ModelType | None:
        result = await session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()
