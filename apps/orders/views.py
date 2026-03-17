from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.serializers import CreateOrderSerializer, OrderResponseSerializer
from apps.orders.services import OrderCreationService

_EXAMPLE_RESPONSE = {
    "user_id": 1,
    "order_id": 1,
    "goods": [
        {
            "good_id": 1,
            "quantity": 2,
            "price": "100.00",
            "discount": "20.00",
            "total": "180.00",
        }
    ],
    "price": "200.00",
    "discount": "20.00",
    "total": "180.00",
}


class CreateOrderView(APIView):

    @extend_schema(
        summary="Создать заказ",
        description=(
            "Создаёт заказ. Если указан промокод — " "применяет скидку к подходящим товарам."
        ),
        request=CreateOrderSerializer,
        responses={
            201: OpenApiResponse(
                response=OrderResponseSerializer,
                description="Заказ успешно создан.",
                examples=[
                    OpenApiExample(name="Пример", value=_EXAMPLE_RESPONSE),
                ],
            ),
            400: OpenApiResponse(description="Ошибка валидации входных данных."),
            404: OpenApiResponse(
                description="Пользователь, товар или промокод не найдены.",
                examples=[
                    OpenApiExample(
                        "Пользователь",
                        value={"error": "Пользователь с id=99 не найден."},
                    ),
                    OpenApiExample(
                        "Товар",
                        value={"error": "Товар с id=99 не найден."},
                    ),
                    OpenApiExample(
                        "Промокод",
                        value={"error": "Промокод 'XYZ' не существует."},
                    ),
                ],
            ),
            422: OpenApiResponse(
                description="Нарушение бизнес-правила промокода.",
                examples=[
                    OpenApiExample(
                        "Просрочен",
                        value={"error": "Срок действия промокода 'X' истёк."},
                    ),
                    OpenApiExample(
                        "Исчерпан",
                        value={"error": "Промокод 'X' достиг лимита использований."},
                    ),
                    OpenApiExample(
                        "Уже использован",
                        value={"error": ("Пользователь 1 уже использовал промокод 'X'.")},
                    ),
                    OpenApiExample(
                        "Не применим",
                        value={"error": "Промокод 'X' не применим к товарам в корзине."},
                    ),
                ],
            ),
        },
        tags=["Заказы"],
    )
    def post(self, request: Request) -> Response:
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        order = OrderCreationService().create_order(
            user_id=data["user_id"],
            goods_data=data["goods"],
            promo_code=data.get("promo_code"),
        )
        return Response(self._build_response(order), status=status.HTTP_201_CREATED)

    @staticmethod
    def _build_response(order: Order) -> dict:
        items = order.items.select_related("good").all()
        payload = {
            "user_id": order.user_id,
            "order_id": order.pk,
            "goods": [
                {
                    "good_id": item.good_id,
                    "quantity": item.quantity,
                    "price": item.price,
                    "discount": item.discount,
                    "total": item.total,
                }
                for item in items
            ],
            "price": order.price,
            "discount": order.discount,
            "total": order.total,
        }
        return OrderResponseSerializer(payload).data
