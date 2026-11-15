from app.core.di import build_dishka_container
from app.core.engines.database import Transaction


async def test_parallel_requests_have_independent_transactions():
    """Запросы каталога и профиля не должны делить активную DB-сессию."""
    container = build_dishka_container()
    try:
        async with container() as first:
            first_transaction = await first.get(Transaction)
            assert await first.get(Transaction) is first_transaction
            async with container() as second:
                second_transaction = await second.get(Transaction)
                assert second_transaction is not first_transaction
    finally:
        await container.close()
