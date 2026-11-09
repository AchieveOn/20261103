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

## 2026-11-04 構成の説明とドキュメント追記

- `docs/ARCHITECTURE.md` に「いまの状態（2026-11-04 時点）」の表（✅/📄/👤）と「アプリの中身（1回のアクセスで何が起きるか）」の図・ファイル別の役割表を追加
- 未 push のまま（本人の指示で保留）
- 全体図を「状態別の3レイヤー（開発環境・確認済み / GitHub・未 push / 本番・未接続）」の mermaid に作り直し、`docs/architecture.mmd` と ARCHITECTURE.md の「全体図」に同じものを置いた
  - mermaid 11 では `%%{init}%%` の直後にコメント行があると図の種類を判定できない → 設定は frontmatter（`---\nconfig:`）で書く
- VS Code 拡張 `bierner.markdown-mermaid`（Markdown プレビューで図を描く）と `mermaidchart.vscode-mermaid-chart`（.mmd を開いて図を拡大表示）を入れ、`.vscode/extensions.json` の推奨にも追加
- 訂正: `mermaidchart.vscode-mermaid-chart` の Preview は Mermaid アカウントへのサインインが必要（図を外部クラウドへ送る機能も付く）→ アンインストールして推奨からも外した。`docs/architecture.mmd` は `docs/architecture-diagram.md`（mermaid フェンス入り）に置き換え、Markdown プレビュー（`Cmd + Shift + V`）で見る方式に統一
- 全体図を縦3段（① 手元 / ② GitHub / ③ 本番）×段の中は左→右に組み直し、文字を 20px に。段どうしは段そのものを矢印でつなぐ（中のノードを外とつなぐと direction LR が無視されるため）
  - 段の見出しは約 200px で折り返すので短くする。暗いテーマで線が消えないよう `linkStyle default` で色を固定

## 2026-11-04 VS Code 拡張と保存時整形

- 拡張を追加（推奨にも登録）: Ruff / Prettier / GitHub Actions / YAML / Even Better TOML / Git Graph / Error Lens / indent-rainbow（+ 既存の markdown-mermaid）
- 保存時整形: Python = Ruff（import の並べ替えも）、css・json・yaml・md = Prettier。HTML は保存時整形オフ、`app/templates/` は `.prettierignore` で除外（Jinja の `{% %}` を崩すため）。Red Hat YAML のテレメトリはワークスペース設定でオフ
- 保存のたびに大きな整形差分が混ざらないよう、既存ファイルを一度だけ整形（Python 11 / その他 11 ファイル。見た目だけで中身は不変）
  - 確認（実行して確認済み）: ruff check・ruff format --check・prettier --check すべて OK、pytest 44 passed、mutation_check 10/10 RED、betterleaks dir で漏れなし
  - 未確認: VS Code 上で保存時に実際に整形が走るか

## 2026-11-04 初回 push

- push 前検品: ファイルと push 対象コミットに実名・メアド・ローカルパスなし、Betterleaks 全履歴で漏れなし。作者は全コミット AchieveOn（noreply）。※ GitHub の Web で作られた `Initial commit` だけ個人メアドの作者で、push 前から公開済み
- `feature/initial-setup` を push（pre-push のテスト 44 passed をローカル Postgres で実行）
- GitHub Actions の CI 初回: lint・pytest（postgres:17 service）・Betterleaks 全履歴が success（実行して確認済み）。壊し検査・CodeQL・Test guard・GitFlow は PR 時だけ動くので未実行
- 残り: `develop` の初回 push（Claude のガードで止まるので本人）→ PR 作成

## 2026-11-04 PR #1（feature/initial-setup → develop）

- PR 作成。PR 時だけ動く検査の初回: CI（lint・pytest 44 passed・0 skipped・壊し検査）・CodeQL・GitFlow・Betterleaks は success（実行して確認済み）
- Test guard は failure: 「skip/xfail が 0 → 4」。develop にテストが1本もない状態からの初回 PR なので、条件つき skip（DB・pg_dump が無い環境だけ飛ばす4か所）が「増えた」と数えられた。CI では 0 skipped
  - 設計どおりの停止。ラベル `test-change-approved` は人が付ける承認なので Claude は付けない（ラベル自体もリポジトリに未作成）
