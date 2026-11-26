# matrix-max-bridge

[![CI](https://github.com/rodmanvictor/matrix-max-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/rodmanvictor/matrix-max-bridge/actions/workflows/ci.yml)
[![Лицензия MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Версия](https://img.shields.io/badge/version-0.14.0-orange.svg)](CHANGELOG.md)

Неофициальный многопользовательский мост **Matrix ↔ MAX** на Python. Мост построен на
[`mautrix-python`](https://github.com/mautrix/python) и использует vendored-версию
[`PyMax`](https://github.com/MaxApiTeam/PyMax) для подключения к MAX.

Проект продолжает [pymatrix-max](https://github.com/NijazKa/pymatrix-max) от NijazKa
(версия 0.12.0, коммит `9aca964`) и развивается отдельно. Что добавлено, см. ниже
и в [CHANGELOG.md](CHANGELOG.md).

> Проект не связан с MAX, VK, Matrix.org Foundation или Element. Он использует
> неофициальный клиентский протокол MAX, поэтому изменения на стороне сервиса могут
> потребовать обновления PyMax или моста.

## Возможности

| Функция | Matrix → MAX | MAX → Matrix |
|---|:---:|:---:|
| Текстовые сообщения | ✅ | ✅ |
| Фото | ✅ | ✅ |
| Видео | ✅ | ✅, включая MPEG-DASH → MP4 |
| Аудио и голосовые сообщения | ✅ | ✅ |
| Файлы | ✅ | ✅ |
| Ответы/цитирование | ✅ | ✅ |
| Реакции | ✅ | ⚠️ экспериментально |
| Личные чаты по номеру | ✅ | — |
| Группы и каналы | ✅ | ✅ |
| Вступление по ссылке | ✅ | — |
| Выход и локальная блокировка чата | ✅ | — |
| Телефон контакта в теме DM | — | ✅, если MAX его предоставляет |

Сверх исходного pymatrix-max:

- вход по QR-коду MAX в терминале на сервере: коды и пароль не проходят через Matrix;
- архив сообщений, контактов и чатов в базе моста для поиска;
- локальный API через Unix-сокет: поиск, история, вложения, открытие комнат;
- отложенные сообщения средствами самого MAX: текст, фото, видео и файлы;
- командные утилиты `tools/matrix-max` и `tools/matrix-agent` для скриптов и агентов.

Описание API и утилит: [API.md](API.md).

Групповые сообщения по умолчанию отправляются в Matrix от bridge bot с именем автора
в тексте. Это предотвращает массовую регистрацию `@max_*`-пользователей для каждого
участника больших групп. Личные чаты используют отдельного ghost-пользователя.

## Быстрый старт с Docker

```bash
git clone https://github.com/rodmanvictor/matrix-max-bridge.git
cd matrix-max-bridge
cp .env.example .env
mkdir -p data
cp example-config.yaml data/config.yaml
```

Отредактируйте `data/config.yaml`: укажите Matrix-домен, адрес Synapse, адрес
Application Service и права пользователей. Затем:

```bash
docker compose build
docker compose run --rm mautrix-max \
   python -m mautrix_max \
   -g \
   -c /opt/mautrix-max/data/config.yaml \
   -r /opt/mautrix-max/data/registration.yaml
```

Подключите `data/registration.yaml` в `homeserver.yaml` Synapse:

```yaml
app_service_config_files:
  - /путь/к/matrix-max-bridge/data/registration.yaml
```

Перезапустите Synapse и запустите мост:

```bash
docker compose up -d
docker compose logs -f mautrix-max
```

Вход в MAX выполняется по QR-коду в интерактивном терминале на сервере, а не в чате
Matrix, чтобы коды и пароль не попали в историю комнат. Ваш Matrix ID должен иметь
уровень `user` или `admin` в `bridge.permissions`:

```bash
docker compose exec -e MAX_AUTH_MXID=@you:example.org \
  -e MAX_DATA_DIR=/opt/mautrix-max/data \
  mautrix-max python -m mautrix_max.qr_cli
```

Отсканируйте QR-код в приложении MAX. Если включена двухфакторная защита, терминал
спросит пароль. Мост подхватит новую сессию в течение 15 секунд. `MAX_DATA_DIR` —
каталог, в котором лежит `sessions/` из `bridge.max.session_dir`.

Подробная инструкция: [docs/installation-docker.md](docs/installation-docker.md).

## Команды

| Команда | Назначение |
|---|---|
| `!max login` | Напомнить, как войти по QR-коду |
| `!max cancel` | Прервать текущий процесс входа |
| `!max logout` | Завершить MAX-сессию |
| `!max ping` | Проверить мост и авторизацию |
| `!max add +79991234567` | Создать или открыть личный чат по номеру |
| `!max contact [MAX ID]` | Показать имя, MAX ID и доступный телефон |
| `!max join <ссылка>` | Вступить в группу или канал по ссылке |
| `!max syncgroups [chat_id или room_id]` | Проверить групповые portal и приглашения |
| `!max leave [chat_id]` | Выйти из MAX-группы или канала |
| `!max block [chat_id]` | Выйти и автоматически выходить при повторном добавлении |
| `!max unblock [chat_id]` | Снять локальную блокировку |
| `!max blocked` | Показать список заблокированных чатов |

Полное описание: [docs/commands.md](docs/commands.md).

## Требования

- Synapse с доступом к Application Service configuration;
- Python 3.10+ или Docker;
- Linux;
- `ffmpeg` для входящих DASH-видео;
- постоянный каталог `data/` для БД, конфигурации и MAX-сессий.

## Ограничения

- сквозное шифрование Matrix не поддерживается;
- нет синхронизации старой истории;
- редактирование и удаление сообщений не мостятся;
- MAX → Matrix реакции зависят от push-событий протокола и могут не приходить;
- inline-клавиатуры и часть служебных вложений MAX не отображаются;
- double puppeting не реализован;
- публикация в канал из Matrix зависит от прав MAX-аккаунта.

См. [ROADMAP.md](ROADMAP.md) и [docs/troubleshooting.md](docs/troubleshooting.md).

## Безопасность и приватность

Никогда не публикуйте:

- `data/config.yaml` и `data/registration.yaml`;
- SQLite-базу моста;
- каталог `data/sessions/`;
- токены Synapse, MAX-сессии и полные отладочные логи.

Перед публичным релизом запустите:

```bash
python tools/check_release.py
```

Политика безопасности: [SECURITY.md](SECURITY.md).

## Разработка

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --no-build-isolation -e .
python -m compileall -q mautrix_max vendor/pymax/src/pymax
python -m unittest discover -s tests -p 'test_*.py'
python tools/check_release.py
```

Правила участия: [CONTRIBUTING.md](CONTRIBUTING.md).

## Лицензия

Проект распространяется по лицензии [MIT](LICENSE). Исходный код pymatrix-max
написан NijazKa, его строка авторского права сохранена в `LICENSE`. Vendored PyMax также
распространяется по MIT; сведения об авторстве и локальных патчах приведены в
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
