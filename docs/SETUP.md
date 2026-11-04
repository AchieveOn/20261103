# 構築手順

凡例: ✅ 済み（Claude が実行・確認済み） / 👤 本人の作業（アカウント・パスワード・課金・公開が絡むもの） / ⏸ 本人の OK 待ち

## 0. リポジトリ ✅

- `~/Desktop/20261103` にクローン、VS Code で開く
- コミット作者はリポジトリローカルで `AchieveOn <…noreply…>` に設定（本名を公開履歴に出さない）

## 1. 手元の開発環境 ✅

```bash
bash scripts/setup.sh
```

やること: Git hooks 有効化（`core.hooksPath=.githooks`）/ Betterleaks 導入 / `.venv`（Python 3.13）/ `.env` を雛形から作成（chmod 600）

VS Code は推奨拡張（Python・Ruff・GitHub Actions・Claude Code）を入れると、テストが左の「テスト」パネルから流せます。

## 2. ローカルで動かす（任意）

テストとローカル起動には PostgreSQL が要ります。どちらか:

- **A. Neon の dev ブランチ**（おすすめ・手元に何も入れない）: Neon で `dev` ブランチを作り、その接続文字列を `.env` の `DATABASE_URL` / `TEST_DATABASE_URL` に入れる
- **B. 手元の Postgres**: `brew install postgresql@17 && brew services start postgresql@17` → `createdb cafe_dev` → `DATABASE_URL=postgresql://localhost/cafe_dev`

```bash
.venv/bin/flask --app app init-db                       # テーブル作成
.venv/bin/python -c "from app.crypto import generate_key; print(generate_key())"   # 出た鍵を .env の APP_ENCRYPTION_KEY へ
.venv/bin/flask --app app auth set-user tenshu --role owner   # パスワードを聞かれる
COOKIE_SECURE=0 .venv/bin/flask --app app run --port 5070
TEST_DATABASE_URL=postgresql://localhost/cafe_test .venv/bin/pytest    # テスト（使い捨てスキーマで動く）
```

## 3. GitHub へ push（feature は ✅ 済み・develop と PR が 👤）

`develop` への push は Claude のガード（`.claude/hooks/guard.py`）が止めるので、初回作成だけ本人がターミナルで打つ。

```bash
git push -u origin develop                 # 初回作成だけ pre-push が許可する
git push -u origin feature/initial-setup
gh pr create --base develop --fill         # CI・CodeQL・Test guard・GitFlow が走る
```

## 4. GitHub の設定 👤（または Claude に依頼）

1. **ブランチ保護**（Settings → Branches → Add rule）: `main` と `develop` に
   - Require a pull request before merging
   - Require status checks: `test` `secrets-scan` `analyze` `guard` `branch-rule`
   - Do not allow bypassing the above settings
2. **Secret scanning / Push protection**（Settings → Code security）を ON（公開リポジトリは無料）
3. ラベル `test-change-approved` を作成（テストを意図的に減らす PR のときだけ付ける）
4. （任意）Settings → Secrets → Actions に `TEST_DATABASE_URL`（Neon test ブランチの**直結** URL）。無ければ CI は使い捨て Postgres で動く

## 5. Neon 👤

1. プロジェクト作成: リージョン **AWS Singapore (ap-southeast-1)**、Postgres **17**、DB 名 `appdb`
2. テーブル作成（owner ロールの接続文字列で、手元から1回）:
   ```bash
   DATABASE_URL='<neondb_owner の接続文字列>' .venv/bin/flask --app app init-db
   ```
3. 権限: SQL Editor か psql で [docs/neon/roles.sql](neon/roles.sql) を実行 → psql で `\password app_rw` と `\password backup_ro`（パスワードは本人だけが知る）
   - ロールは **Console ではなく SQL で作る**（Console 製は neon_superuser に入り権限が広すぎる）
4. **test ブランチ**: Branches → New branch → **Schema only**（本番データをコピーしない）。テスト・リリース前確認に使う
5. 保存時暗号化（AES-256）と TLS は Neon 側で常時有効。接続文字列には `sslmode=require` を付ける
6. （有料プラン）復元期間（Point-in-time restore）を 7 日以上に

## 6. Gmail 👤

1. バックアップ送信用の Google アカウントで 2 段階認証を ON
2. 「アプリ パスワード」を発行（16 桁）→ Render の `GMAIL_APP_PASSWORD` にだけ入れる
3. 受信側にフィルタ「件名: [喫茶在庫] DBバックアップ」→ ラベル付け・スター（迷惑メール回避）

## 7. Render 👤

1. Dashboard → New → **Blueprint** → このリポジトリ → `render.yaml` を読み込む
2. `sync: false` の環境変数を入力（ARCHITECTURE.md「鍵と接続文字列の置き場所」）
   - `DATABASE_URL` = app_rw、`BACKUP_DATABASE_URL` = backup_ro
   - 鍵 2 本は `.venv/bin/python -c "from app.crypto import generate_key; print(generate_key())"` で別々に生成し、**パスワードマネージャにも控える**
3. 作られた URL に合わせて `ALLOWED_HOSTS` を直す（例 `cafe-stock-xxxx.onrender.com`）
4. 費用: web `starter` と cron `starter` は有料。web を `free` にすると無料だが15分無操作でスリープする
5. Render のアカウントは 2 段階認証を ON

## 8. 最初のユーザー 👤

Render の Shell（web サービス → Shell）か、手元から本番の app_rw URL を一時的に渡して:

```bash
flask --app app auth set-user <店主ID> --role owner
flask --app app auth set-user <スタッフID> --role staff
flask --app app auth disable-user <ID>      # 退職時など
```

## 9. 初回リリース

```bash
git switch develop && git pull && git switch -c release/1.0.0 && git push -u origin release/1.0.0
gh pr create --base main --title "Release 1.0.0" --fill
```

main にマージ → CI 通過 → Render が自動デプロイ（`autoDeployTrigger: checksPass`）。

## 10. 本番の確認チェックリスト

- [ ] `https://<URL>/healthz` が `{"db":"ok","status":"ok"}`
- [ ] 未ログインで `/` がログイン画面に飛ぶ
- [ ] staff で原価・仕入先が見えない／owner で見える
- [ ] Render Cron を手動実行（Trigger Run）→ Gmail に `cafe_*.dump.enc` が届く
- [ ] 届いたファイルを復号して test ブランチに復元できる（下記）

```bash
BACKUP_ENCRYPTION_KEY='…' python backup/backup_db.py decrypt cafe_YYYYMMDD_HHMM.dump.enc > restore.dump
pg_restore --no-owner -d '<test ブランチの URL>' restore.dump && rm restore.dump
```
