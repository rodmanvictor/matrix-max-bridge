# Установка без Docker: venv + systemd

## Системные зависимости Debian/Ubuntu

```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-dev \
  build-essential libpq-dev libmagic1 ffmpeg
```

## Установка

```bash
sudo useradd --system --create-home --home-dir /opt/matrix-max-bridge matrix-max-bridge
sudo -u matrix-max-bridge git clone https://github.com/rodmanvictor/matrix-max-bridge.git /opt/matrix-max-bridge/app
cd /opt/matrix-max-bridge/app

sudo -u matrix-max-bridge python3 -m venv .venv
sudo -u matrix-max-bridge .venv/bin/python -m pip install --upgrade pip setuptools wheel
sudo -u matrix-max-bridge .venv/bin/python -m pip install --no-build-isolation .

sudo -u matrix-max-bridge mkdir -p data
sudo -u matrix-max-bridge cp example-config.yaml data/config.yaml
```

Для systemd обычно используются:

```yaml
homeserver:
  address: http://127.0.0.1:8008

appservice:
  address: http://127.0.0.1:29320
```

Сгенерируйте регистрацию:

```bash
sudo -u matrix-max-bridge .venv/bin/python -m mautrix_max \
  -g -c data/config.yaml -r data/registration.yaml
```

Подключите `data/registration.yaml` к Synapse и перезапустите его.

## Unit-файл

`/etc/systemd/system/matrix-max-bridge.service`:

```ini
[Unit]
Description=matrix-max-bridge Matrix ↔ MAX bridge
After=network-online.target matrix-synapse.service
Wants=network-online.target

[Service]
Type=simple
User=matrix-max-bridge
Group=matrix-max-bridge
WorkingDirectory=/opt/matrix-max-bridge/app
ExecStart=/opt/matrix-max-bridge/app/.venv/bin/python -m mautrix_max -c data/config.yaml -r data/registration.yaml
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/matrix-max-bridge/app/data

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now matrix-max-bridge
sudo systemctl status matrix-max-bridge
sudo journalctl -u matrix-max-bridge -f
```

## Вход в MAX

Вход выполняется по QR-коду в интерактивном терминале. Matrix ID должен иметь
уровень `user` или `admin` в `bridge.permissions`:

```bash
cd /opt/matrix-max-bridge/app
sudo -u matrix-max-bridge env MAX_AUTH_MXID=@you:example.org \
  MAX_DATA_DIR=/opt/matrix-max-bridge/app/data \
  .venv/bin/python -m mautrix_max.qr_cli
```

Мост подхватит сессию в течение 15 секунд. Подробнее — в
[installation-docker.md](installation-docker.md#8-первая-авторизация).
