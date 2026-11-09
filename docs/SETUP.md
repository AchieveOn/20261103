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

## 5. Neon（1〜4 ✅ 済み・test ブランチは任意）

1. ✅ プロジェクト作成: リージョン **AWS Singapore (ap-southeast-1)**、Postgres **17**、DB 名は初期値の `neondb` のまま（`roles.sql` が owner ロール `neondb_owner` を前提にしているため）
   - Postgres は 18 が初期値なので 17 に変える（バックアップ用イメージの `pg_dump` が 17。古い `pg_dump` は新しいサーバーを吸い出せない）
2. ✅ テーブル作成: SQL Editor（左メニュー Postgres database → SQL Editor、DB `neondb`）で [app/schema.sql](../app/schema.sql) を実行。手元からなら `DATABASE_URL='<neondb_owner の接続文字列>' .venv/bin/flask --app app init-db` でも同じ
3. ✅ 権限: 同じ SQL Editor で [docs/neon/roles.sql](neon/roles.sql) を実行
   - ロールは **Console ではなく SQL で作る**（Console 製は neon_superuser に入り権限が広すぎる）
4. ✅ パスワード（本人だけが知る。チャット・ファイル・SQL Editor に書かない）:
   1. Mac の「ターミナル」で次を実行し、「接続文字列を貼り付けてEnter:」を出しておく（Claude のチャット欄の `!` では入力できないので不可）:
      ```bash
      read -rs "NEON_URL?接続文字列を貼り付けてEnter: "; echo; /opt/homebrew/opt/postgresql@17/bin/psql "$NEON_URL"; unset NEON_URL
      ```
   2. Neon の **Connect** → Role `neondb_owner`・**Connection pooling を OFF**（管理作業は直接接続で）→ **Copy snippet** → ターミナルで Cmd+V → Enter（画面には出ない）。`neondb=>` が出れば接続成功
      - 先にクリップボードへ入れて `psql "$(pbpaste)"` にする方式は、コマンドをコピーした時点でクリップボードが上書きされて失敗する
   3. ロールごとに（`app_rw` → `backup_ro`、パスワードは別々）:
      - パスワードマネージャーで先に作って保存し、それをコピー（英数字とハイフンだけ。Apple の「強力なパスワード」の形でよい。URL に埋め込むときに変換が要らない）
      - `` \set pw `pbpaste` `` は**コピーせず手で打つ**（チャットや手順書からコピーするとクリップボードのパスワードが上書きされる）。この行で psql の変数 `pw` に移るので、以降はコピペしてよい
      - `\echo :{?pw}` が `TRUE` なら入った（中身は出ない）。`FALSE` のまま進むと `:'pw'` が置き換わらず `syntax error at or near ":"` になる
      - `ALTER ROLE app_rw WITH PASSWORD :'pw';`（`:'pw'` は**そのまま**。psql が中身に置き換えて送るので画面にも `~/.psql_history` にも残らない）
      - ※ `\password` は使えない。手元でハッシュ化して送るため、Neon が `Neon only supports being given plaintext passwords` で拒否する
      - ※ `:'pw'` をパスワードに書き換えると画面と履歴に残る。やってしまったらそのパスワードは捨てて作り直す
   4. 確認（app_rw を設定した直後、`pw` が残っているうちに）: `\setenv PGPASSWORD :pw` → `\c - app_rw`（聞かれずにつながる）→ `DELETE FROM moves;` が **permission denied** なら OK
      - backup_ro: `\c - backup_ro`（パスワードはマネージャーから貼る）→ `SELECT count(*) FROM items;` が通り、`UPDATE items SET name = name;` と `CREATE TABLE x (id int);` が **permission denied** なら OK
      - psql を抜けた後に入るなら: `psql "host=<Connect に出るホスト（-pooler なし）> dbname=neondb user=backup_ro sslmode=require"`（パスワードを聞かれる）
   5. 片付け: `\setenv PGPASSWORD` → `\unset pw` → `\q` → ターミナルで `rm ~/.psql_history`。クリップボードも別の文字をコピーして上書き
   - SQL Editor の `SET ROLE app_rw` は使えない（PG16 以降、ロールを作った側でも自動では成り代われない）。権限そのものは `has_table_privilege` で確認済み
5. **test ブランチ**: Branches → New branch → **Schema only**（本番データをコピーしない）。テスト・リリース前確認に使う
6. 保存時暗号化（AES-256）と TLS は Neon 側で常時有効。接続文字列には `sslmode=require` を付ける
7. （有料プラン）復元期間（Point-in-time restore）を 7 日以上に

## 6. Gmail 👤

