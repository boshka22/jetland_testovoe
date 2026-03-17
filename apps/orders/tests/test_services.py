"""Юнит- и интеграционные тесты для OrderCreationService."""

from decimal import Decimal

import pytest
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
from apps.orders.models import PromoUsage
from apps.orders.services import OrderCreationService, _ItemCalculation

from .conftest import CategoryFactory, GoodFactory, PromoCodeFactory, UserFactory


def _make_item(subtotal: str, discount: str) -> _ItemCalculation:
    """Создаёт минимальный ``_ItemCalculation`` для тестирования итогов."""
    s, d = Decimal(subtotal), Decimal(discount)
    return _ItemCalculation(
        good=None,  # type: ignore[arg-type]
        quantity=1,
        unit_price=s,
        discount_amount=d,
        subtotal=s,
        total=s - d,
    )


class TestCalculateOrderTotals:
    """Тесты чистого метода агрегации итогов."""

    def test_no_discount(self):
        """Без скидок price равно total."""
        items = [_make_item("100.00", "0.00"), _make_item("200.00", "0.00")]
        totals = OrderCreationService._calculate_order_totals(items)
        assert totals.price == Decimal("300.00")
        assert totals.discount == Decimal("0.00")
        assert totals.total == Decimal("300.00")

    def test_partial_discount(self):
        """Только часть товаров со скидкой."""
        items = [_make_item("100.00", "10.00"), _make_item("200.00", "0.00")]
        totals = OrderCreationService._calculate_order_totals(items)
        assert totals.price == Decimal("300.00")
        assert totals.discount == Decimal("10.00")
        assert totals.total == Decimal("290.00")

    def test_full_discount(self):
        """Скидка применена ко всем строкам."""
        items = [_make_item("100.00", "10.00"), _make_item("200.00", "20.00")]
        totals = OrderCreationService._calculate_order_totals(items)
        assert totals.price == Decimal("300.00")
        assert totals.discount == Decimal("30.00")
        assert totals.total == Decimal("270.00")


class TestIsPromoApplicable:
    """Тесты предиката применимости скидки."""

    def test_eligible_no_category_restriction(self):
        """Подходящий товар + промокод без ограничений → применяется."""
        good = GoodFactory.build(is_promo_eligible=True, category_id=1)
        promo = PromoCodeFactory.build(category_id=None)
        assert OrderCreationService._is_promo_applicable(good, promo) is True

    def test_ineligible_good(self):
        """Товар, исключённый из акций → не применяется."""
        good = GoodFactory.build(is_promo_eligible=False, category_id=1)
        promo = PromoCodeFactory.build(category_id=None)
        assert OrderCreationService._is_promo_applicable(good, promo) is False

    def test_category_matches(self):
        """Совпадение категорий → применяется."""
        good = GoodFactory.build(is_promo_eligible=True, category_id=5)
        promo = PromoCodeFactory.build(category_id=5)
        assert OrderCreationService._is_promo_applicable(good, promo) is True

    def test_category_mismatch(self):
        """Категория не совпадает → не применяется."""
        good = GoodFactory.build(is_promo_eligible=True, category_id=5)
        promo = PromoCodeFactory.build(category_id=99)
        assert OrderCreationService._is_promo_applicable(good, promo) is False

    def test_ineligible_good_category_matches(self):
        """Неподходящий товар — категория не имеет значения."""
        good = GoodFactory.build(is_promo_eligible=False, category_id=5)
        promo = PromoCodeFactory.build(category_id=5)
        assert OrderCreationService._is_promo_applicable(good, promo) is False


