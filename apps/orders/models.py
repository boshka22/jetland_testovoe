"""Доменные модели приложения."""

from django.db import models


class Category(models.Model):
    """Категория товаров для ограничения промокодов."""

    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self) -> str:
        return self.name


class User(models.Model):
    """Пользователь приложения. Аутентификация вне scope задачи."""

    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"


class Good(models.Model):
    """Товар с фиксированной ценой и флагом участия в акциях."""

    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="goods",
    )
    is_promo_eligible = models.BooleanField(
        default=True,
        help_text="Снимите галочку, чтобы исключить товар из всех акций.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

    def __str__(self) -> str:
        return f"{self.name} ({self.price})"


class PromoCode(models.Model):
    """Промокод со скидкой, лимитом использований и опциональной категорией.

    Поле ``discount_percent`` хранит долю (0.15 = 15%).
    ``used_count`` обновляется атомарно через F()-выражения.
    """

    code = models.CharField(max_length=50, unique=True, db_index=True)
    discount_percent = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        help_text="Скидка в виде десятичной доли: 0.10 = 10%, 0.15 = 15%.",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Оставьте пустым для бессрочного промокода.",
    )
    max_usages = models.PositiveIntegerField()
    used_count = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promo_codes",
        help_text="Если указано — скидка применяется только к товарам этой категории.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Промокод"
        verbose_name_plural = "Промокоды"

    def __str__(self) -> str:
        return self.code


class Order(models.Model):
    """Заказ покупателя. Финансовые итоги рассчитываются сервисом."""

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="orders")
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def __str__(self) -> str:
        return f"Заказ #{self.pk} — пользователь {self.user_id}"


class PromoUsage(models.Model):
    """Факт применения промокода к заказу. Неизменяема после создания.

    UniqueConstraint на (promo_code, user) реализует правило
    «один промокод — одному пользователю» на уровне БД.
    """

    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.PROTECT,
        related_name="usages",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="promo_usages",
    )
    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="promo_usage",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Использование промокода"
        verbose_name_plural = "Использования промокодов"
        constraints = [
            models.UniqueConstraint(
                fields=["promo_code", "user"],
                name="unique_promo_usage_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.promo_code.code} — user {self.user_id} — order {self.order_id}"


class OrderItem(models.Model):
    """Строка заказа. Хранит снимок цены на момент покупки."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    good = models.ForeignKey(Good, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Строка заказа"
        verbose_name_plural = "Строки заказа"

    def __str__(self) -> str:
        return f"Строка #{self.pk} — товар {self.good_id} x{self.quantity}"
