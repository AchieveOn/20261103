# ガードレール対応表

[CLAUDE.md](../CLAUDE.md) の恒常ルールを、どこで機械的に止めているかの一覧。ルールを足したら、この表に「どこで守るか」も足す。

## 守りの層

| 層            | 中身                                                                         | いつ効くか                                              |
| ------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------- |
| ① Claude Code | `.claude/hooks/guard.py`（操作の前に拒否）・`format.py`（書いた .py を整形） | **このフォルダで起動した** Claude Code のセッションだけ |
| ② Git hooks   | `.githooks/`（pre-commit・pre-push・pre-merge-commit・post-checkout）        | 手元の commit / push / merge（人も AI も）              |
| ③ テスト      | `tests/`（pytest）と壊し検査 `tests/mutation_check.py`                       | 手元・pre-push・CI                                      |
| ④ CI          | `.github/workflows/`（CI・GitFlow・Test guard・CodeQL）                      | GitHub の push / PR（手元をすり抜けても止まる）         |
| ⑤ DB 権限     | `docs/neon/roles.sql`（app_rw は記録を消せない・backup_ro は読むだけ）       | 本番の Neon（アプリが乗っ取られても効く）               |
| ⑥ 人の承認    | PR のラベル `test-change-approved`                                           | テストを弱める変更・ガードの変更があるとき              |

## ルール → 守り

| ルール（CLAUDE.md）                                 | ① Claude Code                                                                       | ② Git hooks                                 | ③ テスト                                                     | ④ CI / ⑤ DB / ⑥ 人                                 |
| --------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------- |
| GitFlow・main/develop に直接入れない                | main/develop への push・force push を拒否                                           | pre-commit・pre-push・pre-merge-commit      | ―                                                            | GitFlow（合流方向）。ブランチ保護は未設定（本人）  |
| `--no-verify` 禁止（hooks を飛ばさない）            | `--no-verify`・`-n`・`core.hooksPath`・`SKIP_TESTS=` を拒否                         | ―                                           | `test_guard.py`                                              | CI が同じ検査をもう一度                            |
| 秘密情報は `.env` と Render だけ・AI は触らない     | Read / Edit / Write / Grep と Bash の `.env` を拒否                                 | 秘密ファイルの混入・Betterleaks             | `test_guard.py`                                              | Betterleaks で全履歴                               |
| 在庫は `moves` の合計・記録は消さない               | ―                                                                                   | ―                                           | `test_rules.py`（在庫数の列なし・DELETE なし）・在庫のテスト | ⑤ app_rw に DELETE なし                            |
| 仕入先・単価・メモは暗号化・owner だけ              | ―                                                                                   | ―                                           | 暗号化して保存・staff に見せない・`test_rules.py`（`*_enc`） | ―                                                  |
| DDL と DB 権限を揃える・app_rw に DELETE を広げない | ―                                                                                   | ―                                           | `test_rules.py`（全表に権限・DELETE は login_failures だけ） | ⑤ Neon で実接続確認済み                            |
| 整形（ruff format・Prettier）                       | `format.py` が .py を整形                                                           | ―                                           | ―                                                            | CI の Format                                       |
| 変更したら ruff と pytest・守りには壊し方を足す     | ―                                                                                   | pre-push で pytest                          | 壊し検査 19/19                                               | CI（Lint・Test・壊し検査）・Test guard（テスト減） |
| TDD（テスト → RED → 実装 → GREEN）                  | tests/ に変更が無いと app/・backup/ の .py を編集させない                           | ―                                           | `test_guard.py`                                              | Test guard（テスト減・skip 増）                    |
| 本番ユーザー・本番の鍵は本人が作る                  | Neon（`neon.tech`）への接続・`generate_key` を拒否                                  | ―                                           | `test_guard.py`                                              | ⑤ owner の接続文字列は Neon の画面にだけ           |
| 作者は noreply・実名・店名・メアドを入れない        | ―                                                                                   | `check_personal.py`（作者・メアド・禁止語） | `test_check_personal.py`                                     | PR の作者メール検査                                |
| 画面: 外部読み込み・インライン JS なし              | ―                                                                                   | ―                                           | `test_rules.py`（テンプレート）・安全ヘッダのテスト          | ―                                                  |
| 画面: 表を骨格に・説明文や箱の入れ子を足さない      | ―                                                                                   | ―                                           | **機械判定できない**                                         | ⑥ PR で人が見る                                    |
| 文書（ARCHITECTURE.md の表と図）が実装と一致        | ―                                                                                   | ―                                           | `test_rules.py`（ルート・ファイル・図のモジュール）          | ―                                                  |
| ガード自身を AI が弱めない                          | `.claude/`・`.githooks/`・`.github/workflows/`・`.github/scripts/` の書き換えを拒否 | ―                                           | `test_guard.py`・壊し検査                                    | ⑥ ガードを変えた PR はラベルが要る                 |

## ガードを変えるとき（本人）

AI はガードを書き換えられない。変えるときは本人が許可してから Claude Code を起動し直す:

- ターミナルの `claude` なら: `CLAUDE_GUARD_MAINTENANCE=1 claude`
- デスクトップアプリなら: `.claude/settings.local.json`（コミットされない）に `{"env": {"CLAUDE_GUARD_MAINTENANCE": "1"}}` を書いて新しいセッション
- 終わったら必ず外す。PR では Test guard が止めるので、中身を見てから `test-change-approved` を付ける

禁止語リスト `.githooks/denylist.local`（本名・店名・学校名など。1行1語・`#` はコメント）も本人が作る。コミットされず、該当しても語そのものは表示しない。

## 限界（ここは守れていない）

- ① は **このフォルダで起動したセッション** でしか効かない（別フォルダで起動した Claude からは素通り）。② ④ が後ろで止める
- Bash の判定は文字列のパターン。わざと難読化したコマンドはすり抜けうる。④ の CI と ⑥ の PR 確認が最後の砦
- TDD の門は「テストを変えたか」しか見ない。RED を実際に見たかは確かめられない
- pre-push は `TEST_DATABASE_URL` が無いと DB のテストを skip する（CI では必ず走る）
- GitHub の画面でマージしたコミットの作者は、GitHub アカウントの設定で決まる（「メールアドレスを非公開」が OFF だと個人のメールが入る）