0. 送信元のアカウントを決める。**送信専用の Google アカウント**がおすすめ（アプリパスワードはそのアカウントのメール全体に入れる鍵なので、Render から漏れたときの被害をバックアップ用だけに閉じ込められる）。受信先（`BACKUP_MAIL_TO`）はふだんのアドレスでよい
1. 送信元アカウントで 2 段階認証を ON: https://myaccount.google.com/signinoptions/twosv
2. アプリパスワードを発行: https://myaccount.google.com/apppasswords → アプリ名 `cafe-stock backup` → 作成 → 出た 16 文字を**スペースを抜いて**パスワードマネージャーに保存（画面を閉じると二度と出ない）。のちに Render の `GMAIL_APP_PASSWORD` にだけ入れる
   - 「お探しの設定はご利用いただけません」と出るときは 2 段階認証が OFF か、学校・会社の Workspace アカウントで管理者が止めている
3. バックアップ暗号化キーを作る（パスワードマネージャーに保存。**無くすとバックアップを復号できない**。Gmail には保存しない）:
   ```bash
   .venv/bin/python -c "from app.crypto import generate_key; print(generate_key(), end='')" | pbcopy
   ```
4. 受信側の Gmail でフィルタ: 検索窓の右の調整アイコン → 件名 `[喫茶在庫] DBバックアップ` → フィルタを作成 → 「スターを付ける」「ラベルを付ける（新しいラベル `喫茶在庫バックアップ`）」「迷惑メールにしない」
5. 手元から1通送って確かめる（Mac の「ターミナル」で。秘密は画面にもシェル履歴にも残らず、`( )` の中だけで消える）。`<ホスト>` は Neon の Connect に出るホスト（`-pooler` なし）:
   ```bash
   ( cd ~/Desktop/20261103 && read "GMAIL_USER?送信元のGmailアドレス: " && read "BACKUP_MAIL_TO?受信先のアドレス: " && read -rs "PGPASSWORD?backup_ro のパスワード: " && echo && read -rs "BACKUP_ENCRYPTION_KEY?バックアップ暗号化キー: " && echo && read -rs "GMAIL_APP_PASSWORD?アプリパスワード: " && echo && export GMAIL_USER BACKUP_MAIL_TO PGPASSWORD BACKUP_ENCRYPTION_KEY GMAIL_APP_PASSWORD="${GMAIL_APP_PASSWORD// /}" BACKUP_DATABASE_URL="postgresql://backup_ro@<ホスト>/neondb?sslmode=require" PG_DUMP=/opt/homebrew/opt/postgresql@17/bin/pg_dump && .venv/bin/python backup/backup_db.py )
   ```
   - 聞かれるたびにパスワードマネージャーからコピー → Cmd+V → Enter（コマンドは1行なので、先に貼っても入力待ちで止まる）
   - `送信しました: cafe_YYYYMMDD_HHMM.dump.enc` が出て、受信側にラベル付きで届けば OK。中身は暗号化済みなので、添付を開いても読めないのが正しい

## 7. Render 👤

web は **free（無料）**、バックアップの Cron は Gmail が済むまで外している（`render.yaml` 参照）。料金は 2026-11-09 に render.com/pricing と render.com/docs/free で確認。

| もの           | プラン               | 費用                        | 注意                                                                              |
| -------------- | -------------------- | --------------------------- | --------------------------------------------------------------------------------- |
| ワークスペース | Hobby                | $0                          |                                                                                   |
| web（アプリ）  | free                 | $0（月750時間まで）         | 15分無操作でスリープ・次に開くと約1分待つ。Shell が使えない。メール送信ポート不可 |
| Cron           | なし（Gmail の後で） | $0.00016/分（動いた分だけ） | 無料プランが無いので、戻すときは支払い方法の登録が要る（1日1分なら月 約 $0.005）  |

毎日お店で使うようになって待ち時間が気になったら、`render.yaml` の web を `plan: starter`（$7/月）にする PR を出す。

### 7-1. アカウントと GitHub 連携（いまできる）

1. https://dashboard.render.com/register でアカウント作成（パスワードはパスワードマネージャーで作る）
2. 右上のアカウント → **Account Settings** → Two-Factor Authentication を ON
3. 支払い方法は登録しない（無料のまま。使いすぎた月は止まるだけで請求されない）
4. **New** → **Blueprint** → GitHub を接続 → GitHub 側の画面で **Only select repositories** → `AchieveOn/20261103` だけを選んで Install（全部のリポジトリは許可しない）
   - ここでいったん止める（main がまだ空なので、Blueprint は 9 の初回リリースの後）
   - Render は **1ユーザーに GitHub アカウント1つ**（ログイン用と連携用で同じ枠）。別の GitHub（個人など）がつながっていると、GitHub 側の許可は通るのに「No repositories found」になり、追加もできない。そのときは Account Settings で Git Deployment Credentials とログイン方法の GitHub を外してから、AchieveOn でつなぎ直す（外した側のサービスは動き続けるが、push での自動デプロイが止まる）

