from app.db.models import User
from app.db.repositories.categories import CategoryRepository
from app.db.repositories.links import LinkCreate, LinkRepository
from sqlalchemy.ext.asyncio import AsyncSession


async def test_repositories_create_search_and_delete_category(session: AsyncSession) -> None:
    user = User(telegram_user_id=1001, username="erfan", first_name="Erfan", language_code="fa")
    session.add(user)
    await session.flush()

    categories = CategoryRepository(session)
    links = LinkRepository(session)

    category = await categories.create(user.id, "Clients", emoji="C")
    link = await links.create(
        LinkCreate(
            user_id=user.id,
            category_id=category.id,
            url="https://example.com/",
            canonical_url="https://example.com/",
            title="Example CRM",
            description="Client portal",
            tags=["crm", "sales"],
            note="Important customer workspace",
        )
    )

    duplicate = await links.find_duplicate(user.id, "https://example.com/")
    search_by_tag = await links.search(user.id, "sales")
    search_by_category = await links.search(user.id, "Clients")

    assert duplicate is not None
    assert duplicate.id == link.id
    assert [found.id for found in search_by_tag] == [link.id]
    assert [found.id for found in search_by_category] == [link.id]

    deleted = await categories.delete(category.id, user.id)
    refreshed_link = await links.get(link.id, user.id)

    assert deleted is True
    assert refreshed_link is not None
    assert refreshed_link.category_id is None


async def test_favorites(session: AsyncSession) -> None:
    user = User(telegram_user_id=2002, username=None, first_name="Sara", language_code="en")
    session.add(user)
    await session.flush()

    links = LinkRepository(session)
    link = await links.create(
        LinkCreate(
            user_id=user.id,
            category_id=None,
            url="https://example.org/",
            canonical_url="https://example.org/",
            title="Example",
        )
    )
    await links.update_fields(link.id, user.id, is_favorite=True)

    favorites = await links.list_favorites(user.id)

    assert len(favorites) == 1
    assert favorites[0].id == link.id