- 本人が `test-change-approved` ラベルを作成・付与 → Test guard 再実行で success。PR #1 の検査は全部 success
- 見つけた穴: Test guard が壊し検査を 10 件ではなく 7 件と数えていた。原因は一括整形で3件が複数行に折り返され、行の形（`^\s*("app/`）で数えていたため。消されても気づけない状態だった
  - 修正: `MUTATIONS` リストの要素数を ast で数える（ファイルが無い・読めないときは 0 ＝止める側）
  - 確認（実行して確認済み・使い捨てクローン）: develop 比較で 0 → 10。折り返された1件を消すと新方式は 10 → 9 で停止、旧方式は 7 → 7 で素通り。承認ラベルありなら警告だけで通過

## 2026-11-04 PR #1 マージ

- 本人の指示で PR #1 を develop にマージ（merge commit `35a976e`、GitFlow どおり feature の履歴を残す）。feature/initial-setup ブランチは消さずに残してある
- この追記と Prettier の空行1つは未コミット。次の feature ブランチで一緒にコミットする

## 2026-11-04 Neon 本番 DB

- 本人のアカウントで Neon のプロジェクト `cafe-stock` を作成（Claude が Chrome で操作）: AWS Singapore・Postgres 17（初期値 18 から変更。バックアップの `pg_dump` が 17 のため）・DB `neondb`・ブランチ `production`・無料プラン
  - Neon の案内（`neon init` で owner の接続文字列を `.env` に書き、Neon MCP を入れる手順）は使わず、画面から作成。owner の鍵が手元に置かれ、AI に広い操作権限が渡るため
- SQL Editor で `app/schema.sql`（CREATE 5件）→ `docs/neon/roles.sql`（11件）を実行。すべて成功
- 確認（実行して確認済み）: `app_rw`・`backup_ro` とも superuser なし・neon_superuser に入っていない・public にテーブルを作れない。`app_rw` は DELETE が `login_failures` だけ、TRUNCATE なし。`backup_ro` は SELECT だけ
- 見つけたこと: `roles.sql` の確認手順 `SET ROLE app_rw` は Neon では permission denied（PG16 以降、ロールを作った側でも自動では成り代われない）。確認方法を psql の `\c - app_rw` と `has_table_privilege` に書き換え
- パスワード（本人がパスワードマネージャーで作成・psql で設定）: `\password` は Neon が拒否（`Neon only supports being given plaintext passwords`）。`` \set pw `pbpaste` `` → `ALTER ROLE ... PASSWORD :'pw'` に切り替え
  - つまずき: ① `psql "$(pbpaste)"` はコマンドをコピーした時点でクリップボードが上書きされて空接続 → `read -rs` で後から貼る方式に ② `:'pw'` をパスワードに書き換えて実行（構文エラーで未登録。そのパスワードは廃棄）③ クリップボードを空にした直後に `\c` して認証失敗。SETUP.md 5-4 に反映
- 確認（本人のターミナルで実行して確認済み）: マネージャーの app_rw パスワードで接続でき、`DELETE FROM moves;` が `permission denied for table moves`
- backup_ro: 最初の登録は `\set` の時点でクリップボードがパスワードでなかったらしく認証失敗。2回目は `\set` が実行されておらず `syntax error at or near ":"`（変数が無いと `:'pw'` は置き換わらない）。`\echo :{?pw}` で入ったことを確かめてから登録し直して成功（本人の報告。読めて、UPDATE・CREATE TABLE は拒否）。`~/.psql_history` は本人が削除
- 残り: test ブランチ（任意）

## 2026-11-04 Gmail の手順

- SETUP.md の 6 を具体化: 送信専用アカウント推奨（アプリパスワードはアカウントのメール全体の鍵のため）・2 段階認証とアプリパスワードの URL・バックアップ暗号化キーの作成・受信フィルタ・手元からの試し送信
- 試し送信は1行のコマンドで、秘密を `read -rs` で受けて `( )` の中だけで使う（画面・シェル履歴に残さない）。backup_ro の接続はパスワード無しの URL ＋ `PGPASSWORD`
  - 確認（機械チェックのみ）: zsh の構文チェック、ダミー値でアプリパスワードのスペース除去が効くこと。実送信は未実行（本人作業）

## 2026-11-09 ガードレール（feature/guardrails）