### 7-2. Blueprint（9 の初回リリースで main にコードが入ってから）

1. **New** → **Blueprint** → `AchieveOn/20261103` → Blueprint の名前 `cafe-stock` → `render.yaml` から web 1本（Free）が出ることを確認
2. 入力を求められる環境変数（チャットや画面共有には出さない）:

   | 変数                 | 中身                                                                                                                       |
   | -------------------- | -------------------------------------------------------------------------------------------------------------------------- |
   | `DATABASE_URL`       | app_rw の接続文字列 `postgresql://app_rw:<パスワード>@<ホスト>/neondb?sslmode=require`。下のコマンドで組み立てる           |
   | `APP_ENCRYPTION_KEY` | 下のコマンドで作った鍵。**先にパスワードマネージャーに保存**してから Render に貼る（失くすと仕入先・原価が二度と読めない） |

   `DATABASE_URL` はパスワードに記号（`@` `:` `/` `?` `#` `%` など）が入ると壊れるので、下のコマンドで組み立ててクリップボードに入れる（記号は自動で `%40` などに置き換わる。画面にも履歴にも残らない）:

   ```bash
   ( read "H?ホスト（-pooler 付き）: " && read -rs "P?app_rw のパスワード: " && echo && H="$H" P="$P" python3 -c 'import os,urllib.parse as u;print("postgresql://app_rw:"+u.quote(os.environ["P"],safe="")+"@"+os.environ["H"]+"/neondb?sslmode=require",end="")' | pbcopy && echo "クリップボードにコピーしました" )
   ```

   - ホストは Neon の Connect（Connection pooling ON）に出る `ep-…-pooler.….neon.tech` の部分だけ
   - コピーできたら Render の `DATABASE_URL` に貼る（パスワードマネージャーにも「app_rw の接続文字列」として保存しておくと 8 で使える）

   `APP_ENCRYPTION_KEY` は:

   ```bash
   cd ~/Desktop/20261103 && .venv/bin/python -c "from app.crypto import generate_key; print(generate_key())" | pbcopy
   ```

   - `SECRET_KEY` は Render が自動で作る。`ALLOWED_HOSTS`・`COOKIE_SECURE` は `render.yaml` に書いてある

3. **Apply** → デプロイが終わったら、サービスの画面上部の URL を確認
   - URL が `cafe-stock.onrender.com` でなければ（名前が先に使われていると `cafe-stock-xxxx` になる）、`render.yaml` の `ALLOWED_HOSTS` をその値に直す PR を出す（画面だけで直すと Blueprint の同期で戻ることがある）
4. `https://<URL>/healthz` が `{"db":"ok","status":"ok"}` なら OK（スリープ中なら約1分待つ）

### 7-3. Cron を戻す（Gmail の後）

1. `render.yaml` の Cron の行頭の `# ` を外す PR → develop → release → main
2. Render に支払い方法を登録（Cron は無料プランが無い）
3. 入力を求められる環境変数: `BACKUP_DATABASE_URL`（backup_ro）・`BACKUP_ENCRYPTION_KEY`（7-2 とは**別の鍵**・同じコマンドで作る）・`GMAIL_USER`・`GMAIL_APP_PASSWORD`・`BACKUP_MAIL_TO`
4. Cron の画面で **Trigger Run** → Gmail に届くか確認

## 8. 最初のユーザー 👤

free の web は Render の Shell が使えないので、手元の Mac のターミナルから本番 DB に登録する（1行のコマンド。接続文字列は画面にも履歴にも残らない）:

```bash
( cd ~/Desktop/20261103 && read -rs "DATABASE_URL?app_rw の接続文字列: " && echo && export DATABASE_URL SECRET_KEY=cli APP_ENCRYPTION_KEY=cli && .venv/bin/flask --app app auth set-user <店主ID> --role owner )
```

- 接続文字列を聞かれたら、パスワードマネージャーからコピー → Cmd+V → Enter。次にそのユーザーのパスワードを2回
- `SECRET_KEY=cli` などは起動チェックを通すための仮の値（ユーザー登録では鍵を使わない）
- スタッフは最後を `set-user <スタッフID> --role staff`、退職時は `disable-user <ID>` にする

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
