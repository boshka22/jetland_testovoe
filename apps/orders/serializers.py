"""Сериализаторы для валидации входящих данных и форматирования ответов."""

from rest_framework import serializers


class OrderItemInputSerializer(serializers.Serializer):
    good_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class CreateOrderSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    goods = OrderItemInputSerializer(many=True, allow_empty=False)
    promo_code = serializers.CharField(max_length=50, required=False, allow_blank=False)

    def validate_goods(self, value: list[dict]) -> list[dict]:
        """Запрещает дублирующиеся good_id в одном заказе."""
        good_ids = [item["good_id"] for item in value]
        if len(good_ids) != len(set(good_ids)):
            raise serializers.ValidationError("Дублирующиеся good_id не допускаются.")
        return value


class OrderItemResponseSerializer(serializers.Serializer):
    good_id = serializers.IntegerField()
    quantity = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2)
    total = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderResponseSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    order_id = serializers.IntegerField()
    goods = OrderItemResponseSerializer(many=True)
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
