#!/usr/bin/env python3
"""Generate the app support site from apps.json + template.html.

Usage: python3 build.py
Outputs (never edit these by hand — edit apps.json / template.html and rebuild):
  - <id>.html         per-app page (privacy/terms/support), name-based URL
  - <legacy>.html     redirect stub (app1.html ... keeps published-app links alive)
  - index.html        the app list
Adding a new app = add an entry to apps.json, then run this script.
"""
import html
import json
import pathlib

ROOT = pathlib.Path(__file__).parent
data = json.loads((ROOT / "apps.json").read_text(encoding="utf-8"))
site = data["site"]
template = (ROOT / "template.html").read_text(encoding="utf-8")


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def p(text: str) -> str:
    return f"    <p>{text}</p>"


def features_block(features: list[str]) -> str:
    if not features:
        return ""
    items = "\n".join(f"      <li>{esc(f)}</li>" for f in features)
    return f"    <h2>主な機能</h2>\n    <ul>\n{items}\n    </ul>"



def audit_privacy(app_id: str, html: str, flags: dict) -> list:
    """公開前に、生成したプライバシーポリシーが実挙動と矛盾していないか自己検査する。

    2026-08-01: `firebase` フラグだけでバックエンド型の文面を出していたため、端末内完結の
    アプリに「サインイン」「クラウド保存」「予定の共有」を記載した虚偽のポリシーが公開された。
    プライバシーポリシーの虚偽は App Store の却下要因であり、生成物を人が読み返す運用では
    19ページ分を毎回確認できない。機械で止める。
    """
    problems = []
    if "として、を収集し" in html or "、を収集し" in html:
        problems.append("収集項目が空のまま文が生成されている（フラグの組み合わせが想定外）")
    backend_phrases = {
        "サインイン": "アカウント機能",
        "クラウドサービス上に保存": "クラウド保存",
        "グループで共有": "共有機能",
        "設定画面からアカウントを削除": "アカウント削除",
    }
    if not (flags.get("accounts") or flags.get("cloudSync")):
        for phrase, feature in backend_phrases.items():
            if phrase in html:
                problems.append(f"{feature}が無いのに「{phrase}」を記載している")
    if flags.get("ads") and "AdMob" not in html:
        problems.append("広告ありなのに AdMob の開示が無い")
    if not flags.get("ads") and "AdMob" in html:
        problems.append("広告なしなのに AdMob の開示がある")
    return [f"{app_id}: {m}" for m in problems]


