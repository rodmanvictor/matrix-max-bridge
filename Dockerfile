FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=600

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
        libmagic1 \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Внутреннее имя и путь сохранены для совместимости с существующими
# registration.yaml, volume paths и production-конфигами.
WORKDIR /opt/mautrix-max

COPY pyproject.toml README.md LICENSE requirements.lock ./
COPY mautrix_max ./mautrix_max
COPY vendor/pymax/src/pymax ./vendor/pymax/src/pymax

# Vendored PyMax включается в wheel matrix-max-bridge. Это устраняет отдельную
# PEP 517 сборку PyMax и уменьшает число сетевых обращений при docker build.
RUN python -m pip install \
    --retries 10 \
    --no-cache-dir \
    -r requirements.lock \
    && python -m pip install --no-build-isolation --no-deps --no-cache-dir .

VOLUME ["/opt/mautrix-max/data"]
EXPOSE 29320

CMD ["python", "-m", "mautrix_max", "-c", "/opt/mautrix-max/data/config.yaml", "-r", "/opt/mautrix-max/data/registration.yaml"]
