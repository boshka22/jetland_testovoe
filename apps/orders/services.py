"""Бизнес-логика создания заказов."""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.orders.exceptions import (
    GoodNotFoundError,
    PromoCodeAlreadyUsedError,
    PromoCodeExhaustedError,
    PromoCodeExpiredError,
    PromoCodeNotApplicableError,
    PromoCodeNotFoundError,
    UserNotFoundError,
)
from apps.orders.models import Good, Order, OrderItem, PromoCode, PromoUsage, User

_CENT = Decimal("0.01")


@dataclass
class _ItemCalculation:
    good: Good
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    subtotal: Decimal
    total: Decimal


@dataclass
class _OrderTotals:
    price: Decimal = field(default_factory=Decimal)
    discount: Decimal = field(default_factory=Decimal)
    total: Decimal = field(default_factory=Decimal)


class OrderCreationService:
    """Создаёт заказ в рамках одной атомарной транзакции.

    Промокод блокируется через SELECT FOR UPDATE для защиты от гонок
    при одновременном исчерпании лимита использований.
    """

    def create_order(
        self,
        user_id: int,
        goods_data: list[dict],
        promo_code: str | None = None,
    ) -> Order:
        """Создаёт и сохраняет заказ.

        Args:
            user_id: ID пользователя.
            goods_data: Список ``{"good_id": int, "quantity": int}``.
            promo_code: Строка промокода или ``None``.

        Returns:
            Созданный экземпляр Order.

        Raises:
            UserNotFoundError: Пользователь не найден.
            GoodNotFoundError: Товар не найден.
            PromoCodeNotFoundError: Промокод не существует.
            PromoCodeNotApplicableError: Промокод не применим ни к одному товару.
            PromoCodeExpiredError: Промокод просрочен.
            PromoCodeExhaustedError: Лимит использований исчерпан.
            PromoCodeAlreadyUsedError: Пользователь уже использовал промокод.
        """
        user = self._get_user(user_id)
        goods = self._get_goods(goods_data)

        # Проверяем применимость промокода до начала транзакции,
        # чтобы не удерживать SELECT FOR UPDATE зря при неподходящей корзине.
        if promo_code is not None:
            self._check_promo_applicable_to_goods_by_code(promo_code, goods)

        with transaction.atomic():
            promo = self._validate_and_lock_promo(promo_code, user_id)
            items = self._calculate_items(goods_data, goods, promo)
            totals = self._calculate_order_totals(items)
            order = self._persist_order(user, promo, items, totals)
        return order

    def _get_user(self, user_id: int) -> User:
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(user_id) from None

    def _get_goods(self, goods_data: list[dict]) -> dict[int, Good]:
        """Загружает товары одним запросом, включая связь category."""
        requested_ids = {item["good_id"] for item in goods_data}
        goods_map: dict[int, Good] = {
            g.pk: g for g in Good.objects.select_related("category").filter(pk__in=requested_ids)
        }
        for good_id in requested_ids:
            if good_id not in goods_map:
                raise GoodNotFoundError(good_id)
        return goods_map

    def _validate_and_lock_promo(self, code: str | None, user_id: int) -> PromoCode | None:
        """Валидирует промокод и захватывает строковую блокировку.

        select_related нельзя совмещать с select_for_update на nullable FK —
        PostgreSQL запрещает FOR UPDATE на nullable стороне LEFT OUTER JOIN.
        Поэтому блокируем без JOIN; category загрузится отдельным запросом.
        """
        if code is None:
            return None

        try:
            promo = PromoCode.objects.select_for_update().get(code=code)
        except PromoCode.DoesNotExist:
            raise PromoCodeNotFoundError(code) from None

        if promo.expires_at is not None and promo.expires_at < timezone.now():
            raise PromoCodeExpiredError(code)

        if promo.used_count >= promo.max_usages:
            raise PromoCodeExhaustedError(code)

        if PromoUsage.objects.filter(promo_code=promo, user_id=user_id).exists():
            raise PromoCodeAlreadyUsedError(code, user_id)

        return promo

    def _check_promo_applicable_to_goods_by_code(
        self, code: str, goods_map: dict[int, Good]
    ) -> None:
        """Проверяет применимость промокода до взятия блокировки.

        Делает лёгкий SELECT без FOR UPDATE — только чтобы узнать
        category_id промокода и проверить корзину.
        Не валидирует лимиты и срок — это делает _validate_and_lock_promo.

        Raises:
            PromoCodeNotFoundError: Промокод не найден.
            PromoCodeNotApplicableError: Ни один товар не получит скидку.
        """
        try:
            promo = PromoCode.objects.only("code", "category_id").get(code=code)
        except PromoCode.DoesNotExist:
            raise PromoCodeNotFoundError(code) from None

        applicable = any(self._is_promo_applicable(good, promo) for good in goods_map.values())
        if not applicable:
            raise PromoCodeNotApplicableError(code)

    def _calculate_items(
        self,
        goods_data: list[dict],
        goods_map: dict[int, Good],
        promo: PromoCode | None,
    ) -> list[_ItemCalculation]:
        """Рассчитывает скидку по каждой строке заказа."""
        results: list[_ItemCalculation] = []
        for item in goods_data:
            good = goods_map[item["good_id"]]
            quantity = item["quantity"]
            subtotal = (good.price * quantity).quantize(_CENT, rounding=ROUND_HALF_UP)

            discount_amount = Decimal("0.00")
            if promo is not None and self._is_promo_applicable(good, promo):
                discount_amount = (subtotal * promo.discount_percent).quantize(
                    _CENT, rounding=ROUND_HALF_UP
                )

            results.append(
                _ItemCalculation(
                    good=good,
                    quantity=quantity,
                    unit_price=good.price,
                    discount_amount=discount_amount,
                    subtotal=subtotal,
                    total=subtotal - discount_amount,
                )
            )
        return results

    @staticmethod
    def _is_promo_applicable(good: Good, promo: PromoCode) -> bool:
        """Возвращает True, если промокод применим к товару."""
        return good.is_promo_eligible and (
            promo.category_id is None or promo.category_id == good.category_id
        )

    @staticmethod
    def _calculate_order_totals(items: list[_ItemCalculation]) -> _OrderTotals:
        price = sum((i.subtotal for i in items), Decimal("0.00"))
        discount = sum((i.discount_amount for i in items), Decimal("0.00"))
        return _OrderTotals(price=price, discount=discount, total=price - discount)

    @staticmethod
    def _persist_order(
        user: User,
        promo: PromoCode | None,
        items: list[_ItemCalculation],
        totals: _OrderTotals,
    ) -> Order:
        """Сохраняет заказ, строки и запись об использовании промокода."""
        order = Order.objects.create(
            user=user,
            promo_code=promo,
            price=totals.price,
            discount=totals.discount,
            total=totals.total,
        )
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    good=item.good,
                    quantity=item.quantity,
                    price=item.unit_price,
                    discount=item.discount_amount,
                    total=item.total,
                )
                for item in items
            ]
        )
        if promo is not None:
            PromoUsage.objects.create(promo_code=promo, user=user, order=order)
            PromoCode.objects.filter(pk=promo.pk).update(used_count=F("used_count") + 1)
        return order
