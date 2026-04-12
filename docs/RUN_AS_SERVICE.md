# Process supervision (API + Worker)

Чтобы процессы не умирали от случайного SIGTERM и не требовали ручного перезапуска,
используйте systemd unit-файлы из `infra/systemd/`.

## Установка

```bash
sudo cp infra/systemd/spatial-pinwheel-api.service /etc/systemd/system/
sudo cp infra/systemd/spatial-pinwheel-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now spatial-pinwheel-api.service
sudo systemctl enable --now spatial-pinwheel-worker.service
```

## Проверка

```bash
systemctl status spatial-pinwheel-api.service
systemctl status spatial-pinwheel-worker.service
journalctl -u spatial-pinwheel-worker.service -f
```

Если API запущен на другом порту, измените `ExecStart` в unit-файле перед копированием.
