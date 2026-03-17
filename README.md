# Promo Orders

Тестовое задание Jetland. REST API для создания заказов с поддержкой промокодов. 

## Стек

| Слой        | Технология                  |
|-------------|-----------------------------|
| Язык        | Python 3.11                 |
| Фреймворк   | Django 4.2 + DRF 3.15       |
| База данных | PostgreSQL 15               |
| Контейнер   | Docker + docker-compose     |
| Линтеры     | black, ruff, pre-commit     |
| Тесты       | pytest + pytest-django      |
| Документация| Swagger (drf-spectacular)   |

---

## Быстрый старт

```bash
cp .env.example .env
docker-compose up --build
```

- API: **http://localhost:8000/api/orders/**
- Swagger: **http://localhost:8000/api/docs/**
- Admin: **http://localhost:8000/admin/**

Создать суперпользователя для Admin:

```bash
docker-compose exec web python manage.py createsuperuser
```

---

## API

### `POST /api/orders/`

Создаёт заказ. Если указан промокод — применяет скидку к подходящим товарам.

**Тело запроса**

```json
{
    "user_id": 1,
    "goods": [
        { "good_id": 1, "quantity": 2 }
    ],
    "promo_code": "SUMMER2025"
}
```

| Поле         | Тип     | Обязательно | Описание                 |
|--------------|---------|-------------|--------------------------|
| `user_id`    | integer | ✅           | ID пользователя          |
| `goods`      | array   | ✅           | Непустой список товаров  |
| `promo_code` | string  | ❌           | Строка промокода         |

**Успешный ответ — 201 Created**

```json
{
    "user_id": 1,
    "order_id": 1,
    "goods": [
        {
            "good_id": 1,
            "quantity": 2,
            "price": "100.00",
            "discount": "20.00",
            "total": "180.00"
        }
    ],
    "price": "200.00",
    "discount": "20.00",
    "total": "180.00"
}
```

**Ответы при ошибках**

| Статус | Причина                                                    |
|--------|------------------------------------------------------------|
| 400    | Некорректное тело запроса                                  |
| 404    | Несуществующий `user_id`, `good_id` или промокод           |
| 422    | Просроченный / исчерпанный / уже использованный промокод, или промокод не применим ни к одному товару |

Формат ошибки:
```json
{ "error": "Описание ошибки" }
```

---

## Правила применения промокода

Промокод применяется только при выполнении **всех** условий:

1. Промокод существует в базе данных.
2. Срок действия не истёк (или `expires_at` не задан).
3. `used_count < max_usages`.
4. Пользователь ещё не использовал этот промокод.
5. Хотя бы один товар в заказе подходит под промокод — `is_promo_eligible = True` и категория совпадает (если промокод ограничен категорией).

Если промокод есть, но ни один товар не подходит — возвращается `422`.
Если подходит только часть товаров — скидка применяется к ним, остальные идут по полной цене.

---

## Структура проекта

```
promo_orders/
├── apps/
│   └── orders/
│       ├── models.py         # User, Category, Good, PromoCode, Order, OrderItem, PromoUsage
│       ├── services.py       # бизнес-логика создания заказа
│       ├── serializers.py    # валидация запроса и формат ответа
│       ├── exceptions.py     # доменные исключения с HTTP-статусами
│       ├── views.py
│       ├── urls.py
│       ├── admin.py
│       ├── migrations/
│       └── tests/
├── config/
│   ├── settings.py
│   ├── exceptions.py         # кастомный обработчик исключений DRF
│   ├── urls.py
│   └── wsgi.py
├── requirements/
│   ├── base.txt
│   ├── test.txt
│   └── lint.txt
├── Dockerfile
├── docker-compose.yml
└── entrypoint.sh
```

---

## Тесты

```bash
docker-compose exec web pip install -r requirements/test.txt
docker-compose exec web pytest
```

---

## Линтеры

```bash
pip install -r requirements/lint.txt
pre-commit install   # запускается автоматически при git commit
black .
ruff check .
```

---

## Работа через Admin

Заказы создаются **только через API** — это гарантирует корректный расчёт
цен и соблюдение бизнес-правил. В Admin заказы доступны только для просмотра.

Порядок наполнения данными:

1. Создать категории → `/admin/orders/category/`
2. Создать товары с ценами → `/admin/orders/good/`
3. Создать пользователей → `/admin/orders/user/`
4. Создать промокоды → `/admin/orders/promocode/` *(скидка вводится в процентах: 15 = 15%)*
5. Создавать заказы → `POST /api/orders/`
