# アプリ サポートサイト

App Store で公開している各アプリの **サポート / プライバシーポリシー / 利用規約** を配信する
静的サイト（GitHub Pages）です。App Store Connect の「サポートURL」「プライバシーポリシーURL」に
このサイトの各ページを設定します。

- 公開URL: `https://tablespoonful.github.io/iosApp/`（Pages 有効化後）
- 各アプリ: `…/era-converter.html` などの**名前ベースURL**
- 旧URL（`app1.html`〜`app4.html`）は**リダイレクトとして維持**（公開済みアプリのリンク互換）

## 構成（データ駆動）
ページは手書きせず、**データ＋共通テンプレから生成**します。

| ファイル | 役割 |
|---|---|
| `apps.json` | **データ（正）**。各アプリの名前・説明・機能・開示フラグ・共通設定 |
| `template.html` | ページ共通の雛形 |
| `style.css` | 共通スタイル（全ページで共有） |
| `build.py` | `apps.json`＋`template.html` から各ページ・リダイレクト・`index.html` を生成 |
| `<id>.html` | **生成物**（例 `era-converter.html`）。手で編集しない |
| `app1.html`〜 | **生成物**（旧URL→新URLのリダイレクト） |
| `404.html` | カスタム404（一覧へ誘導） |
| `app-ads.txt` | AdMob の認証（公開前提のファイル） |
| `docs/appstore-urls.md` | ASC のサポート/プライバシーURL 対応表と差し替え手順 |
| `docs/app-privacy-labels.md` | 各アプリの App Privacy ラベル申告内容（実コード準拠）|
| `scripts/set_appstore_urls.py` | ASC API で URL を一括更新（既定ドライラン）|

> `*.html` は生成物です。内容修正は `apps.json` / `template.html` / `style.css` を編集して
> `python3 build.py` を実行してください。

## 新規アプリ追加手順（ApplePlatformTemplate と接続）
新しいアプリをリリースする際、`ApplePlatformTemplate` 側の量産フロー
（`make new-app` → ローカライズ → スクショ → `release`）の一環としてサポートページも追加します。

1. **アプリ実態を確認**（← ここが最重要）
   - 広告（AdMob）を表示する？ → `flags.ads`
   - 位置情報を使う？ → `flags.location`
   - 写真にアクセスする？ → `flags.photos`
   - ローカル通知を出す？ → `flags.notifications`
   - 外部API（地図・検索等）に送信する？ → `flags.externalApi`
2. `apps.json` の `apps` に 1 エントリ追加:
   ```json
   {
     "id": "my-app",           // URL スラッグ（英小文字・ハイフン）
     "name": "アプリ名",
     "summary": "1〜2文の説明",
     "features": ["主な機能1", "主な機能2"],
     "flags": { "ads": true, "location": false, "photos": false, "notifications": false, "externalApi": false }
   }
   ```
   （`legacy` は旧`appN.html`があるアプリだけ。新規は不要）
3. `python3 build.py` を実行 → `my-app.html` と `index.html` が更新される。
4. `open index.html` でローカル確認 → 問題なければコミット & push。
5. **App Store Connect** に URL を設定（`docs/appstore-urls.md` 参照。手動 or `scripts/set_appstore_urls.py`）:
   - サポートURL / プライバシーポリシーURL = `https://tablespoonful.github.io/iosApp/my-app.html`
   - あわせて **App のプライバシー** ラベルを実態に合わせる（`docs/app-privacy-labels.md` 参照）。
6. `ApplePlatformTemplate` 側の `AppConfig.json` の `supportURL` / `feedbackFormURL` にも同URLを反映。

> テンプレの `skills/appstore-metadata` / `skills/release` の作業に、この「サポートページ追加」を
> 1ステップとして組み込むと量産フローが一気通貫になります。

## GitHub Pages の有効化（初回・404対策）
このサイトが 404 になる場合、**Pages 未有効 かつ 非公開リポジトリ**が原因です（Free では
public でないと Pages を配信できません）。
1. リポジトリを **Public** にする（本サイトは元々公開情報のみ）。
2. **Settings → Pages** → Source: `Deploy from a branch` → Branch: `main` / `/ (root)` → Save。
3. 数分後 `https://tablespoonful.github.io/iosApp/` で配信開始。

## ローカルプレビュー
```bash
python3 build.py
python3 -m http.server 8000   # http://localhost:8000/index.html
```