@pytest.mark.django_db(transaction=True)
class TestOrderCreation:
    """Интеграционные тесты полного цикла создания заказа."""

    def setup_method(self):
        self.service = OrderCreationService()

    def test_create_order_without_promo(self):
        """Заказ без промокода сохраняет корректные итоги."""
        user = UserFactory()
        good = GoodFactory(price=Decimal("100.00"))
        order = self.service.create_order(
            user_id=user.pk,
            goods_data=[{"good_id": good.pk, "quantity": 2}],
        )
        assert order.price == Decimal("200.00")
        assert order.discount == Decimal("0.00")
        assert order.total == Decimal("200.00")
        assert order.promo_code is None

    def test_create_order_with_promo(self):
        """Скидка 10 % на 2 × 100 применяется корректно."""
        user = UserFactory()
        good = GoodFactory(price=Decimal("100.00"))
        promo = PromoCodeFactory(discount_percent=Decimal("0.10"), category=None)
        order = self.service.create_order(
            user_id=user.pk,
            goods_data=[{"good_id": good.pk, "quantity": 2}],
            promo_code=promo.code,
        )
        assert order.price == Decimal("200.00")
        assert order.discount == Decimal("20.00")
        assert order.total == Decimal("180.00")

    def test_promo_only_applies_to_matching_category(self):
        """Промокод для cat_a применяется к cat_a, но не к cat_b."""
        user = UserFactory()
        cat_a, cat_b = CategoryFactory(), CategoryFactory()
        good_a = GoodFactory(price=Decimal("100.00"), category=cat_a)
        good_b = GoodFactory(price=Decimal("100.00"), category=cat_b)
        promo = PromoCodeFactory(discount_percent=Decimal("0.10"), category=cat_a)
        order = self.service.create_order(
            user_id=user.pk,
            goods_data=[
                {"good_id": good_a.pk, "quantity": 1},
                {"good_id": good_b.pk, "quantity": 1},
            ],
            promo_code=promo.code,
        )
        assert order.price == Decimal("200.00")
        assert order.discount == Decimal("10.00")
        assert order.total == Decimal("190.00")

    def test_promo_not_applicable_raises_error(self):
        """Промокод, не подходящий ни одному товару, возвращает ошибку."""
        user = UserFactory()
        good = GoodFactory(price=Decimal("100.00"), is_promo_eligible=False)
        promo = PromoCodeFactory(discount_percent=Decimal("0.10"))
        with pytest.raises(PromoCodeNotApplicableError):
            self.service.create_order(
                user_id=user.pk,
                goods_data=[{"good_id": good.pk, "quantity": 2}],
                promo_code=promo.code,
            )

    def test_promo_partial_category_applies_to_eligible_goods(self):
        """Промокод применяется к товарам своей категории, остальные — без скидки."""
        user = UserFactory()
        cat_a, cat_b = CategoryFactory(), CategoryFactory()
        good_a = GoodFactory(price=Decimal("100.00"), category=cat_a)
        good_b = GoodFactory(price=Decimal("100.00"), category=cat_b)
        promo = PromoCodeFactory(discount_percent=Decimal("0.10"), category=cat_a)
        order = self.service.create_order(
            user_id=user.pk,
            goods_data=[
                {"good_id": good_a.pk, "quantity": 1},
                {"good_id": good_b.pk, "quantity": 1},
            ],
            promo_code=promo.code,
        )
        assert order.discount == Decimal("10.00")
        assert order.total == Decimal("190.00")

    def test_used_count_incremented(self):
        """``used_count`` увеличивается на 1 после успешного заказа."""
        user, good = UserFactory(), GoodFactory()
        promo = PromoCodeFactory(used_count=0)
        self.service.create_order(
            user_id=user.pk,
            goods_data=[{"good_id": good.pk, "quantity": 1}],
            promo_code=promo.code,
        )
        promo.refresh_from_db()
        assert promo.used_count == 1

    def test_promo_usage_record_created(self):
        """Запись PromoUsage создаётся при успешном применении."""
        user, good = UserFactory(), GoodFactory()
        promo = PromoCodeFactory()
        order = self.service.create_order(
            user_id=user.pk,
            goods_data=[{"good_id": good.pk, "quantity": 1}],
            promo_code=promo.code,
        )
        assert PromoUsage.objects.filter(promo_code=promo, user=user, order=order).exists()

    def test_order_items_persisted(self):
        """Все строки заказа сохраняются в БД."""
        user = UserFactory()
        good1 = GoodFactory(price=Decimal("50.00"))
        good2 = GoodFactory(price=Decimal("75.00"))
        order = self.service.create_order(
            user_id=user.pk,
            goods_data=[
                {"good_id": good1.pk, "quantity": 3},
                {"good_id": good2.pk, "quantity": 1},
            ],
        )
        assert order.items.count() == 2

    def test_raises_user_not_found(self):
        """Несуществующий пользователь вызывает UserNotFoundError."""
        good = GoodFactory()
        with pytest.raises(UserNotFoundError):
            self.service.create_order(
                user_id=99999,
                goods_data=[{"good_id": good.pk, "quantity": 1}],
            )

    def test_raises_good_not_found(self):
        """Несуществующий товар вызывает GoodNotFoundError."""
        user = UserFactory()
        with pytest.raises(GoodNotFoundError):
            self.service.create_order(
                user_id=user.pk,
                goods_data=[{"good_id": 99999, "quantity": 1}],
            )

    def test_raises_promo_not_found(self):
        """Неизвестный промокод вызывает PromoCodeNotFoundError."""
        user, good = UserFactory(), GoodFactory()
        with pytest.raises(PromoCodeNotFoundError):
            self.service.create_order(
                user_id=user.pk,
                goods_data=[{"good_id": good.pk, "quantity": 1}],
                promo_code="НЕСУЩЕСТВУЮЩИЙ",
            )

    def test_raises_promo_expired(self):
        """Просроченный промокод вызывает PromoCodeExpiredError."""
        user, good = UserFactory(), GoodFactory()
        delta = timezone.timedelta(seconds=1)
        promo = PromoCodeFactory(expires_at=timezone.now() - delta)
        with pytest.raises(PromoCodeExpiredError):
            self.service.create_order(
                user_id=user.pk,
                goods_data=[{"good_id": good.pk, "quantity": 1}],
                promo_code=promo.code,
            )

    def test_raises_promo_exhausted(self):
        """Исчерпанный промокод вызывает PromoCodeExhaustedError."""
        user, good = UserFactory(), GoodFactory()
        promo = PromoCodeFactory(max_usages=1, used_count=1)
        with pytest.raises(PromoCodeExhaustedError):
            self.service.create_order(
                user_id=user.pk,
                goods_data=[{"good_id": good.pk, "quantity": 1}],
                promo_code=promo.code,
            )

    def test_raises_promo_already_used(self):
        """Повторное применение промокода тем же пользователем вызывает ошибку."""
        user, good = UserFactory(), GoodFactory()
        promo = PromoCodeFactory(max_usages=100)
        self.service.create_order(
            user_id=user.pk,
            goods_data=[{"good_id": good.pk, "quantity": 1}],
            promo_code=promo.code,
        )
        with pytest.raises(PromoCodeAlreadyUsedError):
            self.service.create_order(
                user_id=user.pk,
                goods_data=[{"good_id": good.pk, "quantity": 1}],
                promo_code=promo.code,
            )

    def test_race_condition_does_not_exceed_max_usages(self):
        """Конкурентное использование последнего слота промокода безопасно.

        Два потока одновременно пытаются использовать промокод с ``max_usages=1``.
        ``SELECT FOR UPDATE`` гарантирует, что ровно один успешен,
        а второй получает :class:`~apps.orders.exceptions.PromoCodeExhaustedError`.
        """
        import threading

        user1, user2 = UserFactory(), UserFactory()
        good = GoodFactory()
        promo = PromoCodeFactory(max_usages=1, used_count=0)
        results, errors = [], []

        def attempt(user):
            try:
                self.service.create_order(
                    user_id=user.pk,
                    goods_data=[{"good_id": good.pk, "quantity": 1}],
                    promo_code=promo.code,
                )
                results.append("ok")
            except PromoCodeExhaustedError:
                errors.append("exhausted")

        t1 = threading.Thread(target=attempt, args=(user1,))
        t2 = threading.Thread(target=attempt, args=(user2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        promo.refresh_from_db()
        assert promo.used_count == 1
        assert len(results) == 1
        assert len(errors) == 1
