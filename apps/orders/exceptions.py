"""Доменные исключения с HTTP-статусами для автоматической обработки в DRF."""

from http import HTTPStatus


class OrderError(Exception):
    """Базовое исключение домена заказов."""

    http_status: int = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)


class UserNotFoundError(OrderError):
    http_status = HTTPStatus.NOT_FOUND

    def __init__(self, user_id: int) -> None:
        super().__init__(f"Пользователь с id={user_id} не найден.")


class GoodNotFoundError(OrderError):
    http_status = HTTPStatus.NOT_FOUND

    def __init__(self, good_id: int) -> None:
        super().__init__(f"Товар с id={good_id} не найден.")


class PromoCodeNotFoundError(OrderError):
    http_status = HTTPStatus.NOT_FOUND

    def __init__(self, code: str) -> None:
        super().__init__(f"Промокод '{code}' не существует.")


class PromoCodeExpiredError(OrderError):
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY

    def __init__(self, code: str) -> None:
        super().__init__(f"Срок действия промокода '{code}' истёк.")


class PromoCodeExhaustedError(OrderError):
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY

    def __init__(self, code: str) -> None:
        super().__init__(f"Промокод '{code}' достиг лимита использований.")


class PromoCodeAlreadyUsedError(OrderError):
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY

    def __init__(self, code: str, user_id: int) -> None:
        super().__init__(f"Пользователь {user_id} уже использовал промокод '{code}'.")


class PromoCodeNotApplicableError(OrderError):
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY

    def __init__(self, code: str) -> None:
        super().__init__(f"Промокод '{code}' не применим к товарам в корзине.")
