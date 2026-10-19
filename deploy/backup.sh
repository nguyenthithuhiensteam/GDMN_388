#!/usr/bin/env bash
# Sao lưu hằng ngày: pg_dump (định dạng custom) + bản sao lưu ứng dụng (JSON + tệp), rồi kiểm tra toàn vẹn.
# Biến môi trường lấy từ .env (EnvironmentFile của systemd).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-/srv/mamnon/venv/bin/python}
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
if [ "${DB_ENGINE:-sqlite}" = "postgresql" ]; then
  PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -Fc "$DB_NAME" > "$BACKUP_DIR/pg-$STAMP.dump"
  chmod 600 "$BACKUP_DIR/pg-$STAMP.dump"
  ls -1t "$BACKUP_DIR"/pg-*.dump | tail -n +$(( ${BACKUP_KEEP:-14} + 1 )) | xargs -r rm -f
fi
"$PY" manage.py backup_data
LATEST=$(ls -1t "$BACKUP_DIR"/backup-*.zip | head -n 1)
"$PY" manage.py verify_backup "$LATEST"
# Khuyến nghị: đồng bộ thư mục sao lưu sang nơi lưu trữ khác (mã hóa), ví dụ rclone/rsync tới máy chủ dự phòng.
