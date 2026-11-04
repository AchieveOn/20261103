# 20261103（喫茶在庫）

喫茶店の在庫管理。Flask on Render + Neon。構成は docs/ARCHITECTURE.md、手順は docs/SETUP.md、作業記録は LOG.md（進捗はここに書かずに LOG.md へ）。

## 恒常ルール

- ブランチは GitFlow（docs/GITFLOW.md）。main / develop で直接コミット・push しない。`--no-verify` 禁止
- 秘密情報は `.env` と Render の環境変数だけ。AI は `.env` を読まない・書かない（.claude/hooks/guard.py が止める）
- 在庫は `moves` の合計。在庫数の列を作らない。記録は消さず `voided_at` で取消
- 仕入先・単価・店主メモは `crypto.encrypt` してから保存し、owner にだけ表示する
- DB の DDL は `app/schema.sql` に足し、`docs/neon/roles.sql` の権限も合わせて直す（app_rw に DELETE を広げない）
- 整形は Python = `ruff format`、css / json / yaml / md = Prettier（VS Code は保存時に自動）。`app/templates/` は Jinja が崩れるので Prettier の対象外（`.prettierignore`）
- 変更したら `ruff check .` と `pytest` を通す。守りを足したら `tests/mutation_check.py` に壊し方を1行足して RED を確認
- 本番ユーザー・本番の鍵は本人が作る（Claude は作らない）
- コミット作者はリポジトリローカル設定の AchieveOn（noreply）。公開前に実名・店名・メアドを grep する
- 画面は表を骨格にする。使い方を説明する文・箱の入れ子・見出しの縦棒を足さない
