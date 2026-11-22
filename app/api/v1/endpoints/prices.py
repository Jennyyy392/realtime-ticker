"""Эндпоинты для работы с ценами криптовалют."""

from fastapi import APIRouter, Depends

from app.services.price_service import PriceService, get_price_service

router = APIRouter()


@router.get("/{symbol}")
async def get_price(symbol: str, service: PriceService = Depends(get_price_service)):
    """Получить текущую цену криптовалюты через Service Layer."""
    return await service.get_price(symbol)
