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
