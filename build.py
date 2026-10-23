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


HEALTHKIT_HEADING = "Apple ヘルスケア（HealthKit）"



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
    # INC248: App Privacy に粗い位置・パフォーマンス・診断を申告する SDK 利用アプリは、
    # 公開ポリシーにも同趣旨が必要（GPS 権限の有無とは別の、IP 由来の推定である点に注意）。
    uses_sdk_diagnostics = bool(
        flags.get("ads") or flags.get("analytics") or flags.get("crashReports")
    )
    if uses_sdk_diagnostics and "大まかな位置" not in html:
        problems.append("Firebase/AdMob 利用なのに IP 由来の粗い位置情報の開示が無い")
    if uses_sdk_diagnostics and "パフォーマンスデータ" not in html:
        problems.append("Firebase/AdMob 利用なのにパフォーマンス／診断データの開示が無い")
    healthkit_disclosed = f"<h4>{HEALTHKIT_HEADING}</h4>" in html
    if flags.get("healthKit") and not healthkit_disclosed:
        problems.append("HealthKit 利用ありなのに Apple ヘルスケアの開示が無い")
    if not flags.get("healthKit") and healthkit_disclosed:
        problems.append("HealthKit 利用なしなのに Apple ヘルスケアの開示がある")
    return [f"{app_id}: {m}" for m in problems]