- CLAUDE.md のルールを棚卸しし、どこで守るかを docs/GUARDRAILS.md にまとめた。穴: guard.py にテストが無い・`.env` を grep / python から読める・AI がガード自身を書き換えられる・TDD の強制なし・作者メールと実名の確認が手作業・CI に ruff format が無い
- テストを先に書いて RED を確認してから実装（guard 59件・個人情報チェック 7件・PR 検査 2件・ルール 10件）。壊し検査に9通り追加して 19/19 RED。全体 122 passed
- 入れたもの: guard.py の強化（Bash・Grep の `.env`、hooks のすり抜け、force push、Neon 接続と鍵生成、ガード自身の保護、TDD の門）、format.py（PostToolUse で ruff format）、pre-commit の個人情報チェック、CI の Format と作者メール検査、Test guard でガード変更にラベル必須
- 見つけたこと:
  - このセッションは ai-lab で起動していたため、20261103 の `.claude/settings.json` のフックは効いていなかった（ガードのフォルダへの書き込みが通った）。フックは起動したフォルダの設定だけが効く。フック本体は JSON を標準入力に渡して呼び、拒否（exit 2）を確認
  - 新しい個人情報チェックが、テストの架空の接続文字列（`user@ホスト`）をメールアドレスとして止めた。書き方を変えて通した
  - PR #1 のマージコミット `35a976e` の作者が個人のメールアドレス（GitHub の画面でマージしたため）。公開済み。GitHub の「メールアドレスを非公開」設定は本人
- 未確認: 20261103 で起動したセッションでのフックの実動作、`settings.local.json` の env でメンテナンスモードに入れるか、CI の Format・作者検査・ガード変更検知の GitHub 上での初回実行

## 2026-11-09 発注リスト（feature/order-list・TDD）

- `/orders`（店主だけ）: 発注が必要な品目（在庫切れ・要発注・まもなく）を仕入先ごとにまとめる。仕入先は暗号化列を復号して使う。未登録は最後。発注の目安 = 発注点 + 届くまでの使用見込み（1日の使用 × 届くまでの日数、切り上げ）− 在庫
- TDD: テスト8件を先に書いて RED（404・ImportError）をコミット → 実装で GREEN → 文書のズレ検知（test_rules）が RED になり、ARCHITECTURE.md の表と図に `/orders` を足して GREEN。「まもなく」のテストを1件追加。全体 131 passed、壊し検査に「発注リストを staff に見せる」を足して 20/20 RED
- 画面確認（架空データ・ローカルの使い捨てサーバー）: 最初は仕入先ごとに別の表で列がずれた → 1つの表に仕入先の見出し行を入れる形に。スマホ幅（375px）では品名が1文字ずつ折れ、発注の目安が見切れた → 発注点・届くまでを隠して収めた（表の幅 = 画面内）
- ブランチは feature/guardrails の上に重ねている（ガード入りの状態で開発するため）。PR は guardrails → order-list の順

## 2026-11-09 Render の準備（feature/render-free）

- 料金を公式で確認（render.com/pricing・docs/free）: ワークスペース Hobby $0、web free $0（月750時間・15分でスリープ・復帰約1分・Shell 不可・SMTP ポート不可）/ starter $7/月、Cron は無料プラン無し $0.00016/分
- 決めたこと: web は free（本人）。Cron は Gmail が済むまで `render.yaml` でコメントアウト（その間のバックアップは Neon の履歴からの復元だけ）
- free は Shell が使えないので、最初のユーザー登録（SETUP.md 8）を手元から本番 DB に入れる1行コマンドに変更。`set-user` は鍵を使わないので `SECRET_KEY`・`APP_ENCRYPTION_KEY` は仮の値で起動チェックを通す（ローカルの架空 DB で登録できることを確認）
- 未確認: Render の画面での Blueprint 作成（main にコードが入ってから）、Blueprint の同期で画面の環境変数が戻るか
- 7-1 完了（本人）: Render アカウント・GitHub 連携（AchieveOn・20261103 だけ）。最初は個人の GitHub がログイン方法と連携に入っていて「No repositories found」。Render は1ユーザーに GitHub 1つなので、個人側（使っていない既存サービス3つの連携）を外して AchieveOn でつなぎ直した

## 2026-11-09 初回リリースと Render デプロイ

- PR #2〜#5 をマージし、release/1.0.0 で main へ（本人）。Render の Blueprint `cafe-stock` を作成（web 1本・Free）
- Render が付けた URL は `cafe-stock-tghx.onrender.com`（`cafe-stock` は他で使用済み）。`ALLOWED_HOSTS` が合わず、ヘルスチェック以外は Bad Host になるため hotfix/1.0.1 で修正
- PR #5 の GitFlow / author が、PR #1 のマージコミット 35a976e（作者が個人のメール）で FAILURE。既に develop で公開済みのもので新しい漏れではない。main に入ったので次のリリースからは出ない
