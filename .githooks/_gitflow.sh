#!/usr/bin/env bash
# GitFlow 共通ルール（各フックから source して使う）
#   main      : 本番。release/* と hotfix/* からの PR マージだけで更新する
#   develop   : 開発の統合先。feature/* bugfix/* release/* hotfix/* から PR マージ
#   feature/* : 新機能（develop から切る → develop へ）
#   bugfix/*  : develop 上のバグ修正（develop から切る → develop へ）
#   release/* : リリース準備（develop から切る → main と develop へ）  例: release/1.2.0
#   hotfix/*  : 本番の緊急修正（main から切る → main と develop へ）    例: hotfix/1.2.1
#   support/* : 旧バージョン保守（必要なときだけ）

PROTECTED_BRANCHES_REGEX='^(main|master|develop)$'
WORK_BRANCH_REGEX='^(feature|bugfix|support)/[a-z0-9][a-z0-9._-]*$'
VERSION_BRANCH_REGEX='^(release|hotfix)/[0-9]+\.[0-9]+\.[0-9]+$'

red()    { printf '\033[31m%s\033[0m\n' "$*" >&2; }
yellow() { printf '\033[33m%s\033[0m\n' "$*" >&2; }
green()  { printf '\033[32m%s\033[0m\n' "$*" >&2; }

is_protected_branch() { [[ "$1" =~ $PROTECTED_BRANCHES_REGEX ]]; }

is_valid_work_branch() {
  [[ "$1" =~ $WORK_BRANCH_REGEX ]] || [[ "$1" =~ $VERSION_BRANCH_REGEX ]]
}

branch_name_help() {
  cat >&2 <<'EOF'
  使えるブランチ名（GitFlow）:
    feature/<小文字-ハイフン>   例: feature/login-form
    bugfix/<小文字-ハイフン>    例: bugfix/healthz-timeout
    release/<X.Y.Z>             例: release/1.0.0
    hotfix/<X.Y.Z>              例: hotfix/1.0.1
    support/<名前>
  改名: git branch -m <新しい名前>
EOF
}
