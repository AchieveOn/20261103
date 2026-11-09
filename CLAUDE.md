# 20261103（喫茶在庫）

喫茶店の在庫管理。Flask on Render + Neon。構成は docs/ARCHITECTURE.md、手順は docs/SETUP.md、ルールと守りの対応は docs/GUARDRAILS.md、作業記録は LOG.md（進捗はここに書かずに LOG.md へ）。Claude Code はこのフォルダで起動する（.claude/ のフックはそのときだけ効く）。

## 恒常ルール

- ブランチは GitFlow（docs/GITFLOW.md）。main / develop で直接コミット・push しない。`--no-verify` 禁止
- 秘密情報は `.env` と Render の環境変数だけ。AI は `.env` を読まない・書かない（.claude/hooks/guard.py が止める）
- 在庫は `moves` の合計。在庫数の列を作らない。記録は消さず `voided_at` で取消
- 仕入先・単価・店主メモは `crypto.encrypt` してから保存し、owner にだけ表示する
- DB の DDL は `app/schema.sql` に足し、`docs/neon/roles.sql` の権限も合わせて直す（app_rw に DELETE を広げない）
- 整形は Python = `ruff format`、css / json / yaml / md = Prettier（VS Code は保存時に自動）。`app/templates/` は Jinja が崩れるので Prettier の対象外（`.prettierignore`）
- 機能追加・バグ修正は TDD: 失敗するテストを書く → RED を確認 → 実装 → GREEN → 整理。tests/ に変更が無いと guard.py が app/・backup/ の .py の編集を止める
- 変更したら `ruff check .` と `pytest` を通す。守りを足したら `tests/mutation_check.py` に壊し方を1行足して RED を確認
- ルールを足したら docs/GUARDRAILS.md に「どこで守るか」を足す。機械で判定できるものは tests/test_rules.py に入れる
- ガード（`.claude/` `.githooks/` `.github/workflows/` `.github/scripts/`）は AI が書き換えない。必要なら変更案を本人に出す（本人がメンテナンスモードで起動したときだけ編集）
- 画面のルートやモジュールを足したら docs/ARCHITECTURE.md の表と「アプリの中身」の図も直す（tests/test_rules.py がズレを止める）
- 本番ユーザー・本番の鍵は本人が作る（Claude は作らない）
- コミット作者はリポジトリローカル設定の AchieveOn（noreply）。公開前に実名・店名・メアドを grep する
- 画面は表を骨格にする。使い方を説明する文・箱の入れ子・見出しの縦棒を足さない
