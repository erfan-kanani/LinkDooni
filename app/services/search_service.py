from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Link
from app.db.repositories.links import LinkRepository


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.links = LinkRepository(session)

    async def search(
        self, user_id: int, query: str, *, limit: int = 20, offset: int = 0
    ) -> list[Link]:
        if not query.strip():
            return []
        return await self.links.search(user_id, query, limit=limit, offset=offset)
