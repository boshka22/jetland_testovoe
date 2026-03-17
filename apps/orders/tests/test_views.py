"""API-тесты для эндпоинта создания заказа."""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.orders.models import Order

from .conftest import CategoryFactory, GoodFactory, PromoCodeFactory, UserFactory

ORDER_URL = "/api/orders/"


@pytest.fixture()
def client():
    return APIClient()


@pytest.fixture()
def user():
    return UserFactory()


@pytest.fixture()
def good():
    return GoodFactory(price=Decimal("100.00"))


@pytest.fixture()
def promo():
    return PromoCodeFactory(discount_percent=Decimal("0.10"), category=None)


@pytest.mark.django_db
class TestCreateOrderView:
    """Тесты для ``POST /api/orders/``."""

    def test_returns_201(self, client, user, good):
        """Минимально валидный запрос возвращает 201."""
        payload = {"user_id": user.pk, "goods": [{"good_id": good.pk, "quantity": 2}]}
        assert client.post(ORDER_URL, payload, format="json").status_code == status.HTTP_201_CREATED

    def test_response_shape(self, client, user, good):
        """Ответ содержит все обязательные ключи."""
        payload = {"user_id": user.pk, "goods": [{"good_id": good.pk, "quantity": 1}]}
        data = client.post(ORDER_URL, payload, format="json").json()
        for key in ("order_id", "user_id", "price", "discount", "total", "goods"):
            assert key in data
        for key in ("good_id", "quantity", "price", "discount", "total"):
            assert key in data["goods"][0]

    def test_totals_without_promo(self, client, user, good):
        """price == total при отсутствии промокода."""
        payload = {"user_id": user.pk, "goods": [{"good_id": good.pk, "quantity": 3}]}
        data = client.post(ORDER_URL, payload, format="json").json()
        assert Decimal(data["price"]) == Decimal("300.00")
        assert Decimal(data["discount"]) == Decimal("0.00")
        assert Decimal(data["total"]) == Decimal("300.00")

    def test_totals_with_promo(self, client, user, good, promo):
        """10 % на 2 × 100 → скидка 20, итого 180."""
        payload = {
            "user_id": user.pk,
            "goods": [{"good_id": good.pk, "quantity": 2}],
            "promo_code": promo.code,
        }
        data = client.post(ORDER_URL, payload, format="json").json()
        assert Decimal(data["price"]) == Decimal("200.00")
        assert Decimal(data["discount"]) == Decimal("20.00")
        assert Decimal(data["total"]) == Decimal("180.00")

    def test_order_saved_in_db(self, client, user, good):
        """После успешного запроса запись Order есть в БД."""
        client.post(ORDER_URL, {"user_id": user.pk, "goods": [{"good_id": good.pk, "quantity": 1}]}, format="json")
        assert Order.objects.filter(user=user).exists()

    # -- 400 ошибки валидации -----------------------------------------------

    def test_missing_user_id_returns_400(self, client, good):
        payload = {"goods": [{"good_id": good.pk, "quantity": 1}]}
        assert client.post(ORDER_URL, payload, format="json").status_code == status.HTTP_400_BAD_REQUEST

    def test_empty_goods_returns_400(self, client, user):
        payload = {"user_id": user.pk, "goods": []}
        assert client.post(ORDER_URL, payload, format="json").status_code == status.HTTP_400_BAD_REQUEST

    def test_zero_quantity_returns_400(self, client, user, good):
        payload = {"user_id": user.pk, "goods": [{"good_id": good.pk, "quantity": 0}]}
        assert client.post(ORDER_URL, payload, format="json").status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_good_ids_returns_400(self, client, user, good):
        payload = {
            "user_id": user.pk,
            "goods": [{"good_id": good.pk, "quantity": 1}, {"good_id": good.pk, "quantity": 2}],
        }
        assert client.post(ORDER_URL, payload, format="json").status_code == status.HTTP_400_BAD_REQUEST

    # -- 404 не найдено -----------------------------------------------------

    def test_unknown_user_returns_404(self, client, good):
        response = client.post(ORDER_URL, {"user_id": 99999, "goods": [{"good_id": good.pk, "quantity": 1}]}, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.json()

    def test_unknown_good_returns_404(self, client, user):
        response = client.post(ORDER_URL, {"user_id": user.pk, "goods": [{"good_id": 99999, "quantity": 1}]}, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.json()

    def test_unknown_promo_returns_404(self, client, user, good):
        payload = {"user_id": user.pk, "goods": [{"good_id": good.pk, "quantity": 1}], "promo_code": "ПРИЗРАК"}
        assert client.post(ORDER_URL, payload, format="json").status_code == status.HTTP_404_NOT_FOUND

    # -- 422 нарушения бизнес-правил ----------------------------------------

    def test_expired_promo_returns_422(self, client, user, good):
        promo = PromoCodeFactory(expires_at=timezone.now() - timezone.timedelta(seconds=1))
        payload = {"user_id": user.pk, "goods": [{"good_id": good.pk, "quantity": 1}], "promo_code": promo.code}
        assert client.post(ORDER_URL, payload, format="json").status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_exhausted_promo_returns_422(self, client, user, good):
        promo = PromoCodeFactory(max_usages=1, used_count=1)
        payload = {"user_id": user.pk, "goods": [{"good_id": good.pk, "quantity": 1}], "promo_code": promo.code}
        assert client.post(ORDER_URL, payload, format="json").status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_already_used_promo_returns_422(self, client, user, good, promo):
        payload = {"user_id": user.pk, "goods": [{"good_id": good.pk, "quantity": 1}], "promo_code": promo.code}
        client.post(ORDER_URL, payload, format="json")
        assert client.post(ORDER_URL, payload, format="json").status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_promo_wrong_category_returns_422(self, client, user):
        """Промокод, не подходящий ни одному товару в заказе, возвращает 422."""
        cat_a, cat_b = CategoryFactory(), CategoryFactory()
        good = GoodFactory(price=Decimal("100.00"), category=cat_b)
        promo = PromoCodeFactory(discount_percent=Decimal("0.10"), category=cat_a)
        payload = {"user_id": user.pk, "goods": [{"good_id": good.pk, "quantity": 1}], "promo_code": promo.code}
        response = client.post(ORDER_URL, payload, format="json")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "error" in response.json()

    def test_promo_partial_category_applied(self, client, user):
        """Промокод со своей категорией применяется только к подходящим товарам."""
        cat_a, cat_b = CategoryFactory(), CategoryFactory()
        good_a = GoodFactory(price=Decimal("100.00"), category=cat_a)
        good_b = GoodFactory(price=Decimal("100.00"), category=cat_b)
        promo = PromoCodeFactory(discount_percent=Decimal("0.10"), category=cat_a)
        payload = {
            "user_id": user.pk,
            "goods": [
                {"good_id": good_a.pk, "quantity": 1},
                {"good_id": good_b.pk, "quantity": 1},
            ],
            "promo_code": promo.code,
        }
        data = client.post(ORDER_URL, payload, format="json").json()
        assert Decimal(data["discount"]) == Decimal("10.00")
        assert Decimal(data["total"]) == Decimal("190.00")
