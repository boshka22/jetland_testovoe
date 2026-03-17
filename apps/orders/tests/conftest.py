"""Фабрики и фикстуры для тестов."""

from decimal import Decimal

import factory
import pytest

from apps.orders.models import Category, Good, PromoCode, User


class CategoryFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Категория {n}")

    class Meta:
        model = Category


class GoodFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Товар {n}")
    price = factory.LazyAttribute(lambda _: Decimal("100.00"))
    category = factory.SubFactory(CategoryFactory)
    is_promo_eligible = True

    class Meta:
        model = Good


class UserFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Пользователь {n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")

    class Meta:
        model = User


class PromoCodeFactory(factory.django.DjangoModelFactory):
    """discount_percent=0.10 (10%), expires_at=None (бессрочный), category=None."""

    code = factory.Sequence(lambda n: f"PROMO{n}")
    discount_percent = factory.LazyAttribute(lambda _: Decimal("0.10"))
    max_usages = 100
    used_count = 0
    expires_at = None
    category = None

    class Meta:
        model = PromoCode


@pytest.fixture()
def category():
    return CategoryFactory()


@pytest.fixture()
def good(category):
    return GoodFactory(category=category)


@pytest.fixture()
def user():
    return UserFactory()


@pytest.fixture()
def promo():
    return PromoCodeFactory(category=None)
