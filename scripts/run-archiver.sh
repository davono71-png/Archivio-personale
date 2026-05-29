#!/usr/bin/env sh
set -eu

exec gmail-drive-archiver sync \
  --gmail-rules "${GMAIL_RULES:-config/gmail-rules.yml}" \
  --drive-config "${DRIVE_CONFIG:-config/drive-folders.yml}" \
  --credentials "${GOOGLE_CREDENTIALS:-config/credentials.json}" \
  --token "${GOOGLE_TOKEN:-database/token.json}" \
  --db "${ARCHIVE_DB:-database/personal-archive.sqlite3}" \
  "$@"