def privacy_block(name: str, flags: dict) -> str:
    ads = flags.get("ads")
    location = flags.get("location")
    photos = flags.get("photos")
    notifications = flags.get("notifications")
    external = flags.get("externalApi")
    firebase = flags.get("firebase")
    accounts = flags.get("accounts")
    cloud_sync = flags.get("cloudSync")
    crash_reports = flags.get("crashReports")
    analytics = flags.get("analytics")
    local_history = flags.get("localHistory")
    non_personalized_ads = flags.get("nonPersonalizedAds")
    remote_config = flags.get("remoteConfig")
    # `firebase` だけでは「アカウント・クラウド保存・Push を伴うバックエンド」を意味しない。
    # Analytics / Crashlytics しか使わないアプリにこの分岐を当てると、サインイン・クラウド保存・
    # 予定の共有といった存在しない機能を記載した虚偽のプライバシーポリシーが公開される
    # （オキロク 2026-08-01: 収集項目が空のまま「として、を収集し」という壊れた文まで出た）。
    # バックエンド型の文面は、実際にアカウントかクラウド同期がある場合に限る。
    backend = bool(firebase and (accounts or cloud_sync))

    if non_personalized_ads:
        ad_privacy_text = ('本アプリは Google AdMob による広告を表示します。地域に応じてGoogleの同意フォームを表示し、広告は非パーソナライズ設定で配信します。AdMob は広告配信・計測、不正利用防止のために IP アドレス、デバイス識別子、広告データ、操作情報、診断情報などを収集・利用する場合があります。詳細は <a href="https://policies.google.com/technologies/ads">Google の広告に関するポリシー</a> をご確認ください。本アプリはIDFAを利用せず、App Tracking Transparencyによる許可要求や、他社のアプリ・Webサイトを横断するトラッキングを行いません。')
    else:
        ad_privacy_text = None

    out = [p(f"「{esc(name)}」は、以下の方針に基づきユーザーの情報を取り扱います。"), "    <h3>1. 収集・処理する情報</h3>"]
    if backend:
        collected = ""
        if accounts:
            collected += "アカウント識別子、メールアドレス、氏名、所属グループ情報"
        if cloud_sync:
            collected += ("、" if collected else "") + "予定、変更依頼、操作履歴"
        out.append(p(f"アプリの提供に必要な情報として、{collected}を収集し、Googleのクラウドサービス上に保存します。"))
        out.append(p("GoogleまたはAppleによるサインインを選択した場合、各認証サービスからアカウント識別情報を受け取ります。"))
    else:
        if analytics or crash_reports:
            out.append(p("本アプリの主要な機能は端末内で完結し、記録・進捗などのデータは端末内にのみ保存されます。当方が氏名やメールアドレス等、個人を特定できる情報をサーバーに収集・保存することはありません。"))
            # Remote Config も Firebase Installation ID（デバイス識別子）を送るので、
            # 使っているなら名指しする。「Analytics / Crashlytics だけ」と読める文面は、
            # 実際には3つ目の SDK が通信しているという意味で不正確になる。
            modules = [m for m, on in (("Analytics", analytics), ("Crashlytics", crash_reports),
                                       ("Remote Config", remote_config)) if on]
            if len(modules) > 1:
                service = f"Google Firebase（{' / '.join(modules)}）"
            else:
                service = f"Google Firebase {modules[0]}"
            parts = []
            if analytics:
                parts.append("匿名の利用状況（画面表示・操作イベント）")
            if crash_reports:
                parts.append("クラッシュ情報")
            parts.append("デバイス識別子")
            if len(parts) == 1:
                sent_data = parts[0]
            elif len(parts) == 2:
                sent_data = f"{parts[0]}および{parts[1]}"
            else:
                sent_data = "、".join(parts[:-1]) + "、および" + parts[-1]
            out.append(p(f'品質改善のため、{service}を利用し、{sent_data}を Google のサーバーに送信します。これらの情報は個人を特定するものではなく、ユーザーの個人情報に紐付けられず、トラッキング目的にも使用しません。詳細は <a href="https://policies.google.com/privacy">Google プライバシーポリシー</a>をご確認ください。'))
        else:
            out.append(p("本アプリの主要な機能は端末内で完結し、当方はユーザーの個人情報をサーバーに収集・保存しません。"))
    if photos:
        out.append(p("写真へのアクセスは、あなたが選択した写真の取り込み・編集のためだけに使用し、端末内で完結します。写真を外部サーバーへ送信することはありません。"))
    if notifications and backend:
        out.append(p("変更依頼などのPush通知を配信するため、端末の通知トークンをGoogleのクラウドサービスに保存します。通知はアプリ内またはiOSの設定から無効にできます。"))
    elif notifications:
        out.append(p("リマインダー等の通知は端末内でスケジュールされ、通知内容が外部に送信されることはありません。"))
    if location:
        out.append(p("現在地情報は、周辺の検索結果を表示する目的でのみ使用します。"))
    if external:
        history_text = "検索履歴は端末内にのみ保存され、当方のサーバーには送信されません。" if local_history else "当方が独自に検索履歴を保存・収集することはありません。"
        out.append(p(f'店舗検索・地図表示・住所変換のため、検索条件や現在地を Apple のマップサービス（MapKit / 逆ジオコーディング）に送信します。これらは Apple により提供され、<a href="https://www.apple.com/legal/privacy/">Apple のプライバシーポリシー</a>が適用されます。{history_text}また、当方は位置情報を保存・収集しません。'))

    if backend:
        # 見出し番号は ads の有無で1つずれるため動的に採番する
        n = 2
        out.append(f"    <h3>{n}. Googleのサービス利用</h3>")
        firebase_text = "認証、クラウド保存、Push通知のためGoogleが提供するサービスを利用します。"
        if crash_reports:
            firebase_text += "また、不具合調査のためGoogleのクラッシュ解析サービスへクラッシュ情報と診断情報を送信する場合があります。"
        firebase_text += '詳細は <a href="https://policies.google.com/privacy">Google プライバシーポリシー</a>をご確認ください。'
        out.append(p(firebase_text))
        n += 1
        if ads:
            out.append(f"    <h3>{n}. 広告について</h3>")
            out.append(p(ad_privacy_text or '本アプリは Google AdMob による広告を表示します。AdMob は広告配信・計測のために広告識別子や IP アドレスなどの情報を収集・利用し、Google と共有する場合があります。詳細は <a href="https://policies.google.com/technologies/ads">Google の広告に関するポリシー</a> をご確認ください。本アプリは App Tracking Transparency による許可要求を行わず、ユーザーを横断的にトラッキングしません（広告はトラッキングを伴わない形で配信されます）。'))
            n += 1
        out.append(f"    <h3>{n}. 利用目的・第三者提供</h3>")
        purpose_text = "収集情報は、本人確認、予定の保存・共有、変更依頼、通知配信、不具合調査のために利用します。"
        purpose_text += "法令に基づく場合を除き、Google等の業務委託先および上記の広告事業者以外の第三者へ提供しません。" if ads \
            else "法令に基づく場合を除き、Google等の業務委託先以外の第三者へ提供しません。"
        out.append(p(purpose_text))
        n += 1
        out.append(f"    <h3>{n}. 保存期間・削除</h3>")
        out.append(p("設定画面からアカウントを削除できます。アカウント削除時は、法令上または不正防止上保持が必要な情報を除き、関連する個人情報を削除します。グループで共有された情報は、他の利用者の業務記録として保持される場合があります。"))
        n += 1
        out.append(f"    <h3>{n}. 安全管理</h3>")
        out.append(p("アクセス制御、認証および通信の暗号化など、合理的な安全管理措置を講じます。"))
        n += 1
        out.append(f"    <h3>{n}. プライバシーポリシーの変更</h3>")
        out.append(p("本ポリシーは必要に応じて改定することがあります。重要な変更はアプリ内または本ページでお知らせします。"))
        return "\n".join(out)

    if ads:
        out.append("    <h3>2. 広告について</h3>")
        out.append(p(ad_privacy_text or '本アプリは Google AdMob による広告を表示します。AdMob は広告配信・計測のために広告識別子（IDFA 等）や IP アドレスなどの情報を収集・利用し、Google と共有する場合があります。詳細は <a href="https://policies.google.com/technologies/ads">Google の広告に関するポリシー</a> をご確認ください。本アプリは App Tracking Transparency による許可要求を行わず、ユーザーを横断的にトラッキングしません（広告はトラッキングを伴わない形で配信されます）。'))
        third = "    <h3>3. 第三者への提供</h3>"
        _google_role = "広告事業者・分析サービスの提供元（Google）" if analytics else "広告事業者（Google）"
        third_body = f"上記の{_google_role}および地図サービスの提供元（Apple）を除き、当方がユーザーの個人情報を第三者へ提供することはありません。" if external \
            else f"上記の{_google_role}を除き、当方がユーザーの個人情報を第三者へ提供することはありません。"
        change_h = "    <h3>4. プライバシーポリシーの変更</h3>"
    else:
        third = "    <h3>2. 第三者への提供</h3>"
        third_body = "外部サービスの提供元を除き、当方がユーザーの個人情報を第三者へ提供することはありません。" if external \
            else "当方は、ユーザーの個人情報を第三者へ提供しません。"
        change_h = "    <h3>3. プライバシーポリシーの変更</h3>"

    out += [third, p(third_body), change_h,
            p("本ポリシーは必要に応じて改定することがあります。重要な変更はアプリ内または本ページでお知らせします。")]
    return "\n".join(out)