def privacy_block(name: str, flags: dict) -> str:
    ads = flags.get("ads")
    location = flags.get("location")
    photos = flags.get("photos")
    # カメラは写真ライブラリとは別の権限。photos だけを立てると、カメラを要求するアプリの
    # ポリシーがカメラに一言も触れないページになる。Dimemo はカメラ許可フロー（5.1.1(iv)）で
    # 却下された直後の再提出で、審査員がポリシーを開いてもカメラの記載が無い状態だった。
    camera = flags.get("camera")
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
    healthkit = flags.get("healthKit")
    # `firebase` だけでは「アカウント・クラウド保存・Push を伴うバックエンド」を意味しない。
    # Analytics / Crashlytics しか使わないアプリにこの分岐を当てると、サインイン・クラウド保存・
    # 予定の共有といった存在しない機能を記載した虚偽のプライバシーポリシーが公開される
    # （オキロク 2026-08-01: 収集項目が空のまま「として、を収集し」という壊れた文まで出た）。
    # バックエンド型の文面は、実際にアカウントかクラウド同期がある場合に限る。
    backend = bool(firebase and (accounts or cloud_sync))

    if non_personalized_ads:
        ad_privacy_text = ('本アプリは Google AdMob による広告を表示します。地域に応じてGoogleの同意フォームを表示し、広告は非パーソナライズ設定で配信します。AdMob は広告配信・計測・頻度制御、不正利用防止のためにデバイス識別子、広告データ、操作情報、診断情報などを収集・利用する場合があり、通信時の IP アドレスから大まかな位置（国・地域程度）を推定することがあります（正確な位置情報（GPS）は取得しません）。詳細は <a href="https://policies.google.com/technologies/ads">Google の広告に関するポリシー</a> をご確認ください。本アプリはIDFAを利用せず、App Tracking Transparencyによる許可要求や、他社のアプリ・Webサイトを横断するトラッキングを行いません。')
    else:
        # 標準（トラッキングなし）広告。デバイス識別子は配信・頻度制御に使うことがある一方、
        # ATT は出さず他社横断のトラッキングには使わない（App Privacy の「紐付けなし・トラッキングなし」と整合）。
        ad_privacy_text = ('本アプリは Google AdMob による広告を表示します。AdMob は広告配信・計測・頻度制御のために広告識別子（IDFA 等）やデバイス識別子などの情報を収集・利用し、Google と共有する場合があります。また、通信時の IP アドレスから大まかな位置（国・地域程度）を推定し、広告配信に利用することがあります（正確な位置情報（GPS）は取得しません）。詳細は <a href="https://policies.google.com/technologies/ads">Google の広告に関するポリシー</a> をご確認ください。本アプリは App Tracking Transparency による許可要求を行わず、ユーザーを横断的にトラッキングしません（広告はトラッキングを伴わない形で配信されます）。')

    out = [p(f"「{esc(name)}」は、以下の方針に基づきユーザーの情報を取り扱います。"), "    <h3>1. 収集・処理する情報</h3>"]
    if backend:
        collected = ""
        if accounts:
            collected += "アカウント識別子、メールアドレス、氏名、所属グループ情報"
        if cloud_sync:
            collected += ("、" if collected else "") + "予定、変更依頼、操作履歴"
        out.append(p(f"アプリの提供に必要な情報として、{collected}を収集し、Googleのクラウドサービス上に保存します。"))
        out.append(p("GoogleまたはAppleによるサインインを選択した場合、各認証サービスからアカウント識別情報を受け取ります。"))
        if ads or analytics or crash_reports:
            sdk_bits = []
            if firebase:
                sdk_bits.append("Google Firebase")
            if ads:
                sdk_bits.append("Google AdMob")
            if len(sdk_bits) == 2:
                who = f"{sdk_bits[0]} および {sdk_bits[1]}"
            elif sdk_bits:
                who = sdk_bits[0]
            else:
                who = "外部サービス"
            out.append(p(f'{who}は、通信時の IP アドレスから大まかな位置（国・地域程度）を推定することがあります。正確な位置情報（GPS）は取得しません。'))
            out.append(p('アプリの動作状況に関するパフォーマンスデータおよび診断データ（起動時間、クラッシュ時の状態など）を収集することがあります。これらは広告配信・分析・不具合の解析に使用し、ユーザー個人の特定や、他社のデータとの紐付け（トラッキング）には使用しません。'))
    else:
        if analytics or crash_reports:
            local_storage = "端末内に保存されます" if healthkit else "端末内にのみ保存されます"
            out.append(p(f"本アプリの主要な機能は端末内で完結し、記録・進捗などのデータは{local_storage}。当方が氏名やメールアドレス等、個人を特定できる情報をサーバーに収集・保存することはありません。"))
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
            # App Privacy（粗い位置・パフォーマンス・その他の診断）と公開ポリシーの整合（INC248）。
            # GPS 権限（flags.location）とは別で、SDK が IP から国・地域程度を推定するケースを開示する。
            sdk_names = [service]
            if ads:
                sdk_names.append("Google AdMob")
            who = f"{sdk_names[0]} および {sdk_names[1]}" if len(sdk_names) == 2 else sdk_names[0]
            out.append(p(f'{who}は、通信時の IP アドレスから大まかな位置（国・地域程度）を推定することがあります。正確な位置情報（GPS）は取得しません。'))
            out.append(p('アプリの動作状況に関するパフォーマンスデータおよび診断データ（起動時間、クラッシュ時の状態など）を収集することがあります。これらは広告配信・分析・不具合の解析に使用し、ユーザー個人の特定や、他社のデータとの紐付け（トラッキング）には使用しません。'))
        else:
            out.append(p("本アプリの主要な機能は端末内で完結し、当方はユーザーの個人情報をサーバーに収集・保存しません。"))
            if ads:
                # Analytics/Crashlytics 無しで広告だけのアプリでも、AdMob 由来の粗い位置・診断を開示する。
                out.append(p('Google AdMob は、通信時の IP アドレスから大まかな位置（国・地域程度）を推定することがあります。正確な位置情報（GPS）は取得しません。'))
                out.append(p('アプリの動作状況に関するパフォーマンスデータおよび診断データ（起動時間、クラッシュ時の状態など）を収集することがあります。これらは広告配信・分析・不具合の解析に使用し、ユーザー個人の特定や、他社のデータとの紐付け（トラッキング）には使用しません。'))
    if healthkit:
        health_data_types = flags.get("healthDataTypes") or "本アプリが対応する健康データ"
        out.append(f"    <h4>{HEALTHKIT_HEADING}</h4>")
        out.append(p(f"本アプリがApple ヘルスケア（HealthKit）で読み書きする健康データは、{esc(health_data_types)}です。ヘルスケア連携は既定でオフです。読み込みと書き込みは個別に設定でき、ユーザーが本アプリの設定画面で明示的に有効にした場合にのみ行います。"))
        out.append(p("読み込みを有効にすると、Apple ヘルスケアに保存された対象データを本アプリの記録へ取り込みます。書き込みを有効にすると、本アプリで記録した対象データをApple ヘルスケアへ保存します。"))
        out.append(p("Apple ヘルスケア由来の健康データを広告、マーケティング、データマイニングに使用せず、第三者へ提供せず、解析イベントにも含めません。健康データは端末内とApple ヘルスケアにのみ保存され、開発者のサーバーへ送信しません。ヘルスケアへのアクセスは、iOSの「ヘルスケア」Appからいつでも取り消せます。"))
    if camera:
        # 撮影の用途と写真の扱いはアプリで違う（保存しない・ライブラリ経路が無い等）。
        # flags.cameraPurpose で全文を差し替えられるようにする。
        camera_text = flags.get("cameraPurpose") or "カメラへのアクセスは、あなたが撮影した写真をアプリに取り込んで編集するためだけに使用します。撮影した写真は端末内に保存され、あなたが書き出して共有するときにのみ端末の外に出ます。カメラの許可を求めるのは、あなたがカメラでの撮影を選んだときだけで、許可しなくても写真ライブラリから選ぶ経路をそのまま利用できます。"
        out.append(p(camera_text))
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
        # 何を Apple のマップサービスへ送るかはアプリで違う。既定文は「店舗検索＋現在地」を
        # 前提にしており、現在地を使わないアプリ（写真の EXIF 座標を地名に変えるだけ等）に
        # そのまま当てると、していないことを書いた虚偽のポリシーになる。アプリ側で
        # flags.mapsSentData / mapsPurpose を指定して上書きできるようにする。
        maps_purpose = flags.get("mapsPurpose") or "店舗検索・地図表示・住所変換"
        maps_sent = flags.get("mapsSentData") or "検索条件や現在地"
        out.append(p(f'{maps_purpose}のため、{maps_sent}を Apple のマップサービス（MapKit / 逆ジオコーディング）に送信します。これらは Apple により提供され、<a href="https://www.apple.com/legal/privacy/">Apple のプライバシーポリシー</a>が適用されます。{history_text}また、当方は位置情報を保存・収集しません。'))

    # 課金に RevenueCat を使うアプリは、購入情報の処理委託先として明記する（flags.revenueCat）。
    revenue_cat = flags.get("revenueCat")
    if revenue_cat:
        out.append(p('有料プランの購入状態を確認するため、App Store の購入情報（取引の記録）を RevenueCat, Inc. のサービスで処理します。氏名やメールアドレスは送信せず、アプリごとに割り当てられる匿名の ID で管理します。詳細は <a href="https://www.revenuecat.com/privacy/">RevenueCat のプライバシーポリシー</a>をご確認ください。'))

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
            out.append(p(ad_privacy_text or '本アプリは Google AdMob による広告を表示します。AdMob は広告配信・計測のために広告識別子などの情報を収集・利用し、Google と共有する場合があります。詳細は <a href="https://policies.google.com/technologies/ads">Google の広告に関するポリシー</a> をご確認ください。本アプリは App Tracking Transparency による許可要求を行わず、ユーザーを横断的にトラッキングしません（広告はトラッキングを伴わない形で配信されます）。'))
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
        out.append(p(ad_privacy_text or '本アプリは Google AdMob による広告を表示します。AdMob は広告配信・計測のために広告識別子（IDFA 等）などの情報を収集・利用し、Google と共有する場合があります。詳細は <a href="https://policies.google.com/technologies/ads">Google の広告に関するポリシー</a> をご確認ください。本アプリは App Tracking Transparency による許可要求を行わず、ユーザーを横断的にトラッキングしません（広告はトラッキングを伴わない形で配信されます）。'))
        third = "    <h3>3. 第三者への提供</h3>"
        _google_role = "広告事業者・分析サービスの提供元（Google）" if analytics else "広告事業者（Google）"
        third_body = f"上記の{_google_role}および地図サービスの提供元（Apple）を除き、当方がユーザーの個人情報を第三者へ提供することはありません。" if external \
            else f"上記の{_google_role}を除き、当方がユーザーの個人情報を第三者へ提供することはありません。"
        if revenue_cat:
            third_body = third_body.replace("を除き、", "および購入情報の処理委託先（RevenueCat）を除き、", 1)
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


