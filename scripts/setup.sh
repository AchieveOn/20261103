#!/usr/bin/env bash
# 開発環境のセットアップ（クローン直後に1回）: bash scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# 1) Git hooks を有効化（.githooks/ を使う）
git config core.hooksPath .githooks
chmod +x .githooks/*
echo "✓ Git hooks: .githooks を有効化"

# 2) Betterleaks（秘密情報スキャナ）
if ! command -v betterleaks >/dev/null 2>&1; then
  echo "betterleaks が無いので入れます"; brew install betterleaks
fi
echo "✓ betterleaks $(betterleaks version)"

# 3) Python 仮想環境
PY="$(command -v python3.13 || command -v python3)"
[[ -d .venv ]] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements-dev.txt
echo "✓ .venv（$(.venv/bin/python --version)）"

# 4) .env（秘密情報）は雛形だけコピー。値は本人が入れる
if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  echo "✓ .env を作成（chmod 600）。値を埋めてください"
fi

echo "完了。テスト: TEST_DATABASE_URL=... .venv/bin/pytest"
