# Установка с Docker Compose

## 1. Требования

- Docker Engine и Docker Compose plugin;
- работающий Synapse;
- доступ к `homeserver.yaml` и возможность перезапустить Synapse;
- общая Docker-сеть между Synapse и мостом.

Узнать сети контейнера Synapse:

```bash
docker inspect matrix-synapse --format '{{json .NetworkSettings.Networks}}'
```

## 2. Подготовка проекта

```bash
git clone https://github.com/rodmanvictor/matrix-max-bridge.git
cd matrix-max-bridge
cp .env.example .env
mkdir -p data
cp example-config.yaml data/config.yaml
```

В `.env` укажите имя внешней сети Synapse:

```dotenv
MATRIX_DOCKER_NETWORK=matrix_default
TZ=Europe/Moscow
```

## 3. Настройка `data/config.yaml`

Минимально измените:

```yaml
homeserver:
  address: http://matrix-synapse:8008
  domain: example.org

appservice:
  address: http://mautrix-max:29320

bridge:
  permissions:
    "*": relay
    "example.org": user
    "@admin:example.org": admin
```

`homeserver.address` должен быть доступен из контейнера моста. `appservice.address`
должен быть доступен из контейнера Synapse.

## 4. Сборка

```bash
docker compose build
```

При нестабильном соединении с PyPI повторите сборку. Docker сохранит успешно
собранные слои. Не используйте `--no-cache` без необходимости.

## 5. Генерация Application Service registration

```bash
docker compose run --rm mautrix-max \
  python -m mautrix_max \
  -g \
  -c /opt/mautrix-max/data/config.yaml \
  -r /opt/mautrix-max/data/registration.yaml
```

После команды должны появиться:

- `data/config.yaml` с заполненными `as_token` и `hs_token`;
- `data/registration.yaml`.

Оба файла секретные и не должны попадать в Git.

## 6. Подключение к Synapse

Сделайте `registration.yaml` доступным контейнеру Synapse. Например, добавьте bind
mount в compose-файл Synapse:

```yaml
services:
  matrix-synapse:
    volumes:
      - /полный/путь/matrix-max-bridge/data/registration.yaml:/data/matrix-max-bridge-registration.yaml:ro
```

В `homeserver.yaml`:

```yaml
app_service_config_files:
  - /data/matrix-max-bridge-registration.yaml
```

Если список уже существует, добавьте новый элемент, не создавайте второй ключ
`app_service_config_files`.

Перезапустите Synapse и проверьте его лог:

```bash
docker restart matrix-synapse
docker logs --tail 100 matrix-synapse
```

## 7. Запуск моста

```bash
docker compose up -d
docker compose logs -f mautrix-max
```

Проверка импортов:

```bash
docker exec -i mautrix-max python - <<'PY'
import mautrix
import pymax
import mautrix_max

print("mautrix:", mautrix.__file__)
print("pymax:", pymax.__file__)
print("matrix-max-bridge:", mautrix_max.__file__)
PY
```

## 8. Первая авторизация

Вход выполняется по QR-коду MAX в интерактивном терминале на сервере. Matrix ID
должен иметь уровень `user` или `admin` в `bridge.permissions`:

```bash
docker compose exec -e MAX_AUTH_MXID=@you:example.org \
  -e MAX_DATA_DIR=/opt/mautrix-max/data \
  mautrix-max python -m mautrix_max.qr_cli
```

Отсканируйте QR-код в приложении MAX и, если терминал попросит, введите пароль
двухфакторной защиты. Не копируйте QR-код и пароль в чаты и логи. Сессия
сохраняется в `data/sessions/`, мост подхватывает её в течение 15 секунд.

Инструмент не перезаписывает существующую сессию. После `!max logout` в
`data/sessions/` остаётся каталог с профилем устройства; перед новым входом
перенесите его в резервную копию.

Проверить статус в чате с `@maxbot:example.org`:

```text
!max ping
```

## Обновление

```bash
git pull
docker compose build
docker compose up -d --force-recreate
```

Перед обновлением сохраните `data/`:

```bash
tar -czf matrix-max-bridge-data-$(date +%Y%m%d-%H%M%S).tar.gz data
```

Не запускайте одновременно старый и новый контейнер с одним каталогом сессий.