IAP_TERMS = "\n".join([
    "    <h3>1. ライセンス</h3>",
    p("本アプリの基本機能は無料で利用でき、一部の機能および広告の非表示は有料プランで提供されます。商業目的での使用、再販、改変はできません。"),
    "    <h3>2. アプリ内課金</h3>",
    p("有料プランには、自動更新のサブスクリプションおよび買い切り（非消耗型）があります。代金は App Store を通じて Apple ID に請求されます。具体的な価格およびプランの内容は、アプリ内の購入画面および App Store に表示される内容が適用されます。"),
    p("サブスクリプションは、現在の期間が終了する24時間前までに解約しない限り、自動的に更新されます。更新料は、現在の期間が終了する前の24時間以内に請求されます。"),
    p("サブスクリプションの解約は、iOS の「設定」アプリから Apple アカウントを開き、「サブスクリプション」を選択して行うものとし、本アプリから解約することはできません。解約後も、支払い済みの期間が終了するまでは引き続き有料プランを利用できます。"),
    p("買い切りで購入した機能は、購入時と同じ Apple ID を使用し、本アプリの「購入を復元」から復元できます。返金は Apple の定めに従うものとし、当方から直接返金することはできません。"),
    p("価格およびプランの内容は変更されることがあります。変更する場合は、アプリ内または本ページで事前に告知します。"),
    "    <h3>3. 知的財産権</h3>",
    p("本アプリおよびそのコンテンツに関する知的財産権は、ライセンサーに帰属します。無断での複製・配布・公開は禁止されています。"),
    "    <h3>4. 免責事項</h3>",
    p("本アプリは「現状有姿」で提供され、特定目的への適合性・正確性・完全性を保証しません。本アプリの利用により生じたいかなる損害についても、当方は責任を負いません。"),
    "    <h3>5. 利用制限</h3>",
    p("利用者が本規約に違反した場合、当方は本アプリの利用を制限または禁止する権利を有します。"),
    "    <h3>6. 規約の変更</h3>",
    p("本規約は必要に応じて変更されることがあります。変更後の規約は、アプリ内または本ページで通知された時点から効力を生じます。"),
])