TERMS = "\n".join([
    "    <h3>1. ライセンス</h3>",
    p("本アプリは個人利用のために無料で提供されます。商業目的での使用、再販、改変はできません。"),
    "    <h3>2. 知的財産権</h3>",
    p("本アプリおよびそのコンテンツに関する知的財産権は、ライセンサーに帰属します。無断での複製・配布・公開は禁止されています。"),
    "    <h3>3. 免責事項</h3>",
    p("本アプリは「現状有姿」で提供され、特定目的への適合性・正確性・完全性を保証しません。本アプリの利用により生じたいかなる損害についても、当方は責任を負いません。"),
    "    <h3>4. 利用制限</h3>",
    p("利用者が本規約に違反した場合、当方は本アプリの利用を制限または禁止する権利を有します。"),
    "    <h3>5. 規約の変更</h3>",
    p("本規約は必要に応じて変更されることがあります。変更後の規約は、アプリ内または本ページで通知された時点から効力を生じます。"),
])


def terms_block(flags: dict) -> str:
    if not flags.get("workCollaboration"):
        return TERMS
    return "\n".join([
        "    <h3>1. 利用条件</h3>",
        p("本アプリは個人の予定管理および組織内での予定共有のために提供されます。利用者は正確な情報を登録し、アカウントと招待コードを適切に管理するものとします。"),
        "    <h3>2. 禁止事項</h3>",
        p("不正アクセス、第三者へのなりすまし、他の利用者または業務を妨害する行為、法令に違反する利用を禁止します。"),
        "    <h3>3. 予定情報の位置付け</h3>",
        p("本アプリの予定および変更依頼は業務上の確認を補助するものです。安全管理、勤怠管理、労務管理その他の正式な手続を代替するものではありません。"),
        "    <h3>4. 知的財産権</h3>",
        p("本アプリに関する知的財産権はライセンサーに帰属します。法令で認められる場合を除き、無断での複製・配布・改変を禁止します。"),
        "    <h3>5. サービスの変更・停止</h3>",
        p("保守、障害または運用上の必要により、事前の通知なく本アプリの全部または一部を変更・停止する場合があります。"),
        "    <h3>6. 免責事項</h3>",
        p("本アプリは現状有姿で提供されます。通信障害、端末故障、誤入力などにより生じた損害について、法令で認められる範囲で責任を負いません。"),
        "    <h3>7. 規約の変更</h3>",
        p("本規約は必要に応じて変更することがあります。重要な変更はアプリ内または本ページでお知らせします。"),
    ])

