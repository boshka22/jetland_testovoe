# Promo Orders

REST API для создания заказов с поддержкой промокодов. Тестовое задание.

## Стек технологий

| Слой        | Технология              |
|-------------|-------------------------|
| Язык        | Python 3.11             |
| Фреймворк   | Django 4.2 + DRF 3.15   |
| База данных | PostgreSQL 15           |
| Контейнер   | Docker + docker-compose |
| Линтеры     | black, ruff, pre-commit |
| Тесты       | pytest + pytest-django  |

---

## Быстрый старт

```bash
# 1. Скопировать файл окружения
cp .env.example .env

# 2. Собрать и запустить контейнеры
#    При старте автоматически применяются миграции
docker-compose up --build
```

API доступен по адресу **http://localhost:8000**

Админка доступна по адресу **http://localhost:8000/admin/**

> Чтобы войти в админку, создайте суперпользователя:
> ```bash
> docker-compose exec web python manage.py createsuperuser
> ```

---

## API

### `POST /api/orders/`

Создать новый заказ, опционально применив промокод.

**Тело запроса**

```json
{
  "user_id": 1,
  "goods": [
    {
      "good_id": 1,
      "quantity": 2
    }
  ],
  "promo_code": "SUMMER2025"
}
```

| Поле         | Тип     | Обязательно | Описание                |
|--------------|---------|-------------|-------------------------|
| `user_id`    | integer | ✅           | ID пользователя         |
| `goods`      | array   | ✅           | Непустой список товаров |
| `promo_code` | string  | ❌           | Строка промокода        |

**Успешный ответ — 201 Created**

```json
{
  "order_id": 1,
  "user_id": 1,
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

| Статус | Причина                                                  |
|--------|----------------------------------------------------------|
| 400    | Некорректное тело запроса (отсутствуют поля, и т.д.)     |
| 404    | Несуществующий `user_id`, `good_id` или промокод         |
| 422    | Просроченный / исчерпанный / уже использованный промокод |

Все ошибки возвращаются в формате:

```json
{
  "error": "Описание ошибки"
}
```

---

## Правила применения промокода

Промокод применяется только при выполнении **всех** условий:

1. Промокод существует в базе данных.
2. Срок действия (`expires_at`) не истёк, или он не задан.
3. Количество использований не превысило лимит (`used_count < max_usages`).
4. Данный пользователь ещё не использовал этот промокод.
5. Если промокод привязан к категории или товары исключены из акций (`is_promo_eligible = False`) — промокод применяется
   только к подходящим товарам. Если ни один товар в заказе не подходит — возвращается ошибка `422`.

---

## Структура проекта

```
promo_orders/
├── apps/
│   └── orders/               # единственное приложение
│       ├── models.py         # все модели: User, Good, Category,
│       │                     #   PromoCode, PromoUsage, Order, OrderItem
│       ├── services.py       # вся бизнес-логика создания заказа
│       ├── serializers.py    # валидация входных и выходных данных
│       ├── exceptions.py     # доменные исключения с HTTP-статусами
│       ├── views.py          # тонкий HTTP-слой
│       ├── urls.py           # маршруты
│       ├── admin.py          # регистрация моделей в Django Admin
│       ├── migrations/
│       │   └── 0001_initial.py
│       └── tests/
│           ├── conftest.py   # фабрики и фикстуры
│           ├── test_services.py
│           └── test_views.py
├── config/
│   ├── settings.py           # все настройки в одном файле
│   ├── exceptions.py         # кастомный обработчик исключений DRF
│   ├── urls.py
│   └── wsgi.py
├── requirements/
│   ├── base.txt
│   ├── test.txt
│   └── lint.txt
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh             # ожидает PostgreSQL, применяет миграции
├── pyproject.toml            # конфиг black, ruff, pytest
└── .pre-commit-config.yaml
```

---

## Запуск тестов

```bash
# Внутри контейнера
docker-compose exec web pip install -r requirements/test.txt
docker-compose exec web pytest

# Или локально (требуется PostgreSQL на localhost:5432)
pip install -r requirements/test.txt
pytest
```

---

## Проверка качества кода

```bash
# Установить линтеры
pip install -r requirements/lint.txt

# Установить pre-commit хуки (запускаются автоматически при git commit)
pre-commit install

# Запустить вручную
black .
ruff check .
```

---

## Работа с данными через Admin

Заказы создаются **только через API** — это гарантирует корректный расчёт
цен и соблюдение бизнес-правил. В Admin все заказы доступны только для
просмотра.

Для наполнения БД тестовыми данными через Admin:

1. Создать **категории** (`/admin/orders/category/`)
2. Создать **товары** с ценами и категориями (`/admin/orders/good/`)
3. Создать **пользователей** (`/admin/orders/user/`)
4. Создать **промокоды** с нужными параметрами (`/admin/orders/promocode/`)
5. Создавать заказы через **API** `POST /api/orders/`
