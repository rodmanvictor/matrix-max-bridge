# Выпуск версии

## Подготовка

1. Обновите номер версии в `pyproject.toml`, `mautrix_max/__init__.py`,
   `mautrix_max/__main__.py` и `CITATION.cff`. Бейдж в README берёт версию из
   последнего релиза сам.
2. Опишите изменения в `CHANGELOG.md`.
3. Проверьте исходники:

```bash
python tools/check_release.py
python -m compileall -q mautrix_max vendor/pymax/src/pymax
python -m unittest discover -s tests -p 'test_*.py'
git status --short
```

## Тег и релиз

```bash
git tag -a v0.14.0 -m "matrix-max-bridge v0.14.0"
git push origin main v0.14.0
```

Тег `v*` запускает сборку Docker-образа `ghcr.io/rodmanvictor/matrix-max-bridge`
(`.github/workflows/docker-publish.yml`). Release создайте из раздела версии в
`CHANGELOG.md`:

```bash
gh release create v0.14.0 \
  --title "matrix-max-bridge v0.14.0" \
  --notes-file release-notes.md
```

## Настройки GitHub

Рекомендуемые Topics:

```text
matrix max bridge mautrix python synapse element docker
```

Описание репозитория:

```text
Неофициальный мост Matrix ↔ MAX на Python, mautrix и PyMax.
```

Включите:

- Issues;
- Discussions — по желанию;
- Private vulnerability reporting;
- branch protection для `main`: обязательный CI и запрет force-push.