REDIRECT = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0; url={id}.html">
  <link rel="canonical" href="{id}.html">
  <title>{name}</title>
</head>
<body><p>ページは移動しました。<a href="{id}.html">{name} のページへ</a></p></body>
</html>
"""

# --- render per-app pages + legacy redirects ---
privacy_problems = []
for app in data["apps"]:
    page = (template
            .replace("{{NAME}}", esc(app["name"]))
            .replace("{{UPDATED}}", esc(app.get("updated", site["updated"])))
            .replace("{{SUMMARY}}", esc(app["summary"]))
            .replace("{{FEATURES}}", features_block(app.get("features", [])))
            .replace("{{PRIVACY}}", privacy_block(app["name"], app.get("flags", {})))
            .replace("{{TERMS}}", terms_block(app.get("flags", {})))
            .replace("{{SUPPORT_URL}}", esc(site["supportFormUrl"]))
            .replace("{{YEAR}}", str(site["year"]))
            .replace("{{DEVELOPER}}", esc(site["developer"])))
    privacy_problems += audit_privacy(app["id"], page, app.get("flags", {}))
    (ROOT / f"{app['id']}.html").write_text(page, encoding="utf-8")
    if app.get("legacy"):
        (ROOT / f"{app['legacy']}.html").write_text(
            REDIRECT.format(id=app["id"], name=esc(app["name"])), encoding="utf-8")

if privacy_problems:
    print("✗ プライバシーポリシーが実挙動と矛盾しています（公開前に修正してください）:")
    for problem in privacy_problems:
        print(f"  - {problem}")
    raise SystemExit(1)

# --- index ---
items = "\n".join(
    f'      <li><a href="{a["id"]}.html">{esc(a["name"])}'
    f'<span class="desc">{esc(a["summary"][:40])}…</span></a></li>'
    for a in data["apps"])
index = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{esc(site['developer'])} のアプリ サポート / プライバシーポリシー一覧">
  <title>{esc(site['title'])}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="container">
    <h1>{esc(site['title'])}</h1>
    <ul class="app-list">
{items}
    </ul>
    <div class="footer"><p>&copy; {site['year']} {esc(site['developer'])}. All rights reserved.</p></div>
  </div>
</body>
</html>
"""
(ROOT / "index.html").write_text(index, encoding="utf-8")

print(f"Built {len(data['apps'])} app page(s) + redirects + index.html")
