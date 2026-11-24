"""Эндпоинты для работы с ценами криптовалют."""

from fastapi import APIRouter, Depends, Path

from app.services.price_service import PriceService, get_price_service

router = APIRouter()


@router.get("/{symbol}")
async def get_price(
    symbol: str = Path(..., min_length=2, max_length=10, pattern="^[a-zA-Z0-9]+$"),
    service: PriceService = Depends(get_price_service),
):
    """Получить текущую цену криптовалюты через Service Layer."""
    return await service.get_price(symbol)
