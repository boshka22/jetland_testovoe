"""Регистрация всех моделей в Django Admin."""

from django import forms
from django.contrib import admin

from .models import Category, Good, Order, OrderItem, PromoCode, PromoUsage, User


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "created_at")
    search_fields = ("name", "email")


@admin.register(Good)
class GoodAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "category", "is_promo_eligible")
    list_filter = ("category", "is_promo_eligible")
    search_fields = ("name",)


class PromoCodeAdminForm(forms.ModelForm):
    """Принимает скидку в процентах (15), сохраняет как долю (0.15)."""

    discount_percent = forms.DecimalField(
        min_value=0,
        max_value=100,
        label="Скидка, %",
        help_text="Введите процент: 15 = 15%, 10 = 10%.",
    )

    class Meta:
        model = PromoCode
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # При редактировании конвертируем сохранённую долю обратно в проценты
        if self.instance.pk and self.instance.discount_percent is not None:
            self.initial["discount_percent"] = self.instance.discount_percent * 100

    def clean_discount_percent(self):
        """Конвертирует введённые проценты в долю для хранения в БД.

        Args:
            Значение из поля формы (0–100).

        Returns:
            Десятичная доля (0.0–1.0).
        """
        value = self.cleaned_data.get("discount_percent")
        if value is not None:
            return (value / 100).quantize(__import__("decimal").Decimal("0.0001"))
        return value


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    """Промокоды. Скидка вводится в процентах, хранится как доля."""

    form = PromoCodeAdminForm
    list_display = (
        "id",
        "code",
        "discount_display",
        "expires_at",
        "max_usages",
        "used_count",
        "category",
    )
    search_fields = ("code",)
    list_filter = ("category",)
    readonly_fields = ("used_count",)

    @admin.display(description="Скидка")
    def discount_display(self, obj: PromoCode) -> str:
        """Отображает скидку в процентах в списке промокодов."""
        return f"{obj.discount_percent * 100:.2f}%"


@admin.register(PromoUsage)
class PromoUsageAdmin(admin.ModelAdmin):
    """Использования промокодов. Только просмотр — создаются сервисом."""

    list_display = ("id", "promo_code", "user", "order", "created_at")
    list_filter = ("promo_code",)
    search_fields = ("promo_code__code", "user__email")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("good", "quantity", "price", "discount", "total")

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Заказы. Только просмотр — создаются через API POST /api/orders/."""

    list_display = (
        "id",
        "user",
        "promo_code",
        "price",
        "discount",
        "total",
        "items_count",
        "created_at",
    )
    list_filter = ("promo_code", "created_at")
    search_fields = ("user__email", "user__name")
    readonly_fields = (
        "user",
        "promo_code",
        "price",
        "discount",
        "total",
        "created_at",
        "updated_at",
    )
    inlines = [OrderItemInline]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description="Кол-во товаров")
    def items_count(self, obj: Order) -> int:
        return obj.items.count()
