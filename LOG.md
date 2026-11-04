# 作業ログ

## 2026-11-04 初期構築（feature/initial-setup）

依頼: 手書きの構成図（VS Code ハーネス Hooks / Git + Betterleaks / GitHub CI・コード解析・テスト変更検知 / Render CD・バックアップ / Neon テストDB・権限・暗号 / Gmail バックアップ）どおりに組む。題材は秘匿性の高い喫茶店の在庫管理。ブランチは GitFlow とその hooks。

### やったこと
- クローン、コミット作者をリポジトリローカルで AchieveOn（noreply）に設定
- GitFlow: `main` から `develop`、`develop` から `feature/initial-setup` を作成
- Git hooks（`.githooks/`）: pre-commit / pre-push / pre-merge-commit / post-checkout
- Claude Code hooks（`.claude/`）: `.env` 読み書き・`--no-verify`・main/develop への push を拒否
- アプリ（`app/`）: Flask + psycopg3。店主/スタッフの役割、仕入先・単価・メモの Fernet 暗号化、取消は削除せず印、CSRF・Host チェック・ログインロック・CSP ほか
  - 土台は ai-lab/coffee-stock のログイン設計（session_gen・ロック・safe_next）を Postgres 用に移植
- テスト 44 件 + `tests/mutation_check.py`（守りを10通り壊して全部 RED になることを確認）
- GitHub Actions: CI（ruff・pytest on Postgres 17・壊し検査）、Betterleaks 全履歴、CodeQL、Test guard、GitFlow 合流チェック、Dependabot
- Render Blueprint（web + cron）、バックアップ（pg_dump 17 → Fernet → Gmail）、Neon 権限 SQL
- ドキュメント: README / docs/ARCHITECTURE.md / docs/SETUP.md / docs/GITFLOW.md / CLAUDE.md

### 確認したこと（実行して確認済み）
- `ruff check .` / `pytest` 44 passed（ローカル Postgres 17）
- mutation_check 10/10 RED
- Git hooks を使い捨てリポジトリで違反させて確認: main/develop 直コミット・規則外ブランチ名・`.env` 強制 add・GitHub トークン風文字列・develop への2回目以降の直 push・テスト失敗での push・main への feature 逆流マージ（ローカル/リモート追跡とも）→ すべて停止。正規の操作は通過
- Claude ガード: 11 パターン（`.env` 読み取り拒否、`.env.example` 許可、`feature/main-menu` への push は許可 など）
- Test guard: テスト関数の減少・skip 追加で exit 1、ラベル付きで通過、テスト追加は OK
- `docs/neon/roles.sql` をローカル Postgres で適用し、app_rw は INSERT/UPDATE 可・moves の DELETE / DROP / CREATE 不可、backup_ro は SELECT と pg_dump のみ可
- アプリを app_rw 権限で起動し Playwright で操作: 店主は仕入先・単価が見える／スタッフは見えず `/items/new` は 403、在庫超過の使用は拒否、375px 幅で横スクロールなし、コンソールエラーなし

### つまずき
- `pre-merge-commit` の時点では MERGE_HEAD が無い → `GIT_REFLOG_ACTION` から合流元を読むよう修正
- ローカル確認のポート 5060 は Chrome の unsafe port（SIP）で開けない → 5070 に変更
- `python -m app.crypto` は RuntimeWarning が出る → ドキュメントの鍵生成コマンドを `python -c "from app.crypto import generate_key; ..."` に統一

### 未確認（本番環境では未確認）
- GitHub Actions の実行（未 push）
- Render のデプロイ、`autoDeployTrigger: checksPass`、`.python-version` の解釈
- `backup/Dockerfile` のビルド（手元に Docker なし）と Gmail 送信
- Neon 上での roles.sql（ローカル Postgres では確認済み）
