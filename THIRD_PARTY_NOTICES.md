# Сторонние компоненты

## pymatrix-max

matrix-max-bridge продолжает pymatrix-max. Код моста до коммита `9aca964`
(версия 0.12.0) написан NijazKa, дальнейшие изменения описаны в `CHANGELOG.md`.

- исходный проект: https://github.com/NijazKa/pymatrix-max
- авторское право: Copyright (c) 2026 NijazKa
- лицензия: MIT, строка авторского права сохранена в `LICENSE`

## PyMax

Каталог `vendor/pymax` содержит PyMax (`maxapi-python`) версии 2.5.0 (исходный коммит c4cb917d354a1179be625925530d72c8aaa969ff).

- исходный проект: https://github.com/MaxApiTeam/PyMax
- авторское право: Copyright (c) 2025 ink-developer
- лицензия: MIT, полный текст в `vendor/pymax/LICENSE`

Vendored-копия включается в wheel `matrix-max-bridge` и содержит совместимые с мостом изменения:

- обработку дополнительных типов входящих reaction frame;
- разбор нескольких форматов MAX video CDN payload;
- поддержку URL MPEG-DASH, который мост затем remux-ит через FFmpeg.

При обновлении PyMax эти изменения необходимо переносить и повторно тестировать.

## mautrix-python

Мост использует `mautrix-python` как внешний пакет. Проект распространяется по
MPL-2.0; условия лицензии и авторство см. в репозитории:
https://github.com/mautrix/python.

## FFmpeg

Docker-образ устанавливает FFmpeg из системного репозитория Debian. Лицензирование
конкретной сборки зависит от включённых компонентов дистрибутива Debian.