def terms_block(flags: dict) -> str:
    if not flags.get("workCollaboration"):
        if flags.get("iap"):
            return IAP_TERMS
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


def lang_switch_block(has_english: bool) -> str:
    if not has_english:
        return ""
    return (
        '    <p class="lang-switch">'
        '<a href="#privacy">日本語</a> / <a href="#privacy-en">English</a>'
        "</p>\n"
    )


ENGLISH_TERMS = [
    "    <h3>1. License</h3>",
    p("This app is provided free of charge for personal use. Commercial use, resale, or modification is not permitted."),
    "    <h3>2. Intellectual Property</h3>",
    p("Intellectual property rights in this app and its content belong to the licensor. Unauthorized copying, distribution, or publication is prohibited."),
    "    <h3>3. Disclaimer</h3>",
    p('This app is provided "as is" without warranties of fitness for a particular purpose, accuracy, or completeness. We are not liable for any damages arising from use of this app.'),
    "    <h3>4. Restrictions on Use</h3>",
    p("If a user violates these terms, we reserve the right to restrict or prohibit use of this app."),
    "    <h3>5. Changes to These Terms</h3>",
    p("These terms may be changed as needed. Updated terms take effect when notified in the app or on this page."),
]


ENGLISH_IAP_TERMS = [
    "    <h3>1. License</h3>",
    p("The basic features of this app are available free of charge, while certain features and the removal of advertisements are offered through paid plans. Commercial use, resale, or modification is not permitted."),
    "    <h3>2. In-App Purchases</h3>",
    p("Paid plans include auto-renewable subscriptions and a one-time purchase (non-consumable). Payment is charged to your Apple ID through the App Store. The specific price and plan details displayed on the in-app purchase screen and in the App Store apply."),
    p("A subscription automatically renews unless canceled at least 24 hours before the end of the current period. The renewal fee is charged within 24 hours before the end of the current period."),
    p('To cancel a subscription, open the iOS Settings app, select your Apple Account, and then select "Subscriptions." A subscription cannot be canceled within this app. After cancellation, you may continue to use the paid plan until the end of the period for which you have already paid.'),
    p('Features obtained through the one-time purchase can be restored with "Restore Purchases" in this app while using the same Apple ID used for the original purchase. Refunds are governed by Apple\'s policies, and we cannot issue refunds directly.'),
    p("Prices and plan details may change. Any changes will be announced in advance in the app or on this page."),
    "    <h3>3. Intellectual Property</h3>",
    p("Intellectual property rights in this app and its content belong to the licensor. Unauthorized copying, distribution, or publication is prohibited."),
    "    <h3>4. Disclaimer</h3>",
    p('This app is provided "as is" without warranties of fitness for a particular purpose, accuracy, or completeness. We are not liable for any damages arising from use of this app.'),
    "    <h3>5. Restrictions on Use</h3>",
    p("If a user violates these terms, we reserve the right to restrict or prohibit use of this app."),
    "    <h3>6. Changes to These Terms</h3>",
    p("These terms may be changed as needed. Updated terms take effect when notified in the app or on this page."),
]


