"""Глобальные обработчики исключений приложения SmartMonitor."""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.logger import logger


class SymbolNotFoundError(Exception):
    """Запрошенный символ отсутствует в кэше цен."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(f"Price for {symbol} not found in cache")


async def symbol_not_found_handler(request: Request, exc: SymbolNotFoundError) -> JSONResponse:
    """Возвращает 404 для отсутствующего символа."""
    logger.warning(
        "Символ не найден",
        method=request.method,
        url=str(request.url),
        symbol=exc.symbol,
    )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": f"Price for {exc.symbol} not found in cache"},
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Глобальный обработчик для всех необработанных исключений.
    Логирует ошибку с полным стек-трейсом и возвращает клиенту безопасный JSON.
    """
    # Логируем ошибку с полным traceback (уровень ERROR)
    logger.exception(
        "Необработанное исключение в приложении",
        method=request.method,
        url=str(request.url),
        client_host=request.client.host if request.client else "unknown",
        error_type=type(exc).__name__,
        error_message=str(exc),
    )

    # Возвращаем безопасный ответ клиенту (без утечки traceback)
    content = {
        "detail": "Internal Server Error. Пожалуйста, попробуйте позже или обратитесь в поддержку.",
    }
    if settings.DEBUG:
        content["error_type"] = type(exc).__name__

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
    )