def english_legal_block(app: dict) -> str:
    """英語のプライバシー／利用規約。現状は Simple Photo Book（photo-book）のみ。

    日本語節（収集情報・広告・第三者提供・改定／ライセンス・課金・知的財産・免責・利用制限）を
    忠実に英訳する。アプリ名は "Simple Photo Book"。
    """
    if app.get("id") != "photo-book":
        return ""
    return "\n".join([
        '    <h2 id="privacy-en">Privacy Policy</h2>',
        p('"Simple Photo Book" handles user information according to the following policy.'),
        "    <h3>1. Information We Collect and Process</h3>",
        p("The main features of this app run entirely on your device. We do not collect or store your personal information on our servers."),
        p("Access to photos is used only to import and edit the photos you select, and remains on your device. Photos are never sent to an external server."),
        "    <h3>2. Advertising</h3>",
        p('This app displays ads via Google AdMob. AdMob may collect and use information such as advertising identifiers (for example IDFA) for ad delivery and measurement, and may share it with Google. Please see <a href="https://policies.google.com/technologies/ads">Google\'s advertising policies</a> for details. This app does not request App Tracking Transparency permission and does not track users across apps or websites (ads are delivered without cross-app tracking).'),
        "    <h3>3. Sharing with Third Parties</h3>",
        p("Except for the advertising provider above (Google), we do not provide your personal information to third parties."),
        "    <h3>4. Changes to This Privacy Policy</h3>",
        p("We may update this policy as needed. Material changes will be announced in the app or on this page."),
        '    <h2 id="terms-en">Terms of Use</h2>',
    ] + (ENGLISH_IAP_TERMS if app.get("flags", {}).get("iap") else ENGLISH_TERMS))


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
    english = english_legal_block(app)
    page = (template
            .replace("{{NAME}}", esc(app["name"]))
            .replace("{{LANG_SWITCH}}", lang_switch_block(bool(english)))
            .replace("{{UPDATED}}", esc(app.get("updated", site["updated"])))
            .replace("{{SUMMARY}}", esc(app["summary"]))
            .replace("{{FEATURES}}", features_block(app.get("features", [])))
            .replace("{{PRIVACY}}", privacy_block(app["name"], app.get("flags", {})))
            .replace("{{TERMS}}", terms_block(app.get("flags", {})))
            .replace("{{ENGLISH_LEGAL}}", english)
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
