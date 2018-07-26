import pprint
import os

import datetime
import re
# noinspection PyUnresolvedReferences
import urllib.parse as urlparse

import numpy
from flask import Flask, request, abort

from apscheduler.schedulers.background import BackgroundScheduler

import logging

from linebot.exceptions import (
    InvalidSignatureError, LineBotApiError
)

from constants import line_bot_api, handler, get_text_template_for_id, \
    get_text_template_for_delegate, DATABASE_URL, total_question_counts

from sample_handler import (
    add_group_event_handler, add_multimedia_event_handler
)

# noinspection PyUnresolvedReferences
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    SourceUser, SourceGroup, SourceRoom,
    TemplateSendMessage, ConfirmTemplate, MessageTemplateAction, ImageSendMessage,
    ButtonsTemplate, ImageCarouselTemplate, ImageCarouselColumn, URITemplateAction,
    ImagemapSendMessage, ImagemapArea, ImagemapAction, MessageImagemapAction, URIImagemapAction,
    PostbackTemplateAction, DatetimePickerTemplateAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage, FileMessage,
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent,
    FlexContainer, FlexComponent, FlexSendMessage,
    RichMenu, RichMenuArea, BaseSize
)

from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)
logging.basicConfig()

# todo 担当代わった場合押すボタンを設置
# todo sample に担当代わった列を追加
# todo　質問内容を聞くボタン


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String())
    staff_id = db.Column(db.String())
    real_name = db.Column(db.String())

    def __init__(self, user_id, staff_id, real_name):
        self.user_id = user_id
        self.staff_id = staff_id
        self.real_name = real_name

    def __repr__(self):
        return '<user_id {}>'.format(self.user_id)


class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String())
    text = db.Column(db.String())
    text_id = db.Column(db.String())
    text_type = db.Column(db.String())
    datetime = db.Column(db.DateTime())

    def __init__(self, user_id, text, text_id, text_type, dt):
        self.user_id = user_id
        self.text = text
        self.text_id = text_id
        self.text_type = text_type
        self.datetime = dt

    def __repr__(self):
        return f'<user_id {self.user_id} text:{self.text}>'


class Sample(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String())
    start_datetime = db.Column(db.DateTime)
    end_datetime = db.Column(db.DateTime)
    state = db.Column(db.String())

    def __init__(self, user_id, start_datetime, end_datetime, state):
        self.user_id = user_id
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.state = state

    def __repr__(self):
        return f'<Sample {self.id}>'


class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer)
    user_id = db.Column(db.String())
    question_number = db.Column(db.Integer)
    answer = db.Column(db.String())

    def __init__(self, sample_id, user_id, question_number, answer):
        self.sample_id = sample_id
        self.user_id = user_id
        self.question_number = question_number
        self.answer = answer

    def __repr__(self):
        return f'<Survey {self.sample_id} {self.question_number} {self.answer}>'


@app.route("/line/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    pprint.pprint(body, indent=2)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    now = datetime.datetime.now()

    user_text = event.message.text

    my_number_lost_flow(event, user_text)

    my_number_make_flow(event, user_text)

    my_number_others_flow(event, user_text)

    juminhyou_flow(event, user_text)

    kei_car_certificate_flow(event, user_text)

    certificates_flow(event, user_text)

    address_change_flow(event, user_text)

    start_timer(event, user_text, now)

    end_timer(event, user_text, now)

    insert_log_to_db(event, now)

    register_user(event, user_text)

    if user_text == 'data':
        push_summary()


def register_user(event, user_text):
    if user_text == "職員登録":
        line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text="職員番号を入力してください。\n正職員：半角数字4桁\n臨時職員：英数字8桁")]
        )
    if re.match('[A-Z]?\d{4}$', user_text):
        if len(user_text) in [4, 5]:
            line_bot_api.reply_message(
                event.reply_token,
                [TextSendMessage(
                    text=f"{user_text}を{line_bot_api.get_profile(event.source.user_id).display_name}さん"
                         f"の職員番号として登録しました。\n\n修正する場合、もう一度入力してください。")]
            )
            user_data = User(
                event.source.user_id,
                user_text,
                "dummy"
            )
            db.session.add(user_data)
            print(type(user_text))
            db.session.commit()


def end_timer(event, user_text, now):
    if user_text in ['計測終了']:
        # 両方おしているのをとって、ちゃんと直前が計測終了になってないことを確認する。
        start_log = Sample.query \
            .filter((Sample.user_id == event.source.user_id)) \
            .order_by(db.desc(Sample.start_datetime)).first()

        if start_log.start_datetime == start_log.end_datetime:
            str_dt = start_log.start_datetime.strftime("%H:%M:%S")
            start_log.end_datetime = now
            start_log.state = "end"
            db.session.commit()
            time_used = int((now - start_log.start_datetime).total_seconds())

            # richmenuを変更するコードを以下に
            user_id = event.source.user_id
            # user_id = "U0a028f903127e2178bd789b4b4046ba7"
            rms = line_bot_api.get_rich_menu_list()
            menu_init_rm = [rm for rm in rms if rm.name == "q1"][0]
            latest_menu_init_id = menu_init_rm.rich_menu_id
            line_bot_api.link_rich_menu_to_user(user_id, latest_menu_init_id)

            messages = [
                TextSendMessage(
                    text=f'対応お疲れ様です！\nご協力ありがとうございます！\n\n'
                         f'開始時刻:{str_dt}\n'
                         f'対応時間:{time_used}秒\n実験ID:{start_log.id}'
                ),
                TextSendMessage(
                    text="ご自身の対応の評価をお願いいたします。\n\n前に戻るボタン、キャンセルボタンを必要な場合は押してください。"),
            ]

            line_bot_api.reply_message(
                event.reply_token,
                messages
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f'前の計測はすでに終了しております。')
            )


def start_timer(event, user_text, now):
    # 両方おしているのをとって、ちゃんと直前が計測スタートになってないことを確認する。
    if user_text in ['計測スタート']:
        date_str = datetime.datetime.strftime(now, "%H:%M:%S")
        start_log = Sample.query \
            .filter((Sample.user_id == event.source.user_id)) \
            .order_by(db.desc(Sample.start_datetime)).first()

        if start_log is None:
            buttons_template = ButtonsTemplate(
                title='キャンセルする場合、その理由を押してください', text='お選びください', actions=[
                    PostbackTemplateAction(label='クレーム故に代わる必要', text='計測終了（キャンセル。クレーム故交代。）', data='cancel_クレーム故に代わる必要'),
                    PostbackTemplateAction(label='窓口呼び出し', text='計測終了（キャンセル。窓口呼び出し。）', data='cancel_窓口呼び出し'),
                ])
            template_message = TemplateSendMessage(
                alt_text='計測中です。キャンセルボタンが表示されています。', template=buttons_template
            )
            line_bot_api.reply_message(event.reply_token,
                                       [TextSendMessage(text=f'計測開始:{date_str}'),
                                        template_message])

            data = Sample(event.source.user_id, now, now, "ongoing")
            db.session.add(data)
            return
        if start_log.start_datetime == start_log.end_datetime:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f'計測はすでに開始しております。あるいは終了していない計測があります。')
            )
        else:
            buttons_template = ButtonsTemplate(
                title='キャンセルする場合、その理由を押してください', text='お選びください', actions=[
                    PostbackTemplateAction(label='クレーム故に代わる必要', text='計測終了（キャンセル。クレーム故に代わった。）', data='cancel_クレーム故に代わる必要'),
                    PostbackTemplateAction(label='その他', text='計測終了（キャンセル。その他。）', data='cancel_その他'),
                ])
            template_message = TemplateSendMessage(
                alt_text='計測中です。キャンセルボタンが表示されています。', template=buttons_template
            )

            buttons_template_change_operator = ButtonsTemplate(
                title='電話応対の職員が代わった場合押してください', text='代わった場合のみで結構です', actions=[
                    PostbackTemplateAction(label='職員が交代した', text='職員が交代した', data='change_staff'),
                ]
            )
            template_message_change_operator = TemplateSendMessage(
                alt_text='計測中です。キャンセルまたは対応職員が変更した場合、注意お願いします。', template=buttons_template_change_operator
            )
            line_bot_api.reply_message(event.reply_token,
                                       [TextSendMessage(text=f'計測開始:{date_str}\n\n職員ID:{staff_id}'),
                                        template_message,
                                        template_message_change_operator])

            data = Sample(event.source.user_id, now, now, "ongoing")
            db.session.add(data)


def insert_log_to_db(event, now):
    data = Log(
        event.source.user_id,
        event.message.text,
        event.message.id,
        event.message.type,
        now
    )
    db.session.add(data)
    db.session.commit()
    print('data committed to db.')


def address_change_flow(event, user_text):
    if user_text in ['住所異動']:
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(text='お選びください', title='住所関連でお探しですか？', actions=[
                MessageTemplateAction(label='住所変更の際の持ち物', text='住所変更の際の持ち物'),
                MessageTemplateAction(label='住所を変えず、世帯を変更', text='住所を変えず、世帯を変更'),
                MessageTemplateAction(label='住所修正（地番変更など）', text='住所修正（地番変更など）'),
            ]),
            CarouselColumn(text='お選びください', title='住所関連でお探しですか？', actions=[
                MessageTemplateAction(label='転出届を取り消したい', text='転出届を取り消したい'),
                MessageTemplateAction(label='転出証明を再交付', text='転出証明を再交付'),
                MessageTemplateAction(label='住所変更と同時に○○', text='住所変更と同時に○○'),
            ]),
            CarouselColumn(text='お選びください', title='住所関連でお探しですか？', actions=[
                MessageTemplateAction(label='住所変更と同時にこれら以外', text='住所変更と同時にこれら以外'),
                MessageTemplateAction(label='ダミー', text='ダミー'),
                MessageTemplateAction(label='ダミー', text='ダミー'),
            ]),
        ])
        template_message = TemplateSendMessage(
            alt_text='Carousel alt text', template=carousel_template)
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['住所変更の際の持ち物']:
        buttons_template = ButtonsTemplate(
            title='転入or転出？', text='お選びください', actions=[
                MessageTemplateAction(label='転入（市外から）', text='転入（市外から）'),
                MessageTemplateAction(label='転入（海外から）', text='転入（海外から）'),
                MessageTemplateAction(label='転出（市外へ）', text='転出（市外へ）'),
                MessageTemplateAction(label='転居（市内）', text='転居（市内）'),
            ])
        template_message = TemplateSendMessage(
            alt_text='転入or転出？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['転入（市外から）']:
        buttons_template = ButtonsTemplate(
            title='転入手続きをされるのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text='転入手続きをするのは本人'),
                MessageTemplateAction(label='本人以外', text='転入手続きをするのは本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text='転入手続きされるのはどなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['転入手続きをするのは本人']:
        reply_text = '本人確認書類、世帯全員分の通知カード（個人番号カード所得者を除く）、' \
                     '個人番号カード、住基カード（取得者のみ）、転出証明書（個人番号カード、住基カードで' \
                     '転出届をした人は、個人番号カード・住基カード）が必要です。\n\n転入者全員の在留カードまたは外国人登録証明書が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転入手続きをするのは本人以外']:
        buttons_template = ButtonsTemplate(
            title='転入手続きをするのはどなたでしょうか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人とつくば市で同一世帯となる人', text='本人とつくば市で同一世帯となる人が転入手続きをする'),
                MessageTemplateAction(label='任意代理人', text='任意代理人が転入手続きをする'),
                MessageTemplateAction(label='法定代理人', text='法定代理人が転入手続きをする'),
                MessageTemplateAction(label='親族や養護施設などの職員', text='親族や養護施設などの職員が転入手続きをする'),
            ])
        template_message = TemplateSendMessage(
            alt_text='転入手続きをするのはどなたでしょうか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['本人とつくば市で同一世帯となる人が転入手続きをする']:
        reply_text = '窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）、' \
                     '転出証明書（個人番号カード・住基カードで転出届をした人は、個人番号カード・住基カード）が必要です。外国人住民の場合、転入者全員の在留カードまたは外国人登録証明書が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['任意代理人が転入手続きをする']:
        reply_text = '委任状（※２）窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）、' \
                     '転出証明書（個人番号カード・住基カードで転出届をした人は、個人番号カード・住基カード）が必要です。任意代理人のマイナンバーカードの継続は照会書になり、' \
                     '後日来庁が必要です。外国人住民の場合、転入者全員の在留カードまたは外国人登録証明書が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['法定代理人が転入手続きをする']:
        reply_text = '''（親権者）
戸籍謄本（平日の昼間の場合は不要）
窓口に来た人の本人確認書類（※１）、
世帯全員分の通知カード（個人番号カード所得者を除く）、
個人番号カード・住基カード（取得者のみ）、
転出証明書（個人番号カード・住基カードで転出届をした人は、個人番号カード・住基カード）が必要です。

外国人住民の場合、転入者全員の在留カードまたは外国人登録証明書が必要です。
（成年後見人）登記事項証明書
窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）、転出証明書（個人番号カード・住基カードで転出届をした人は、個人番号カード・住基カード）が必要です。
外国人住民の場合、転入者全員の在留カードまたは外国人登録証明書が必要です'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['親族や養護施設などの職員が転入手続きをする']:
        reply_text = '''住民記録係に繋ぐ。\n\n施設などの職員証。親族の場合、本人が来庁不可能なことを証明する資料（施設入居・入院を証明するもの、介護認定等
窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）、転出証明書（個人番号カード・住基カードで転出届をした人は、個人番号カード・住基カード）が必要です。
外国人住民の場合、転入者全員の在留カードまたは外国人登録証明書が必要です。。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転入（海外から）']:
        buttons_template = ButtonsTemplate(
            title='転入手続きをされるのはどなたでしょうか？', text='お選びください', actions=[
                MessageTemplateAction(label='異動者本人', text='転入手続きをするのは異動者本人'),
                MessageTemplateAction(label='異動者本人以外', text='転入手続きをするのは異動者本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text='転入手続きをされるのはどなたでしょうか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['転入手続きをするのは異動者本人']:
        reply_text = '本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転入手続きをするのは異動者本人以外']:
        buttons_template = ButtonsTemplate(
            title='手続きするのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人とつくば市で同一世帯となる人', text='転入手続きをするのは本人とつくば市で同一世帯となる人'),
                MessageTemplateAction(label='任意代理人', text='転入手続きをするのは任意代理人'),
                MessageTemplateAction(label='法定代理人', text='転入手続きをするのは法定代理人'),
                MessageTemplateAction(label='親族や養護施設などの職員', text='転入手続きをするのは親族や養護施設などの職員'),
            ])
        template_message = TemplateSendMessage(
            alt_text='手続きするのはどなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['転入手続きをするのは本人とつくば市で同一世帯となる人']:
        reply_text = '''本人確認書類（※１）、転入する人全員のパスポート、戸籍謄本・戸籍の附票が必要です。
つくば市に在住したことがあれば、戸籍謄本・戸籍の附票は不要です。
外国人住民の場合、転入者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転入手続きをするのは任意代理人']:
        reply_text = '''委任状（※２）、本人確認書類（※１）、転入する人全員のパスポート、戸籍謄本・戸籍の附票が必要です。
つくば市に在住したことがあれば、戸籍謄本・戸籍の附票は不要です。
外国人住民の場合、転入者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転入手続きをするのは法定代理人']:
        reply_text = '''（親権者）
戸籍謄本（平日の昼間の場合は不要）
窓口に来た人の本人確認書類（※１）、転入する人全員のパスポート、戸籍謄本・戸籍の附票が必要です。
つくば市に在住したことがあれば、戸籍謄本・戸籍の附票は不要です。
外国人住民の場合、転入者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。


（成年後見人）
登記事項証明書が必要です。
窓口に来た人の本人確認書類（※１）、転入する人全員のパスポート、戸籍謄本・戸籍の附票が必要です。
つくば市に在住したことがあれば、戸籍謄本・戸籍の附票は不要です。
外国人住民の場合、転入者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転入手続きをするのは親族や養護施設などの職員']:
        reply_text = '''住民記録係に繋ぐ。

施設などの職員証。親族の場合、本人が来庁不可能なことを証明する資料（施設入居・入院を証明するもの、介護認定等
窓口に来た人の本人確認書類（※１）、転入する人全員のパスポート、戸籍謄本・戸籍の附票が必要です。

つくば市に在住したことがあれば、戸籍謄本・戸籍の附票は不要です。

外国人住民の場合、転入者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転出（市外へ）']:
        pretext = '転出手続きをするのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}異動者本人でしょうか？', text='お選びください', actions=[
                MessageTemplateAction(label='異動者本人', text=f'{pretext}異動者本人'),
                MessageTemplateAction(label='異動者本人以外', text=f'{pretext}異動者本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}異動者本人でしょうか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['転出手続きをするのは異動者本人']:
        reply_text = '''本人確認書類が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転出手続きをするのは異動者本人以外']:
        pretext = '転出手続きをするのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}どなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人とつくば市で同一世帯', text=f'{pretext}本人とつくば市で同一世帯'),
                MessageTemplateAction(label='任意代理人', text=f'{pretext}任意代理人'),
                MessageTemplateAction(label='法定代理人', text=f'{pretext}法定代理人'),
                MessageTemplateAction(label='親族や養護施設などの職員', text=f'{pretext}親族や養護施設などの職員')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}どなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['転出手続きをするのは本人とつくば市で同一世帯']:
        reply_text = '''窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転出手続きをするのは任意代理人']:
        reply_text = '''委任状（※2）、窓口に来た人の本人確認書類が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転出手続きをするのは法定代理人']:
        reply_text = '''（親権者）戸籍謄本、窓口に来た人の本人確認書類が必要です。（平日の昼間の来庁の場合、本籍地へ電話照会するため、戸籍謄本不要です。）
（成年後見人）登記事項証明書、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転出手続きをするのは親族や養護施設などの職員']:
        reply_text = '''住民記録係につなぐ。
（親族）本人が来庁不可能なことを証明する資料（施設入居・入院を証明するもの、介護認定など）、窓口に来た人の本人確認書類が必要です。
 
（施設などの職員）施設などの職員証、窓口に来た人の本人確認書類が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転居（市内）']:
        pretext = '転居手続きをされるのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}異動者本人ですか？', text='お選びください', actions=[
                MessageTemplateAction(label='異動者本人', text=f'{pretext}異動者本人'),
                MessageTemplateAction(label='異動者本人以外', text=f'{pretext}異動者本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}異動者本人ですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['転居手続きをされるのは異動者本人']:
        reply_text = '''本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。
外国人住民の場合、転居者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転居手続きをされるのは異動者本人以外']:
        pretext = '転居手続きをされるのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}どなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人と同一世帯となる人', text=f'{pretext}本人と同一世帯となる人'),
                MessageTemplateAction(label='任意代理人', text=f'{pretext}任意代理人'),
                MessageTemplateAction(label='法定代理人', text=f'{pretext}法定代理人'),
                MessageTemplateAction(label='親族や養護施設などの職員', text=f'{pretext}親族や養護施設などの職員')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}どなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['転居手続きをされるのは本人と同一世帯となる人']:
        reply_text = '''窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。
外国人住民の場合、転居者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転居手続きをされるのは任意代理人']:
        reply_text = '''委任状（※２）、窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。
外国人住民の場合、転居者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転居手続きをされるのは法定代理人']:
        reply_text = '''（親権者）
戸籍謄本　（平日の昼間の場合不要です）
窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。
外国人住民の場合、転居者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。


（成年後見人）
登記事項証明書が必要です。
窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。
外国人住民の場合、転居者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転居手続きをされるのは親族や養護施設などの職員']:
        reply_text = '''住民記録係に繋ぐ。\n\n施設等の職員証。親族の場合、本人が来庁不可能なことを証明するもの（施設入居・入院していることを証明するもの、介護認定等
窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。
外国人住民の場合、転居者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['住所を変えず、世帯を変更']:
        pretext = ''
        buttons_template = ButtonsTemplate(
            title=f'{pretext}以下のどれでしょうか？', text='お選びください', actions=[
                MessageTemplateAction(label='世帯分離', text=f'{pretext}世帯分離'),
                MessageTemplateAction(label='世帯合併', text=f'{pretext}世帯合併'),
                MessageTemplateAction(label='世帯主変更', text=f'{pretext}世帯主変更'),
                MessageTemplateAction(label='世帯構成変更', text=f'{pretext}世帯構成変更')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}以下のどれでしょうか？', template=buttons_template
        )
        description_of_options = '''
世帯分離：
1つの世帯を住所変更せずに2つに分ける。　※生計が別ですか?他課に相談済ですか？（保険料を安くするためなどの理由では受付できません）

世帯合併：
2つの世帯を住所変更せずに1つにする。　※生計が同じですか?

世帯主変更：
世帯主を変更する　※主に生計を立てるほうが変更になるということですか?

世帯構成変更：
同住所に存在する2つの世帯間で、人を異動させる。住所は変更されないので転居ではない。
        '''
        messages = [TextSendMessage(text=description_of_options), template_message]
        line_bot_api.reply_message(event.reply_token, messages)

    if user_text in ['世帯分離']:
        pretext = '世帯分離手続きをするのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}本人ですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text=f'{pretext}本人'),
                MessageTemplateAction(label='本人以外', text=f'{pretext}本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}本人ですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['世帯分離手続きをするのは本人']:
        reply_text = '''窓口に来た人の本人確認書類が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯分離手続きをするのは本人以外']:
        pretext = '世帯分離手続きをするのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}どなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人と同一世帯の人', text=f'{pretext}本人と同一世帯の人'),
                MessageTemplateAction(label='任意代理人', text=f'{pretext}任意代理人'),
                MessageTemplateAction(label='法定代理人', text=f'{pretext}法定代理人'),
                MessageTemplateAction(label='親族や養護施設などの職員', text=f'{pretext}親族や養護施設などの職員')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}どなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['世帯分離手続きをするのは本人と同一世帯の人']:
        reply_text = '''窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯分離手続きをするのは任意代理人']:
        reply_text = '''委任状（※２）、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯分離手続きをするのは法定代理人']:
        reply_text = '''（親権者）
戸籍謄本（平日の昼間は不要）、窓口に来た人の本人確認書類（※１）が必要です。

（成年後見人）
登記事項証明書、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯分離手続きをするのは親族や養護施設などの職員']:
        reply_text = '''（施設の職員）施設などの職員証、窓口に来た人の本人確認書類（※１）が必要です。
（親族）親族の場合、本人が来庁不可能なことを証明する資料（施設入居・入院を証明するもの、介護認定等）、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯合併']:
        pretext = '世帯合併手続きをするのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}本人ですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text=f'{pretext}本人'),
                MessageTemplateAction(label='本人以外', text=f'{pretext}本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}本人ですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['世帯合併手続きをするのは本人']:
        reply_text = '''窓口に来た人の本人確認書類が必要です'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯合併手続きをするのは本人以外']:
        pretext = '世帯合併手続きをするのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}どなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人と同一世帯の人', text=f'{pretext}本人と同一世帯の人'),
                MessageTemplateAction(label='任意代理人', text=f'{pretext}任意代理人'),
                MessageTemplateAction(label='法定代理人', text=f'{pretext}法定代理人'),
                MessageTemplateAction(label='親族や養護施設などの職員', text=f'{pretext}親族や養護施設などの職員')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}どなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['世帯合併手続きをするのは本人と同一世帯の人']:
        reply_text = '''窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯合併手続きをするのは任意代理人']:
        reply_text = '''委任状（※２）、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯合併手続きをするのは法定代理人']:
        reply_text = '''（親権者）
戸籍謄本（平日の昼間は不要）、窓口に来た人の本人確認書類（※１）が必要です。

（成年後見人）
登記事項証明書、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯合併手続きをするのは親族や養護施設などの職員']:
        reply_text = '''（施設の職員）施設などの職員証、窓口に来た人の本人確認書類（※１）が必要です。
（親族）親族の場合、本人が来庁不可能なことを証明する資料（施設入居・入院を証明するもの、介護認定等）、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯主変更']:
        pretext = '世帯主変更するのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}どなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text=f'{pretext}本人'),
                MessageTemplateAction(label='本人以外', text=f'{pretext}本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}どなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['世帯主変更するのは本人']:
        reply_text = '''窓口に来た人の本人確認書類が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯主変更するのは本人以外']:
        pretext = '世帯主変更するのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}どなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人と同一世帯の人', text=f'{pretext}本人と同一世帯の人'),
                MessageTemplateAction(label='任意代理人', text=f'{pretext}任意代理人'),
                MessageTemplateAction(label='法定代理人', text=f'{pretext}法定代理人'),
                MessageTemplateAction(label='親族や養護施設などの職員', text=f'{pretext}親族や養護施設などの職員')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}どなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['世帯主変更するのは本人と同一世帯の人']:
        reply_text = '''窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯主変更するのは任意代理人']:
        reply_text = '''委任状（※２）、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯主変更するのは法定代理人']:
        reply_text = '''（親権者）
戸籍謄本（平日の昼間は不要）、窓口に来た人の本人確認書類（※１）が必要です。

（成年後見人）
登記事項証明書、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯主変更するのは親族や養護施設などの職員']:
        reply_text = '''（施設の職員）施設などの職員証、窓口に来た人の本人確認書類（※１）が必要です。
（親族）親族の場合、本人が来庁不可能なことを証明する資料（施設入居・入院を証明するもの、介護認定等）、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯構成変更']:
        pretext = '世帯構成変更手続きをするのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}どなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text=f'{pretext}本人'),
                MessageTemplateAction(label='本人以外', text=f'{pretext}本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}どなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['世帯構成変更手続きをするのは本人']:
        reply_text = '''窓口に来た人の本人確認書類が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯構成変更手続きをするのは本人以外']:
        pretext = '世帯構成変更手続きをするのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}どなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人と同一世帯の人', text=f'{pretext}本人と同一世帯の人'),
                MessageTemplateAction(label='任意代理人', text=f'{pretext}任意代理人'),
                MessageTemplateAction(label='法定代理人', text=f'{pretext}法定代理人'),
                MessageTemplateAction(label='親族や養護施設などの職員', text=f'{pretext}親族や養護施設などの職員')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}どなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['世帯構成変更手続きをするのは本人と同一世帯の人']:
        reply_text = '''窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯構成変更手続きをするのは任意代理人']:
        reply_text = '''委任状（※２）、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯構成変更手続きをするのは法定代理人']:
        reply_text = '''（親権者）
戸籍謄本（平日の昼間は不要）、窓口に来た人の本人確認書類（※１）が必要です。

（成年後見人）
登記事項証明書、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['世帯構成変更手続きをするのは親族や養護施設などの職員']:
        reply_text = '''（施設の職員）施設などの職員証、窓口に来た人の本人確認書類（※１）が必要です。
（親族）親族の場合、本人が来庁不可能なことを証明する資料（施設入居・入院を証明するもの、介護認定等）、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['住所修正（地番変更など）']:
        pretext = '住所修正手続きをされるのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}居住者本人ですか？', text='お選びください', actions=[
                MessageTemplateAction(label='居住者本人', text=f'{pretext}居住者本人'),
                MessageTemplateAction(label='居住者本人以外', text=f'{pretext}居住者本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}居住者本人ですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['住所修正手続きをされるのは居住者本人']:
        reply_text = '''本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。
外国人住民の場合、転居者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['住所修正手続きをされるのは居住者本人以外']:
        pretext = '住所修正手続きをするのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}どなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人と同一世帯となる人', text=f'{pretext}本人と同一世帯となる人'),
                MessageTemplateAction(label='任意代理人', text=f'{pretext}任意代理人'),
                MessageTemplateAction(label='法定代理人', text=f'{pretext}法定代理人'),
                MessageTemplateAction(label='親族や養護などの職員', text=f'{pretext}親族や養護などの職員')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}どなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['住所修正手続きをするのは本人と同一世帯となる人']:
        reply_text = '''本人と同一世帯の人（転居前・転居後どちらでも）
窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。
外国人住民の場合、転居者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['住所修正手続きをするのは任意代理人']:
        reply_text = '''委任状※2、窓口に来た人の本人確認書類、世帯全員分の通知カード（個人番号カード取得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['住所修正手続きをするのは法定代理人']:
        reply_text = '''（親権者）戸籍謄本　（平日の昼間の場合不要です）
窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。
外国人住民の場合、転居者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。
（成年後見人）登記事項証明書が必要です。
窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。
外国人住民の場合、転居者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['住所修正手続きをするのは親族や養護などの職員']:
        reply_text = '''住民記録係につなぐ。
        
施設等の職員証。親族の場合、本人が来庁不可能なことを証明するもの（施設入居・入院していることを証明するもの、介護認定等

窓口に来た人の本人確認書類（※１）、世帯全員分の通知カード（個人番号カード所得者を除く）、個人番号カード・住基カード（取得者のみ）が必要です。

外国人住民の場合、転居者全員の在留カードまたは特別永住者証明書または外国人登録証明書が必要です。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転出届を取り消したい']:
        pretext = '取り消し手続きをされるのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}転出者本人ですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text=f'{pretext}本人'),
                MessageTemplateAction(label='本人以外', text=f'{pretext}本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}転出者本人ですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['取り消し手続きをされるのは本人']:
        reply_text = '''窓口に来た人の本人確認書類（※１）、転出証明書が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['取り消し手続きをされるのは本人以外']:
        pretext = '転出取り消し手続きをされるのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}どなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人と同一世帯の人', text=f'{pretext}本人と同一世帯の人'),
                MessageTemplateAction(label='任意代理人', text=f'{pretext}任意代理人'),
                MessageTemplateAction(label='法定代理人', text=f'{pretext}法定代理人'),
                MessageTemplateAction(label='親族や養護施設などの職員', text=f'{pretext}親族や養護施設などの職員')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}どなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['転出取り消し手続きをされるのは本人と同一世帯の人']:
        reply_text = '''窓口に来た人の本人確認書類（※１）、転出証明書が必要です。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転出取り消し手続きをされるのは任意代理人']:
        reply_text = '''委任状（※２）、窓口に来た人の本人確認書類（※１）、転出証明書が必要です。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転出取り消し手続きをされるのは法定代理人']:
        reply_text = '''（親権者）戸籍謄本（平日の昼間は不要）、窓口に来た人の本人確認書類（※１）、転出証明書が必要です。

（成年後見人）登記事項証明書、窓口に来た人の本人確認書類（※１）、転出証明書が必要です。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転出取り消し手続きをされるのは親族や養護施設などの職員']:
        reply_text = '''住民記録係に繋ぐ。
        
（施設の職員）施設などの職員証、窓口に来た人の本人確認書類（※１）、転出証明書が必要です。

（親族）親族の場合、本人が来庁不可能なことを証明する資料（施設入居・入院を証明するもの、介護認定等）、窓口に来た人の本人確認書類（※１）、転出証明書が必要です。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['転出証明を再交付']:
        pretext = '再交付手続きをされるのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}異動者本人ですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text=f'{pretext}本人'),
                MessageTemplateAction(label='本人以外', text=f'{pretext}本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}異動者本人ですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['再交付手続きをされるのは本人']:
        reply_text = '''窓口に来た人の本人確認書類が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['再交付手続きをされるのは本人以外']:
        pretext = '再交付手続きをされるのは'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}どなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人と同一世帯の人', text=f'{pretext}本人と同一世帯の人'),
                MessageTemplateAction(label='任意代理人', text=f'{pretext}任意代理人'),
                MessageTemplateAction(label='法定代理人', text=f'{pretext}法定代理人'),
                MessageTemplateAction(label='親族や養護施設などの職員', text=f'{pretext}親族や養護施設などの職員')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}どなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['再交付手続きをされるのは本人と同一世帯の人']:
        reply_text = '''窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['再交付手続きをされるのは任意代理人']:
        reply_text = '''委任状（※２）、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['再交付手続きをされるのは法定代理人']:
        reply_text = '''
（親権者）
戸籍謄本（平日の昼間は不要）、窓口に来た人の本人確認書類（※１）が必要です。

（成年後見人）
登記事項証明書、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['再交付手続きをされるのは親族や養護施設などの職員']:
        reply_text = '''（施設の職員）施設などの職員証、窓口に来た人の本人確認書類（※１）が必要です。
（親族）親族の場合、本人が来庁不可能なことを証明する資料（施設入居・入院を証明するもの、介護認定等）、窓口に来た人の本人確認書類（※１）が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['住所変更と同時に○○']:
        pretext = '住所変更と同時に'
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(title=f'{pretext}されたいことはどれですか？', text='お選びください', actions=[
                MessageTemplateAction(label='住民票の発行', text=f'{pretext}住民票の発行'),
                MessageTemplateAction(label='税証明書', text=f'{pretext}税証明書'),
                MessageTemplateAction(label='印鑑登録', text=f'{pretext}印鑑登録'),
            ]),
            CarouselColumn(text='お選びください', title=f'{pretext}されたいことはどれですか？', actions=[
                MessageTemplateAction(label='印鑑証明', text=f'{pretext}印鑑証明'),
                MessageTemplateAction(label='通知カードの再発行', text=f'{pretext}通知カードの再発行'),
                MessageTemplateAction(label='マイナンバーカードの申請', text=f'{pretext}マイナンバーカードの申請'),
            ]),
            CarouselColumn(text='お選びください', title=f'{pretext}されたいことはどれですか？', actions=[
                MessageTemplateAction(label='これら以外', text=f'{pretext}これら以外'),
                MessageTemplateAction(label='ダミー', text=f'ダミー'),
                MessageTemplateAction(label='ダミー', text=f'ダミー'),
            ]),
        ])
        template_message = TemplateSendMessage(
            alt_text='Carousel alt text', template=carousel_template)
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in [f'住所変更と同時に通知カードの再発行', f'住所変更と同時にマイナンバーカードの申請']:
        reply_text = '''メニューから、マイナンバー関連を選んで、欲しい情報を選んでください。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['住所変更と同時に印鑑証明']:
        reply_text = '''（市内異動）すでに印鑑登録をしているのであれば、住所変更をした時点で自動的に証明書に記載される住所が変更される。印鑑登録証と本人確認書類（※１）が必要。


（市外からの異動）印鑑登録をすればできる。登録したい印鑑と写真付き本人確認書類（運転免許証やパスポート等）が必要

詳細は印鑑登録関連のフローにて
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時にこれら以外']:
        pretext = '住所変更と同時に'
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(title=f'{pretext}なにをされますか？', text='お選びください。', actions=[
                MessageTemplateAction(label='国民健康保険', text=f'{pretext}国民健康保険'),
                MessageTemplateAction(label='後期高齢者医療保険', text=f'{pretext}後期高齢者医療保険'),
                MessageTemplateAction(label='マル福', text=f'{pretext}マル福'),
            ]),
            CarouselColumn(title=f'{pretext}なにをされますか？', text='お選びください。', actions=[
                MessageTemplateAction(label='国民年金', text=f'{pretext}国民年金'),
                MessageTemplateAction(label='児童手当', text=f'{pretext}児童手当'),
                MessageTemplateAction(label='児童扶養手当', text=f'{pretext}児童扶養手当'),
            ]),
            CarouselColumn(title=f'{pretext}なにをされますか？', text='お選びください。', actions=[
                MessageTemplateAction(label='ひとり親など児童福祉金', text=f'{pretext}ひとり親など児童福祉金'),
                MessageTemplateAction(label='いばらきキッズクラブカード', text=f'{pretext}いばらきキッズクラブカード'),
                MessageTemplateAction(label='小中学校/義務教育学校', text=f'{pretext}小中学校/義務教育学校'),
            ]),
            CarouselColumn(title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='予防接種予診票', text=f'{pretext}予防接種予診票'),
                MessageTemplateAction(label='母子健康手帳・受診票', text=f'{pretext}母子健康手帳・受診票'),
                MessageTemplateAction(label='各種がん検診・健康診断', text=f'{pretext}各種がん検診・健康診断'),
            ]),
            CarouselColumn(title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='介護保険', text=f'{pretext}介護保険'),
                MessageTemplateAction(label='各種障害者手帳等', text=f'{pretext}各種障害者手帳等'),
                MessageTemplateAction(label='各種障害児（者）手当など', text=f'{pretext}各種障害児（者）手当など'),
            ]),
            CarouselColumn(title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='原付バイクなど', text=f'{pretext}原付バイクなど'),
                MessageTemplateAction(label='ダミー', text=f'{pretext}ダミー'),
                MessageTemplateAction(label='ダミー', text=f'{pretext}ダミー'),
            ]),

        ])
        template_message = TemplateSendMessage(
            alt_text='Carousel alt text', template=carousel_template)
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in [f'住所変更と同時に国民健康保険']:
        pretext = '国民健康保険&'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='転入', text=f'{pretext}転入'),
                MessageTemplateAction(label='転居・転出', text=f'{pretext}転居・転出')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}なにをされますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['国民健康保険&転入']:
        reply_text = '''本人確認書類、マイナンバーがわかるものが必要です。その他詳細は国民健康保険課まで。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['国民健康保険&転居・転出']:
        reply_text = '''本人確認書類、マイナンバーがわかるもの、国民健康保険証が必要です。その他詳細は国民健康保険課まで。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に後期高齢者医療保険']:
        pretext = '後期高齢者医療保険&'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='転入', text=f'{pretext}転入'),
                MessageTemplateAction(label='転居・転出', text=f'{pretext}転居・転出')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}なにをされますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['後期高齢者医療保険&転入']:
        reply_text = '''印鑑、負担区分等証明書、マイナンバーがわかるもの。
        その他詳細は、医療年金課までお問い合わせください。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['後期高齢者医療保険&転居・転出']:
        reply_text = '''印鑑、後期高齢者医療被保険者証、マイナンバーがわかるもの。
        その他詳細は、医療年金課までお問い合わせください。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時にマル福']:
        pretext = 'マル福&'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='転入', text=f'{pretext}転入'),
                MessageTemplateAction(label='転居・転出', text=f'{pretext}転居・転出')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}なにをされますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['マル福&転入']:
        pretext = 'マル福を申請&転入&'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}何に該当しますか？', text='お選びください', actions=[
                MessageTemplateAction(label='妊娠している', text=f'{pretext}妊娠している'),
                MessageTemplateAction(label='各種障害手帳を持っている', text=f'{pretext}各種障害手帳を持っている'),
                MessageTemplateAction(label='中学３年生までのお子様あり', text=f'{pretext}中学３年生までのお子様あり'),
                MessageTemplateAction(label='ひとり親家庭', text=f'{pretext}ひとり親家庭')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}何に該当しますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['マル福を申請&転入&妊娠している']:
        reply_text = '''所得制限があります。

印鑑、母子健康手帳、健康保険証、預金通帳、所得証明書または課税証明書、同意書、マイナンバーがわかるものが必要です。
その他詳細については、医療年金課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['マル福を申請&転入&各種障害手帳を持っている']:
        reply_text = '''所得制限があります。
        
        本人確認書類、印鑑、健康保険証、預金通帳、所得証明書または課税証明書、身体障害者手帳等（重度心身障害者の方）、同意書、マイナンバーがわかるものが必要です。
        その他詳細については、医療年金課までお問い合わせください。

        '''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['マル福を申請&転入&中学３年生までのお子様あり']:
        reply_text = '''所得制限なし。本人確認書類、印鑑、健康保険証、預金通帳、所得証明書または課税証明書、同意書、マイナンバーがわかるものが必要です。
その他詳細については、医療年金課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['マル福を申請&転入&ひとり親家庭']:
        reply_text = '''所得制限あり。\n\n\n本人確認書類、印鑑、健康保険証、預金通帳、所得証明書または課税証明書、同意書、マイナンバーがわかるもの、ひとり親であることを証明する書類が必要です。
その他詳細については、医療年金課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['マル福&転居・転出']:
        reply_text = '''現在つくば市でマル福を受給している場合
印鑑、マル福受給者証が必要です。
その他詳細については、医療年金課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に国民年金']:
        pretext = '国民年金と同時に'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='転入', text=f'{pretext}転入'),
                MessageTemplateAction(label='転居', text=f'{pretext}転居'),
                MessageTemplateAction(label='転出', text=f'{pretext}転出')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}なにをされますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['国民年金と同時に転入']:
        reply_text = '''受給中・加入中の方
年金手帳またはマイナンバーがわかるものが必要です。
その他詳細については、医療年金課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['国民年金と同時に転居']:
        reply_text = '''受給中の方
年金手帳またはマイナンバーがわかるものが必要です。
その他詳細については、医療年金課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['国民年金と同時に転出']:
        reply_text = '''海外へ転出される方
年金手帳またはマイナンバーがわかるものが必要です。
その他詳細については、医療年金課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に児童手当']:
        pretext = '児童手当同時に'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='転入', text=f'{pretext}転入'),
                MessageTemplateAction(label='転居', text=f'{pretext}転居'),
                MessageTemplateAction(label='転出', text=f'{pretext}転出')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}なにをされますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['児童手当同時に転入']:
        reply_text = '''印鑑、請求者の健康保険証、預金通帳、児童が市外にいる場合は住民票の写しが必要です。必要なものが不足していても申請はできます。
その他詳細については、こども政策課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['児童手当同時に転居']:
        reply_text = '''印鑑（電話番号が変更になった方は手続きが必要です）
その他詳細については、こども政策課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['児童手当同時に転出']:
        reply_text = '''印鑑（受給者と児童が転出、または受給者のみ転出の場合は、転入先で所得証明書が必要になる場合があります。受給者のみ転出の場合は、住民票の写しが必要になる場合があります。転入先の市町村で問い合わせください。
その他詳細については、こども政策課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に児童扶養手当']:
        pretext = '児童扶養手当と同時に'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='転入・転居', text=f'{pretext}転入・転居'),
                MessageTemplateAction(label='転出', text=f'{pretext}転出')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}なにをされますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['児童扶養手当と同時に転入・転居']:
        reply_text = '''印鑑、児童扶養手当証書（新規の場合、戸籍謄本）が必要です。
その他詳細については、こども政策課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['児童扶養手当と同時に転出']:
        reply_text = '''印鑑が必要です。
どの他詳細については、こども政策課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時にひとり親など児童福祉金']:
        pretext = 'ひとり親など児童福祉金と同時に'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='転入', text=f'{pretext}転入'),
                MessageTemplateAction(label='転居・転出', text=f'{pretext}転居・転出')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}なにをされますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['ひとり親など児童福祉金と同時に転入']:
        reply_text = '''印鑑、児童の戸籍謄本が必要です。
その他詳細については、こども政策課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['ひとり親など児童福祉金と同時に転居・転出']:
        reply_text = '''印鑑が必要です。
その他詳細については、こども政策課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時にいばらきキッズクラブカード']:
        reply_text = '''転入の場合のみ。\n児童の健康保険証、母子健康手帳等児童の年齢がわかるものが必要です。
その他詳細については、こども政策課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に小中学校/義務教育学校']:
        pretext = '小中学校/義務教育学校と同時に'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='転入', text=f'{pretext}転入'),
                MessageTemplateAction(label='転居', text=f'{pretext}転居(学区変更伴う)'),
                MessageTemplateAction(label='転出', text=f'{pretext}転出（引き続きつくば市の学校へ就学する場合）')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}なにをされますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['小中学校/義務教育学校と同時に転入']:
        reply_text = '''印鑑が必要です。
その他詳細については、学務課にお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['小中学校/義務教育学校と同時に転居(学区変更伴う)']:
        reply_text = '''印鑑が必要です。
その他詳細については、学務課にお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['小中学校/義務教育学校と同時に転出（引き続きつくば市の学校へ就学する場合）']:
        reply_text = '''印鑑が必要です。
その他詳細については、学務課にお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に予防接種予診票']:
        reply_text = '''転入（7歳6か月未満のお子様がいる家庭の場合）
予防接種記録のわかるもの（母子健康手帳等）が必要です。
その他詳細については、健康増進課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に母子健康手帳・受診票']:
        reply_text = '''妊娠している場合

母子健康手帳、妊婦一般健康診査受診票が必要です。
その他詳細については、健康増進課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に各種がん検診・健康診断']:
        reply_text = '''転入（各種がん検診を希望の方、39歳以下で検診を受ける機会のない方（学生は除く））
受診券が発行されます。その他詳細については、健康増進課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に介護保険']:
        pretext = '介護保険と同時に'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='転入', text=f'{pretext}転入'),
                MessageTemplateAction(label='転居', text=f'{pretext}転居'),
                MessageTemplateAction(label='転出', text=f'{pretext}転出')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}なにをされますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['介護保険と同時に転入']:
        reply_text = '''受給資格証明書（お持ちの方のみ）、マイナンバーがわかるものが必要です。
その他詳細については、介護保険課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['介護保険と同時に転居']:
        reply_text = '''介護保険証、負担割合証、負担限度額認定証（お持ちの方のみ）が必要です。
その他詳細については、介護保険課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['介護保険と同時に転出']:
        reply_text = '''介護保険証、負担限度額認定証（お持ちの方のみ）、負担割合証（受給資格証明書が交付されます）が必要です。
その他詳細については、介護保険課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に各種障害者手帳等']:
        reply_text = '''転入・転居
        
印鑑、各種手帳（身体障害者手帳、療育手帳、精神障害者保健福祉手帳等）、各種サービス受給者証、自立支援医療受給者証などが必要です。
その他詳細については、障害福祉課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に各種障害児（者）手当など']:
        pretext = '各種障害児（者）手当等と同時に'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='転入', text=f'{pretext}転入'),
                MessageTemplateAction(label='海外転出', text=f'{pretext}海外転出')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}なにをされますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['各種障害児（者）手当等と同時に転入']:
        reply_text = '''印鑑、特別児童扶養手当受給資格者は証書及び新住所の住民票謄本が必要です。
その他詳細については、障害福祉課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['各種障害児（者）手当等と同時に海外転出']:
        reply_text = '''資格喪失手続きが必要です。詳細については、障害福祉課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in [f'住所変更と同時に原付バイクなど']:
        pretext = '原付バイクと同時に'
        buttons_template = ButtonsTemplate(
            title=f'{pretext}なにをされますか？', text='お選びください', actions=[
                MessageTemplateAction(label='転入', text=f'{pretext}転入'),
                MessageTemplateAction(label='転居', text=f'{pretext}転居'),
                MessageTemplateAction(label='転出', text=f'{pretext}転出')
            ])
        template_message = TemplateSendMessage(
            alt_text=f'{pretext}なにをされますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['原付バイクと同時に転入']:
        reply_text = '''印鑑、廃車証明書、本人確認書類が必要です。
その他詳細については、市民税課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['原付バイクと同時に転居']:
        reply_text = '''印鑑、標識交付証明書、本人確認書類が必要です。
その他詳細については、市民税課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['原付バイクと同時に転出']:
        reply_text = '''印鑑、標識交付証明書、本人確認書類、ナンバープレートが必要です。
その他詳細については、市民税課までお問い合わせください。
'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )


def certificates_flow(event, user_text):
    # q1
    if user_text in ['各種証明書', '住所変更と同時に税証明書']:
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(text='お探しなのはどれでしょう？', title='お選びください。', actions=[
                MessageTemplateAction(label='住民票', text='住民票がほしい'),
                MessageTemplateAction(label='戸籍謄本/改製原戸/戸籍の附票', text='戸籍謄本・抄本、改製原戸・除籍・戸籍の附票がほしい。'),
                MessageTemplateAction(label='軽自動車用住所証明書', text='軽自動車用住所証明書がほしい'),
            ]),
            CarouselColumn(text='お探しなのはどれでしょう？', title='お選びください。', actions=[
                MessageTemplateAction(label='身分証明書がほしい', text='身分証明書がほしい'),
                MessageTemplateAction(label='独身証明書がほしい', text='独身証明書がほしい'),
                MessageTemplateAction(label='受理証明書がほしい', text='受理証明書がほしい'),
            ]),
            CarouselColumn(text='お探しなのはどれでしょう？', title='お選びください。', actions=[
                MessageTemplateAction(label='戸籍届記載事項証明書', text='戸籍届記載事項証明書'),
                MessageTemplateAction(label='自動車の仮ナンバーがほしい', text='自動車の仮ナンバーがほしい'),
                MessageTemplateAction(label='住所変更証明書がほしい', text='住所変更証明書がほしい'),
            ]),
            CarouselColumn(text='お探しなのはどれでしょう？', title='お選びください。', actions=[
                MessageTemplateAction(label='合併証明', text='合併証明'),
                MessageTemplateAction(label='不在住所証明書・不在籍証明書', text='不在住所証明書・不在籍証明書'),
                MessageTemplateAction(label='住民票の写しの広域交付', text='住民票の写しの広域交付'),
            ]),
            CarouselColumn(text='お探しなのはどれでしょう？', title='お選びください。', actions=[
                MessageTemplateAction(label='納税証明書', text='納税証明書'),
                MessageTemplateAction(label='課税/非課税/所得証明', text='課税/非課税/所得証明'),
                MessageTemplateAction(label='資産税証明', text='資産税証明'),
            ]),
        ])
        template_message = TemplateSendMessage(
            alt_text='Carousel alt text', template=carousel_template)
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['不在住所証明書・不在籍証明書']:
        reply_text = '誰でも申請できます。窓口に来た人の本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['住民票の写しの広域交付']:
        reply_text = '２００円。本人または本人と同一世帯の人で、窓口に来た人の本人確認書類が必要です。申請者は記載台に設置されていないので、来庁の際は証明受付窓口までお越しください。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    inkan_flow(event, user_text)
    if user_text in ['戸籍謄本・抄本、改製原戸・除籍・戸籍の附票がほしい。', 'ksk']:
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(text='ほしいのはどなたですか？', title='お選びください。', actions=[
                MessageTemplateAction(label='本人', text='本人が戸籍系書類がほしい。'),
                MessageTemplateAction(label='本人配偶者、直系血族',
                                      text='本人の配偶者、直系の血族（本人の親、祖父母、子、孫）が戸籍系書類をほしい。'),
                MessageTemplateAction(label='任意代理人', text='任意代理人が戸籍系書類をほしい。')
            ]),
            CarouselColumn(text='ほしいのはどなたですか？', title='お選びください', actions=[
                MessageTemplateAction(label='成年後見人', text='成年後見人が戸籍系書類をほしい。'),
                MessageTemplateAction(label='親族',
                                      text='親族（本人が死亡しており、直系の血族もいない場合）が戸籍系書類をほしい。'),
                MessageTemplateAction(label='ダミー', text='このボタンは、ボタンの数を揃えるためのダミーです。')
            ]),
            CarouselColumn(text='ほしいのはどなたですか？', title='お選びください', actions=[
                MessageTemplateAction(label='特定事務受給者', text='特定事務時給者が戸籍系書類をほしい。'),
                MessageTemplateAction(label='国/地方公共団体職員', text='国・地方公共団体の機関の職員からの請求'),
                MessageTemplateAction(label='ダミー', text='このボタンは、ボタンの数を揃えるためのダミーです。')
            ])
        ])
        template_message = TemplateSendMessage(
            alt_text='Carousel alt text', template=carousel_template)
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['本人が戸籍系書類がほしい。']:
        reply_text = '本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['本人の配偶者、直系の血族（本人の親、祖父母、子、孫）が戸籍系書類をほしい。']:
        reply_text = '直系の血族であることを証明できるもの（例：戸籍謄本・抄本）、本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['任意代理人が戸籍系書類をほしい。']:
        reply_text = '委任状、窓口に来た人の本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['成年後見人が戸籍系書類をほしい。']:
        reply_text = '登記事項証明書、本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['親族（本人が死亡しており、直系の血族もいない場合）が戸籍系書類をほしい。']:
        reply_text = '問い合わせについては、証明交付係につなく。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['特定事務時給者が戸籍系書類をほしい。']:
        reply_text = '問い合わせについては、証明交付係につなく。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['国・地方公共団体の機関の職員からの請求']:
        reply_text = '問い合わせについては、証明交付係につなく。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['身分証明書がほしい']:
        buttons_template = ButtonsTemplate(
            title='身分証明書がほしいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text='本人が身分証明書をほしい'),
                MessageTemplateAction(label='本人以外', text='本人以外が身分証明書をほしい')
            ])
        template_message = TemplateSendMessage(
            alt_text='身分証明書がほしいのはどなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['本人が身分証明書をほしい']:
        reply_text = '本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['本人以外が身分証明書をほしい']:
        reply_text = '委任状があっても本籍が不明だったり、申請書記載の本籍が誤っているときは、交付できません。\n\n' \
                     '委任状、窓口に来た人の本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['独身証明書がほしい']:
        buttons_template = ButtonsTemplate(
            title='独身証明書がほしいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text='本人が独身証明書をほしい'),
                MessageTemplateAction(label='本人以外', text='本人以外が独身証明書をほしい')
            ])
        template_message = TemplateSendMessage(
            alt_text='独身証明書がほしいのはどなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['本人が独身証明書をほしい']:
        reply_text = '本人確認書類と（あれば）印鑑が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['本人以外が独身証明書をほしい']:
        reply_text = '本人にしか交付できません。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['受理証明書がほしい']:
        buttons_template = ButtonsTemplate(
            title='受理証明書がほしいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='届出人(本人)', text='受理証明書を届出人がほしい'),
                MessageTemplateAction(label='本人以外', text='受理証明を本人以外がほしい')
            ])
        template_message = TemplateSendMessage(
            alt_text='受理証明書がほしいのはどなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['受理証明書を届出人がほしい']:
        reply_text = '本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['受理証明を本人以外がほしい']:
        reply_text = '委任状、窓口に来た人の本人確認書類が必要です。（委任状があっても本籍が不明だったり、申請書記載の本籍が誤っているときは、交付できません）'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['戸籍届記載事項証明書']:
        reply_text = '戸籍届記載事項証明書（戸籍届出をした市役所で交付する）（使用目的が制限されている）' \
                     '（1~2か月以上前に届出した届書は法務局に送付され交付できない可能性があるので、戸籍係へ確認をとる必要がある） ※350円'
        messages = get_text_send_messages(event, reply_text)
        buttons_template = ButtonsTemplate(
            title='戸籍届記載事項証明書をほしいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='届出人（本人）', text='戸籍届記載事項証明書をほしいのは届出人（本人）'),
                MessageTemplateAction(label='利害関係人', text='戸籍届記載事項証明書をほしいのは利害関係人'),
                MessageTemplateAction(label='死亡給付金の受け取り者', text='戸籍届記載事項証明書をほしいのは死亡給付金の受け取り者（死亡届の記載事項証明）'),
                MessageTemplateAction(label='該当の子の親', text='戸籍届記載事項証明書をほしいのは該当の子の親'),
            ])
        template_message = TemplateSendMessage(
            alt_text='戸籍届記載事項証明書をほしいのはどなたですか？', template=buttons_template
        )
        messages.append(template_message)
        line_bot_api.reply_message(event.reply_token, messages)
    if user_text in ['戸籍届記載事項証明書をほしいのは届出人（本人）']:
        reply_text = '本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['戸籍届記載事項証明書をほしいのは利害関係人']:
        reply_text = 'ケースバイケースであるため、証明交付係につなぐ'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['戸籍届記載事項証明書をほしいのは死亡給付金の受け取り者（死亡届の記載事項証明）']:
        reply_text = '簡易保険の証書等(原本）、窓口に来た人の本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['戸籍届記載事項証明書をほしいのは該当の子の親']:
        reply_text = '※出生届の記載事項証明。届出人でなくても親であれば、委任状をもって取得できる。委任状（届出人でない場合）、窓口に来た人の本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['自動車の仮ナンバーがほしい']:
        reply_text = '''窓口に来た人の本人確認書類、
臨時運行する車の自賠責保険証明書の原本、
臨時運行する車の自動車検査証または抹消登録証明書または完成検査終了証等（車体番号・社名・車体形状が確認できるもの）、窓口に来た人の印鑑(法人の場合は法人の印鑑）、法人に所属していることを示す社員証や代表者からの在職証明書が必要です。'''
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['住所変更証明書がほしい']:
        buttons_template = ButtonsTemplate(
            title='住所変更証明書がほしいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text='住所変更証明書がほしいのは本人'),
                MessageTemplateAction(label='本人以外', text='住所変更証明書がほしいのは本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text='住所変更証明書がほしいのはどなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['住所変更証明書がほしいのは本人']:
        reply_text = '''（町名地番変更による住所変更を証明するもの） ※無料'''
        messages = get_text_send_messages(event, reply_text)
        reply_text = '窓口に来た人の本人確認書類が必要です。'
        messages.extend(get_text_send_messages(event, reply_text))
        line_bot_api.reply_message(
            event.reply_token,
            messages
        )
    if user_text in ['住所変更証明書がほしいのは本人以外']:
        reply_text = '窓口に来た人の本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['合併証明']:
        reply_text = '（旧町村がつくば市に合併されたことを文章により証明するもの） ※無料'
        messages = get_text_send_messages(event, reply_text)
        buttons_template = ButtonsTemplate(
            title='合併証明が必要なかたはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text='合併証明が必要なのは本人'),
                MessageTemplateAction(label='本人以外', text='合併証明が必要なのは本人以外')
            ])
        template_message = TemplateSendMessage(
            alt_text='合併証明が必要なかたはどなたですか？', template=buttons_template
        )
        messages.append(template_message)
        line_bot_api.reply_message(event.reply_token, messages)
    if user_text in ['合併証明が必要なのは本人']:
        reply_text = '窓口に来た人の本人確認書類が必要です'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['合併証明が必要なのは本人以外']:
        reply_text = '窓口に来た人の本人確認書類が必要です'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['納税証明書']:
        messages = [TextSendMessage(text='細かい質問があったら、納税課に繋ぐ。1通200円。（軽自動車は無料。）')]

        buttons_template = ButtonsTemplate(
            title='どなたが必要ですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text='本人が納税証明書をほしい'),
                MessageTemplateAction(label='本人と同一世帯の人', text='本人と同一世帯の人が納税証明書をほしい'),
                MessageTemplateAction(label='任意代理人', text='任意代理人が納税証明書をほしい'),
                MessageTemplateAction(label='軽自動車税納税証明書', text='軽自動車税納税証明書'),
            ])
        template_message = TemplateSendMessage(
            alt_text='どなたが必要ですか？', template=buttons_template
        )
        messages.append(template_message)
        line_bot_api.reply_message(event.reply_token, messages)

    if user_text in ['本人が納税証明書をほしい']:
        reply_text = '窓口に来た人の本人確認書類が必要です。'
        department_to_connect = "納税課"
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect=department_to_connect)
        )
    if user_text in ['本人と同一世帯の人が納税証明書をほしい']:
        reply_text = '窓口に来た人の本人確認書類が必要です。\n市外に転出している場合は、委任状を要してもらう案内をする。'
        department_to_connect = "納税課"
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect=department_to_connect)
        )

    if user_text in ['任意代理人が納税証明書をほしい']:
        reply_text = '委任状と、窓口に来た人の本人確認書類が必要です。'
        department_to_connect = "納税課"
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect=department_to_connect)
        )

    if user_text in ['軽自動車税納税証明書']:
        buttons_template = ButtonsTemplate(
            title='証明書をほしいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text='本人が軽自動車税納税証明をほしい'),
                MessageTemplateAction(label='本人以外', text='本人以外が軽自動車税納税証明をほしい。'),
            ])
        template_message = TemplateSendMessage(
            alt_text='証明書をほしいのはどなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['本人が軽自動車税納税証明をほしい']:
        reply_text = '窓口に来た人の本人確認書類と自動車のナンバーが必要です。'
        department_to_connect = "納税課"
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect=department_to_connect)
        )

    if user_text in ['本人以外が軽自動車税納税証明をほしい。']:
        reply_text = '該当の車の車検証（コピーでも可）、窓口に来た人の本人確認書類が必要です。'
        department_to_connect = "納税課"
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect=department_to_connect)
        )

    if user_text in ['課税/非課税/所得証明']:
        buttons_template = ButtonsTemplate(
            title='証明書をほしいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text='本人が課税/非課税/所得証明をほしい'),
                MessageTemplateAction(label='本人と同一世帯の人', text='本人と同一世帯の人が課税/非課税/所得証明'),
                MessageTemplateAction(label='任意代理人', text='任意代理人が課税/非課税/所得証明をほしい'),
                MessageTemplateAction(label='事業所所在証明', text='事業所所在証明'),
            ])
        template_message = TemplateSendMessage(
            alt_text='証明書をほしいのはどなたですか？', template=buttons_template
        )
        messages = [TextSendMessage(text='細かい質問があったら、市民税課に繋ぐ。1通200円。（軽自動車は無料。）'), template_message]
        line_bot_api.reply_message(event.reply_token, messages)

    if user_text in ['本人が課税/非課税/所得証明をほしい']:
        reply_text = '窓口に来た人の本人確認書類が必要です。'
        department_to_connect = "市民税課"
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect=department_to_connect)
        )

    if user_text in ['本人と同一世帯の人が課税/非課税/所得証明']:
        reply_text = '窓口に来た人の本人確認書類が必要です。\n市街に転出している場合は、現在同一世帯であることが証明できる住民票などがなければ委任状が必要。ない場合は市民税課に相談に行くよう案内。'
        department_to_connect = "市民税課"
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect=department_to_connect)
        )

    if user_text in ['任意代理人が課税/非課税/所得証明をほしい']:
        reply_text = '委任状、窓口に来た人の本人確認書類が必要です。'
        department_to_connect = "市民税課"
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect=department_to_connect)
        )

    if user_text in ['事業所所在証明']:
        reply_text = '窓口に来た人の本人確認書類が必要です。'
        department_to_connect = "市民税課"
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect=department_to_connect)
        )

    if user_text in ['資産税証明']:
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(text='お選びください', title='お求めなのはどれでしょう？', actions=[
                MessageTemplateAction(label='固定資産評価・公果証明・名寄帳の写し', text='固定資産評価・公果証明・名寄帳の写し'),
                MessageTemplateAction(label='固定資産課税台帳記載事項証明', text='固定資産課税台帳記載事項証明'),
                MessageTemplateAction(label='公課証明', text='公課証明'),
            ]),
            CarouselColumn(text='お選びください', title='お求めなのはどれでしょう？', actions=[
                MessageTemplateAction(label='現況証明・家屋滅失証明', text='現況証明・家屋滅失証明'),
                MessageTemplateAction(label='住宅用家屋証明', text='住宅用家屋証明'),
                MessageTemplateAction(label='地番図・航空写真', text='地番図・航空写真'),
            ]),
            CarouselColumn(text='お選びください', title='お求めなのはどれでしょう？', actions=[
                MessageTemplateAction(label='評価額通知書', text='評価額通知書'),
                MessageTemplateAction(label='ダミー', text='ダミー'),
                MessageTemplateAction(label='ダミー', text='ダミー'),
            ]),
        ])
        template_message = TemplateSendMessage(
            alt_text='Carousel alt text', template=carousel_template)
        messages = [TextSendMessage(text="細かい質問は資産税課へ。（申請者区分に応じて必要書類がことなるので、資産税課に繋ぐ。あくまでも照明の種類と申請できる人と手数料までの案内。）"),
                    template_message]
        line_bot_api.reply_message(event.reply_token, messages)

    if user_text in ['固定資産評価・公果証明・名寄帳の写し']:
        reply_text = '申請できるのは1月1日時点の所有者または所有者の相続人'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect="資産税課")
        )

    if user_text in ['固定資産課税台帳記載事項証明']:
        reply_text = '申請できるのは、所有者、所有者の相続人、貸借人、管財人、訴訟提起者'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect="資産税課")
        )

    if user_text in ['公課証明']:
        reply_text = '申請できるのは競売申立人'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect="資産税課")
        )

    if user_text in ['現況証明・家屋滅失証明']:
        reply_text = '申請できるのは所有者'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect="資産税課")
        )

    if user_text in ['住宅用家屋証明']:
        reply_text = '申請できるのは所有者'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect="資産税課")
        )

    if user_text in ['地番図・航空写真']:
        reply_text = '申請できるのはどなたでも'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect="資産税課")
        )

    if user_text in ['評価額通知書']:
        reply_text = '申請できるのは法務局からの依頼書をお餅の方'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text, department_to_connect="資産税課")
        )


def inkan_flow(event, user_text):
    # q1
    if user_text in ['印鑑登録関連', '住所変更と同時に印鑑登録']:
        buttons_template = ButtonsTemplate(
            title='印鑑登録関連の何をお望みですか？', text='お選びください', actions=[
                MessageTemplateAction(label='印鑑登録証明書がほしい', text='印鑑登録証明書'),
                MessageTemplateAction(label='印鑑登録を廃止したい', text='印鑑登録を廃止したい'),
                MessageTemplateAction(label='印鑑登録をしたい', text='印鑑登録をしたい'),
            ])
        template_message = TemplateSendMessage(
            alt_text='印鑑登録関連の何をお望みですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['印鑑登録をしたい']:
        buttons_template = ButtonsTemplate(
            title='印鑑登録をしたいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text='印鑑登録をしたいのは本人'),
                MessageTemplateAction(label='本人＋保証人', text='印鑑登録をしたいのは本人＋保証人'),
                MessageTemplateAction(label='本人以外', text='印鑑登録をしたいのは本人以外'),
            ])
        template_message = TemplateSendMessage(
            alt_text='印鑑登録をしたいのはどなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['印鑑登録をしたいのは本人']:
        buttons_template = ButtonsTemplate(
            title='写真付き本人確認書類をお持ちですか？', text='お選びください', actions=[
                MessageTemplateAction(label='持っている', text='写真付き本人確認書類を持っている'),
                MessageTemplateAction(label='持っていない', text='写真付き本人確認書類を持っていない')
            ])
        template_message = TemplateSendMessage(
            alt_text='本人確認書類をお持ちですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['写真付き本人確認書類を持っている']:
        reply_text = '即日登録が可能。写真付き本人確認書類と、登録する印鑑が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['写真付き本人確認書類を持っていない']:
        reply_text = '証明交付係に繋ぐ。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['印鑑登録をしたいのは本人＋保証人']:
        reply_text = '証明交付係に繋ぐ。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['印鑑登録をしたいのは本人以外']:
        reply_text = '証明交付係に繋ぐ。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['印鑑登録証明書']:
        buttons_template = ButtonsTemplate(
            title='印鑑登録証明書をほしいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人がほしい', text='印鑑登録証明書を本人がほしい'),
                MessageTemplateAction(label='本人以外がほしい', text='印鑑登録証明書を本人以外がほしい'),
                MessageTemplateAction(label='印鑑登録証がない場合', text='印鑑登録証がない場合'),
            ])
        template_message = TemplateSendMessage(
            alt_text='印鑑登録証明書をほしいのはどなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['印鑑登録証明書を本人がほしい']:
        reply_text = '本人確認書類が、印鑑登録証が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['印鑑登録証明書を本人以外がほしい']:
        reply_text = '窓口に来た人の本人確認書類、印鑑登録証が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['印鑑登録証がない場合']:
        reply_text = '本人確認書類や実印をもってきても、申請できない。紛失してしまった場合、廃止届＋再登録を案内。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['印鑑登録を廃止したい']:
        buttons_template = ButtonsTemplate(
            title='印鑑登録を廃止したいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text='本人が印鑑登録を廃止したい'),
                MessageTemplateAction(label='本人以外', text='本人以外が印鑑登録を廃止したい')
            ])
        template_message = TemplateSendMessage(
            alt_text='印鑑登録を廃止したいのはどなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['本人が印鑑登録を廃止したい']:
        reply_text = '本人確認書類、印鑑登録証（紛失による廃止の場合不要）が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['本人以外が印鑑登録を廃止したい']:
        reply_text = '本人確認書類、印鑑登録証（紛失による廃止の場合不要）、委任状が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )


def kei_car_certificate_flow(event, user_text):
    if user_text in ['軽自動車用住所証明書がほしい', 'kei']:
        buttons_template = ButtonsTemplate(
            title='軽自動車用住所証明書がほしいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人がほしい', text='軽自動車用住所証明書を本人がほしい'),
                MessageTemplateAction(label='本人以外がほしい', text='軽自動車用住所証明書を本人以外がほしい')
            ])
        template_message = TemplateSendMessage(
            alt_text='軽自動車用住所証明書がほしい', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['軽自動車用住所証明書を本人がほしい']:
        reply_text = '本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['軽自動車用住所証明書を本人以外がほしい']:
        buttons_template = ButtonsTemplate(
            title='軽自動車用住所証明書をほしいのはどなたですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人と同一世帯の人', text='軽自動車用住所証明書を本人と同一世帯の人がほしい'),
                MessageTemplateAction(label='任意代理人', text='軽自動車用住所証明書を任意代理人がほしい'),
                MessageTemplateAction(label='自動車販売関係社社員', text='軽自動車用住所証明書を自動車販売関係会社の社員などがほしい'),
            ])
        template_message = TemplateSendMessage(
            alt_text='軽自動車用住所証明書をほしいのはどなたですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['軽自動車用住所証明書を本人と同一世帯の人がほしい']:
        reply_text = '窓口に来た人の本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['軽自動車用住所証明書を任意代理人がほしい']:
        reply_text = '委任状、窓口に来た人の本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['軽自動車用住所証明書を自動車販売関係会社の社員などがほしい']:
        reply_text = '軽自動車の売買契約書または注文書の写し、委任状、窓口に来た人の本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )


def juminhyou_flow(event, user_text):
    if user_text in ['住民票がほしい', 'jumin', '住所変更と同時に住民票の発行']:
        buttons_template = ButtonsTemplate(
            title='住民票がほしい方は本人ですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本人', text='本人が住民票をほしい'),
                MessageTemplateAction(label='本人以外', text='本人以外が住民票をほしい')
            ])
        template_message = TemplateSendMessage(
            alt_text='住民票がほしい', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['本人が住民票をほしい']:
        reply_text = '本人確認書類が必要です。記載事項証明の場合、提出先から提供された書式を使用することが可能です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['本人以外が住民票をほしい', 'jh']:
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(text='住民票をほしいのはどなたですか？', title='お選びください', actions=[
                MessageTemplateAction(label='本人と同一世帯の人', text='本人と同一世帯の人'),
                MessageTemplateAction(label='任意代理人', text='任意代理人'),
                MessageTemplateAction(label='法定代理人', text='法定代理人'),
            ]),
            CarouselColumn(text='住民票をほしいのはどなたですか？', title='お選びください', actions=[
                MessageTemplateAction(label='親族',
                                      text='親族（除票の申請で本人がすでに死亡しており、本人が単身世帯だったとき）'),
                MessageTemplateAction(label='債権者', text='債権者'),
                MessageTemplateAction(label='ダミー', text='このボタンはボタンの数を統一するためのダミーです。'),
            ]),
            CarouselColumn(text='住民票をほしいのはどなたですか？', title='お選びください', actions=[
                MessageTemplateAction(label='特定事務責任者', text='特定事務責任者（弁護士・司法書士など）'),
                MessageTemplateAction(label='国/公共地方団体職員', text='国・公共地方団体の機関の職員'),
                MessageTemplateAction(label='ダミー', text='このボタンはボタンの数を統一するためのダミーです。'),
            ]),
        ])
        template_message = TemplateSendMessage(
            alt_text='Carousel alt text', template=carousel_template)
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['本人と同一世帯の人']:
        reply_text = '窓口に来た人の本人確認書類が必要です。記載事項証明の場合、提出先から提供された書式を使用することが可能です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['任意代理人']:
        buttons_template = ButtonsTemplate(
            title='取得したい住民票などは「住基コードやマイナンバー」なし、あり？', text='お選びください', actions=[
                MessageTemplateAction(label='あり', text='「住基コードやマイナンバーなし」'),
                MessageTemplateAction(label='なし', text='「住基コードやマイナンバーあり」')
            ])
        template_message = TemplateSendMessage(
            alt_text='取得したい住民票などは「住基コードやマイナンバーなし」', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['「住基コードやマイナンバーなし」']:
        reply_text = '委任状、窓口に来た人の本人確認書類が必要です。記載事項証明の場合、提出先から提供された書式を使用することが可能です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['「住基コードやマイナンバーあり」']:
        reply_text = '委任状、窓口に来た人の本人確認書類が必要です。ただし、即日交付はできないため、後日申請者本人宛に簡易書留で送付されます。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['法定代理人']:
        buttons_template = ButtonsTemplate(
            title='親権者ですか？成年後見人ですか？', text='お選びください', actions=[
                MessageTemplateAction(label='親権者', text='親権者'),
                MessageTemplateAction(label='成年後見人', text='成年後見人')
            ])
        template_message = TemplateSendMessage(
            alt_text='親権者ですか？成年後見人ですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['親権者']:
        reply_text = '親権者であることの証明（戸籍謄本など。つくば市に本籍がある場合は不要。）窓口に来た人の本人確認書類が必要です。記載事項証明の場合、提出先から提供された書式を使用することが可能です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['成年後見人']:
        reply_text = '登記事項証明書、窓口に来た人の本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['親族（除票の申請で本人がすでに死亡しており、本人が単身世帯だったとき）']:
        reply_text = '親族であることの証明（戸籍謄本など。申請者の本籍がつくば市の場合は不要。）窓口に来た人の方の本人確認書類が必要です。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['債権者']:
        reply_text = '交付の可否についての即答厳禁。必要書類や審査などが存在するため、証明交付係に繋ぐ'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['特定事務責任者（弁護士・司法書士など）']:
        reply_text = '職務上請求用紙により身分証持参で申請可能。申請内容については証明交付係に繋ぐ。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['国・公共地方団体の機関の職員']:
        reply_text = '公用請求（無料）。証明交付係に繋ぐ。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )


def my_number_others_flow(event, user_text):
    # q1
    if user_text in ['マイナンバー関連', 'number']:
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(text='お選びください', title='マイナンバー関連', actions=[
                MessageTemplateAction(label='個人番号/通知カード紛失', text='マイナンバーカード・通知カードを紛失した'),
                MessageTemplateAction(label='マイナンバーを知りたい', text='マイナンバーを知りたい'),
                MessageTemplateAction(label='"支所"で可能かどうか', text='市役所が遠いから支所でマイナンバー手続きをしたい'),
            ]),
            CarouselColumn(text='お選びください', title='マイナンバー関連', actions=[
                MessageTemplateAction(label='マイナンバーがロック', text='コンビニで証明書を取得しようとしたがロック'),
                MessageTemplateAction(label='個人番号カードの受取予約', text='マイナンバーカードの受け取り予約をしたい'),
                MessageTemplateAction(label='ダミー', text='ダミー'),
            ]),
        ])
        template_message = TemplateSendMessage(
            alt_text='Carousel alt text', template=carousel_template)
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['far', '市役所が遠いから支所でマイナンバー手続きをしたい']:
        buttons_template = ButtonsTemplate(
            title='お客様がおっしゃっている支所とは、「窓口センター」or「出張所」？', text='お選びください', actions=[
                MessageTemplateAction(label='窓口センター', text='窓口センター'),
                MessageTemplateAction(label='出張所', text='出張所'),
            ])
        template_message = TemplateSendMessage(
            alt_text='default alt_text', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['出張所']:
        reply_text = 'マイナンバーの手続きは出張所ではできないことをお伝えして、近くの窓口センターを案内する'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['窓口センター']:
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(text='希望する手続きはなんですか？', title='お選びください', actions=[
                MessageTemplateAction(label='個人番号入り住民票', text='マイナンバー入りの住民の発行'),
                MessageTemplateAction(label='通知カードの再発行', text='通知カードの再発行'),
                MessageTemplateAction(label='写真付個人番号カード', text='写真付きマイナンバーカードは申込書の作成まで'),
            ]),
            CarouselColumn(text='希望する手続きはなんですか？', title='お選びください', actions=[
                MessageTemplateAction(label='通知カード返戻カード分の受取', text='通知カード返戻カード分の受け取り'),
                MessageTemplateAction(label='作成済み個人番号カードの受取', text='作成済みマイナンバーカードの受け取り'),
                MessageTemplateAction(label='ダミー', text='ダミー'),
            ]),
        ])
        template_message = TemplateSendMessage(
            alt_text='Carousel alt text', template=carousel_template)
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['マイナンバー入りの住民の発行']:
        reply_text = 'マイナンバーカードを急ぎで知りたいだけの場合、マイナンバー入りの住民票の発行をご案内。本人確認書類を持って、窓口センターへ。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['通知カードの再発行']:
        reply_text = '申請者本人が本人確認書類を持って窓口センターへ。家族分など自分自身ではない場合、「通知カードの再発行」を委任事項とした委任状と再発行する人の本人確認書類の原本も必要（５００円）'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['写真付きマイナンバーカードは申込書の作成まで']:
        reply_text = '申請書の作成までは窓口センターで可能。本人確認書類の原本が必要。自分でインターネット申請や郵送申請が必要になる。写真撮影まで無料で実施している窓口申請補助を本庁舎のみ。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['通知カード返戻カード分の受け取り']:
        reply_text = '返礼された通知カードの受け取り・確認を行う。氏名・生年月日をきき、該当者を検索。' \
                     '返戻がある場合、どこのセンターでの受け取りを希望を確認する。（職員による直接配送となるので配送可能日を確認し、）いつからお渡し可能かを案内し、' \
                     '本人確認書類を持って本人が該当のセンターに来庁するように伝える。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['作成済みマイナンバーカードの受け取り']:
        reply_text = '詳細は個人番号カード係へ繋ぐ。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )

    if user_text in ['コンビニで証明書を取得しようとしたがロック']:
        reply_text = '本人確認書類とマイナンバーカードをもって、市役所または窓口センターで暗証番号の初期化をすることでロック解除できることを案内。' \
                     '（代理人の場合、照会になるのでHPを確認するよう案内。詳細は、個人番号カードかかりへ繋ぐ。）'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['マイナンバーカードの受け取り予約をしたい']:
        messages = [TextSendMessage(text='平日の本庁舎希望の場合、予約不要。')]

        buttons_template = ButtonsTemplate(
            title='土日の本庁舎or平日の窓口センター？', text='お選びください', actions=[
                MessageTemplateAction(label='土日の本庁舎', text='土日の本庁舎'),
                MessageTemplateAction(label='平日の窓口センター', text='平日の窓口センター'),
            ])
        template_message = TemplateSendMessage(
            alt_text='default alt_text', template=buttons_template
        )
        messages.append(template_message)

        line_bot_api.reply_message(event.reply_token, messages)
    if user_text in ['土日の本庁舎']:
        reply_text = '今月・来月の予約可能日を案内。予約をする場合は、予約簿を用意し、氏名・生年月日・住所・電話番号を予約簿に書き込む。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['平日の窓口センター']:
        reply_text = '今月の空き状況を説明。予約をする場合は、予約簿を用意し、氏名・生年月日・住所・電話番号を予約簿に書き込む。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )


def my_number_make_flow(event, user_text):
    if user_text in ['マイナンバーを知りたい', 'make']:
        buttons_template = ButtonsTemplate(
            title='１ヶ月以内に必要ですか？', text='お選びください', actions=[
                MessageTemplateAction(label='必要です。', text='必要です。'),
                MessageTemplateAction(label='必要ではないです。', text='必要ではないです。'),
            ])
        template_message = TemplateSendMessage(
            alt_text='１ヶ月以内に必要ですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['必要です。']:
        reply_text = 'マイナンバー入り住民票を案内。本人確認書類を持って、市役所もしくは窓口センターへ。土日も手続き可能。別途カードを作りたい場合、要通知カードor写真入りマイナンバーカード。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['必要ではないです。']:
        buttons_template = ButtonsTemplate(
            title='通知カードと写真入り？', text='お選びください', actions=[
                MessageTemplateAction(label='通知カード', text='通知カードがほしい'),
                MessageTemplateAction(label='個人番号カード', text='マイナンバーカードがほしい'),
            ])
        template_message = TemplateSendMessage(
            alt_text='通知カードor写真入りマイナンバーカード？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['通知カードがほしい']:
        buttons_template = ButtonsTemplate(
            title='通知カードを受け取ったことはございますか？', text='お選びください', actions=[
                MessageTemplateAction(label='受け取ったことがない', text='通知カードを受け取ったことがない'),
                MessageTemplateAction(label='自宅でなくした', text='通知カードを自宅でなくした'),
                MessageTemplateAction(label='自宅外・盗難で紛失', text='通知カードを自宅外または盗難でなくした'),
            ])
        template_message = TemplateSendMessage(
            alt_text='通知カードを受け取ったことはございますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['通知カードを受け取ったことがない']:
        reply_text = '個人番号カード係へつなぐ。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['マイナンバーカードがほしい']:
        buttons_template = ButtonsTemplate(
            title='マイナンバーカードを作るのは初めてですか？', text='お選びください', actions=[
                MessageTemplateAction(label='初めてである', text='初めてである'),
                MessageTemplateAction(label='2回目以降である', text='2回目以降である')
            ])
        template_message = TemplateSendMessage(
            alt_text='マイナンバーカードを作るのは初めてですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['初めてである']:
        buttons_template = ButtonsTemplate(
            title='本庁舎への来庁は可能ですか？',
            text='お選びください', actions=[
                MessageTemplateAction(label='本庁舎へ来庁可能', text='本庁舎へ来庁可能'),
                MessageTemplateAction(label='本庁舎へ来庁不可', text='本庁舎へ来庁不可'),
            ])
        template_message = TemplateSendMessage(
            alt_text='本庁舎への来庁は可能ですか？（通知カードに付属する申請書が使える場合もあるが、住所移動や修正などでIDが出回っている場合もあることを考えると最新のIDの取得をしていただいたほうが確実。）',
            template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['2回目以降である']:
        buttons_template = ButtonsTemplate(
            title='なくしたのはどこですか？', text='お選びください', actions=[
                MessageTemplateAction(label='自宅', text='自宅でマインバーカードを紛失した'),
                MessageTemplateAction(label='自宅外または盗難', text='自宅外または盗難でマイナンバーカードを紛失した'),
            ])
        template_message = TemplateSendMessage(
            alt_text='default alt_text', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['自宅でマインバーカードを紛失した']:
        buttons_template = ButtonsTemplate(
            title='写真付きマイナンバーカード(800円)or 通知カード(500円)？', text='お選びください', actions=[
                MessageTemplateAction(label='マイナンバーカード', text='マイナンバーカードを再発行したい'),
                MessageTemplateAction(label='通知カード', text='通知カードを再発行したい'),
            ])
        template_message = TemplateSendMessage(
            alt_text='default alt_text', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['自宅外または盗難でマイナンバーカードを紛失した']:
        buttons_template = ButtonsTemplate(
            title='マイナンバーの変更を希望しますか？', text='お選びください', actions=[
                MessageTemplateAction(label='変更を希望する', text='マイナンバーの変更を希望する'),
                MessageTemplateAction(label='変更を希望しない', text='マイナンバーの変更を希望しない'),
            ])
        template_message = TemplateSendMessage(
            alt_text='default alt_text', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['通知カードを再発行したい']:
        # 箱をわける
        reply_text = '''個人番号カードの廃止のため、本人確認書類を持って、来庁頂く必要があることをご案内。

通知カード再交付のご案内。再交付手数料１通に付き５００円、本人が本人確認書類を持って、市役所または窓口センターに来庁。'''

        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['マイナンバーカードを再発行したい']:
        reply_text = '個人番号カード係へつなぐ。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    # １枚めスライドのマイナンバー紛失フローと２枚めスライド右下あたりのフローが微妙に違うのはなぜか？
    # ※３と※４はなにか？


def my_number_lost_flow(event, user_text):
    # My number flow lost flow
    if user_text in ['lost', 'マイナンバーカード・通知カードを紛失した']:
        buttons_template = ButtonsTemplate(
            title='なくしたのは通知カード or 個人番号カード？', text='お選びください。', actions=[
                MessageTemplateAction(label='通知カード', text='通知カード'),
                MessageTemplateAction(label='個人番号カード', text='個人番号カードを紛失'),
            ])
        template_message = TemplateSendMessage(
            alt_text='なくしたのは通知カード or 個人番号カード？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    # My number flow answers(1)
    if user_text in ['通知カード']:
        buttons_template = ButtonsTemplate(
            title='なくしたのはどこですか？', text='お選びください', actions=[
                MessageTemplateAction(label='自宅でなくした', text='通知カードを自宅でなくした'),
                MessageTemplateAction(label='自宅外・盗難', text='通知カードを自宅外または盗難でなくした'),
                MessageTemplateAction(label='急ぎで必要', text='通知カードが急ぎで必要'),
            ])
        template_message = TemplateSendMessage(
            alt_text='なくしたのはどこですか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    # My number flow answers(1, 1) and 1,2,2
    if user_text in ['通知カードを自宅でなくした', 'マイナンバーの変更を希望しない']:
        buttons_template = ButtonsTemplate(
            title='どちらで作り直しますか？', text='お選びください', actions=[
                MessageTemplateAction(label='通知カードで', text='通知カードで作り直す'),
                MessageTemplateAction(label='マイナンバーカードで', text='マイナンバーカードで作り直す'),
            ])
        template_message = TemplateSendMessage(
            alt_text='どちらで作り直しますか', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    # My number flow answers(1, 2)
    if user_text in ['通知カードを自宅外または盗難でなくした']:
        buttons_template = ButtonsTemplate(
            title='マイナンバーの変更を希望するか否か', text='お選びください', actions=[
                MessageTemplateAction(label='希望する', text='マイナンバーの変更を希望する'),
                MessageTemplateAction(label='希望しない', text='マイナンバーの変更を希望しない'),
            ])
        template_message = TemplateSendMessage(
            alt_text='どちらで作り直しますか', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    # My number flow answers(1, 3)
    if user_text in ['通知カードが急ぎで必要']:
        reply_text = 'マイナンバー入りの住民票を案内。\n本人確認書類を持って、市役所または窓口へ。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    # My number flow 1,1,1
    if user_text in ['通知カードで作り直す']:
        reply_text = '通知カード再交付のご案内。再交付手数料１通に付き５００円、本人が本人確認書類を持って、市役所または窓口センターに来庁。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    # My number flow 1,1,2
    if user_text in ['マイナンバーカードで作り直す']:
        buttons_template = ButtonsTemplate(
            title='本庁舎へ来庁可能ですか？', text='お選びください', actions=[
                MessageTemplateAction(label='本庁舎へ来庁可能', text='本庁舎へ来庁可能'),
                MessageTemplateAction(label='本庁舎へ来庁不可', text='本庁舎へ来庁不可'),
            ])
        template_message = TemplateSendMessage(
            alt_text='本庁舎へ来庁可能ですか', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    # My number flow 1,2,1
    if user_text in ['マイナンバーの変更を希望する']:
        reply_text = '警察でどういった状況でなくしたのかを説明し、受理番号をもらい本人確認書類を持参し来庁。番号変更の手続きをして新しいマイナンバーで通知カードが送付される。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    # My number flow 1,2,1
    if user_text in ['本庁舎へ来庁可能']:
        reply_text = '申請補助を案内。本人確認書類をもって、平日本庁舎へ。その場で写真を取り申請。１ヶ月程度で自宅にカード受け取りのお知らせが届くので、また受け取りに来てくださいと案内。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['本庁舎へ来庁不可']:
        reply_text = '窓口センターの受付で「個人番号カード申請のための申込書がほしい」とお話して、申請書を作成した後、自分自身で写真を貼って郵送するか、インターネット申請をするように案内。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    # My number flow answers(2)
    if user_text in ['個人番号カードを紛失']:
        buttons_template = ButtonsTemplate(
            title='どこでなくされましたか？', text='お選びください', actions=[
                MessageTemplateAction(label='自宅', text='自宅でマイナンバーカードを紛失'),
                MessageTemplateAction(label='自宅外、または盗難', text='自宅外または盗難でマイナンバーカードを紛失'),
            ])
        template_message = TemplateSendMessage(
            alt_text='どこでなくされましたか', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['自宅でマイナンバーカードを紛失']:
        buttons_template = ButtonsTemplate(
            title='通知カードとマイナンバーカード、どちらを再交付されますか？', text='お選びください', actions=[
                MessageTemplateAction(label='通知カード', text='通知カードを再交付したい'),
                MessageTemplateAction(label='マイナンバーカード', text='マイナンバーカードを再交付したい'),
            ])
        template_message = TemplateSendMessage(
            alt_text='通知カードとマイナンバーカード、どちらを再交付されますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['通知カードを再交付したい']:
        reply_text = 'カード廃止の手続き後、通知カード再発行の手続きを行う。本人確認書類を持って、本人が来庁するように説明。窓口センターでも可能。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['マイナンバーカードを再交付したい']:
        reply_text = '個人番号カードの申請についてのご案内。電子証明書の一時停止のため、' \
                     'コールセンターの電話番号をお伝えする。カード廃止の手続きは、カード交付の際に実施する旨を説明。本庁舎へ来庁可能であれば、窓口申請補助について案内する。（開発者意見：本庁舎へ来れない場合は？）'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['自宅外または盗難でマイナンバーカードを紛失']:
        buttons_template = ButtonsTemplate(
            title='個人番号の変更を希望されますか？', text='お選びください', actions=[
                MessageTemplateAction(label='変更を希望する', text='マイナンバーカードを自宅外または盗難で紛失したので、番号を変えた上で再交付したい。'),
                MessageTemplateAction(label='変更を希望しない', text='マイナンバーカードを自宅外または盗難で紛失したので、番号をそのままに再交付したい。'),
            ])
        template_message = TemplateSendMessage(
            alt_text='個人番号の変更を希望されますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    if user_text in ['マイナンバーカードを自宅外または盗難で紛失したので、番号を変えた上で再交付したい。']:
        reply_text = '警察でどういった状況でなくしたのかを説明し、受理番号をもらい本人確認書類を持参し来庁。個人番号カード廃止処理後、番号変更の手続きをして新しいマイナンバーで通知カードが送付される。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['マイナンバーカードを自宅外または盗難で紛失したので、番号をそのままに再交付したい。']:
        buttons_template = ButtonsTemplate(
            title='通知カードとマイナンバーカードのどちらで再交付されますか？', text='お選びください', actions=[
                MessageTemplateAction(label='通知カード', text='自宅外または盗難でマイナンバーカードを紛失したので、番号そのままに通知カードを発行したい'),
                MessageTemplateAction(label='マイナンバーカード', text='自宅外または盗難でマイナンバーカードを紛失したので、番号そのままにマイナンバーカードを再発行したい。'),
            ])
        template_message = TemplateSendMessage(
            alt_text='通知カードとマイナンバーカードのどちらで再交付されますか？', template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    if user_text in ['自宅外または盗難でマイナンバーカードを紛失したので、番号そのままに通知カードを発行したい']:
        reply_text = '個人番号カード廃止の手続き後、通知カード再発行の手続きを行う、本人確認書類を持って、本人が来庁するように説明。窓口センターでも可能。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )
    if user_text in ['自宅外または盗難でマイナンバーカードを紛失したので、番号そのままにマイナンバーカードを再発行したい。']:
        reply_text = '個人番号カードの最新性についてのご案内、' \
                     '電子証明書の一時停止のため、コールセンターの電話番号をお伝えする。カード廃止の手続きはカード交付の際に実施する旨を説明。本庁舎へ来庁可能であれば、窓口補助について案内する。'
        line_bot_api.reply_message(
            event.reply_token,
            get_text_send_messages(event, reply_text)
        )


def get_text_send_messages(event, reply_text, **kwargs):
    messages = [TextSendMessage(text=reply_text)]

    if '本人確認書類' in reply_text:
        messages.append(get_text_template_for_id())

    if '委任状' in reply_text:
        messages.append(get_text_template_for_delegate())

    if "department_to_connect" in kwargs.keys():
        messages.append(
            TextSendMessage(text=f'これ以上の質問は{kwargs["department_to_connect"]}につないでください。')
        )

    return messages


def add_message_to_connect_other_department(reply_text):
    messages = [TextSendMessage(text=reply_text), TextSendMessage(text=f"これ以上の質問は、{reply_text}につないでください。")]
    return messages


@handler.add(PostbackEvent)
def handle_postback(event):
    data_str = event.postback.data
    # data_dict = dict(urlparse.parse_qsl(data_str))
    user_id = event.source.user_id

    if "cancel" in data_str:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="キャンセルします。 Going back to default menu.")
        )

        rms = line_bot_api.get_rich_menu_list()
        menu_init_rm = [rm for rm in rms if rm.name == "menu_init"][0]
        latest_menu_init_id = menu_init_rm.rich_menu_id
        line_bot_api.link_rich_menu_to_user(user_id, latest_menu_init_id)

        sample_data = Sample.query \
            .filter((Sample.user_id == event.source.user_id)) \
            .order_by(db.desc(Sample.start_datetime)).first()

        sample_data.state = data_str
        sample_data.end_datetime = datetime.datetime.now()
        db.session.commit()

    if re.match('q\d=\d', data_str):

        sample_id = Sample.query \
            .filter((Sample.user_id == event.source.user_id)) \
            .order_by(db.desc(Sample.start_datetime)).first().id

        question_number = data_str[1]
        rms = line_bot_api.get_rich_menu_list()

        if int(question_number) != total_question_counts:
            menu_init_rm = [rm for rm in rms if rm.name == 'q' + str(int(question_number) + 1)][0]
            latest_menu_init_id = menu_init_rm.rich_menu_id
            line_bot_api.link_rich_menu_to_user(user_id, latest_menu_init_id)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"Sample {sample_id}:{data_str}. 次の質問に移ります.")
            )

        elif int(question_number) == total_question_counts:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"{data_str}.\n\nご回答、ご協力ありがとうございました!!")
            )

            rms = line_bot_api.get_rich_menu_list()
            menu_init_rm = [rm for rm in rms if rm.name == "menu_init"][0]
            latest_menu_init_id = menu_init_rm.rich_menu_id
            line_bot_api.link_rich_menu_to_user(user_id, latest_menu_init_id)

        data = Survey(
            sample_id,
            event.source.user_id,
            int(question_number),
            data_str[-1]
        )
        db.session.add(data)
        db.session.commit()

    # back_to_q1
    if "back" in data_str:
        question_number = data_str[-1]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{data_str}. 前の質問に戻ります。もう一度選択してください。")
        )
        rms = line_bot_api.get_rich_menu_list()
        menu_init_rm = [rm for rm in rms if rm.name == 'q' + str(int(question_number))][0]
        latest_menu_init_id = menu_init_rm.rich_menu_id
        line_bot_api.link_rich_menu_to_user(user_id, latest_menu_init_id)


@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        LocationSendMessage(
            title=event.message.title, address=event.message.address,
            latitude=event.message.latitude, longitude=event.message.longitude
        )
    )


@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        StickerSendMessage(
            package_id=event.message.package_id,
            sticker_id=event.message.sticker_id)
    )


@handler.add(FollowEvent)
def handle_follow(event):

    rms = line_bot_api.get_rich_menu_list()
    menu_init_rm = [rm for rm in rms if rm.name == "menu_init"][0]
    latest_menu_init_id = menu_init_rm.rich_menu_id

    user_id = event.source.user_id
    try:
        richmenu_id_applied = line_bot_api.get_rich_menu_id_of_user(user_id)

    except LineBotApiError:
        richmenu_id_applied = "no rich menu"
        pass

    if richmenu_id_applied != latest_menu_init_id:
        line_bot_api.link_rich_menu_to_user(user_id, latest_menu_init_id)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='つくば市役所botを友達登録していただきありがとうございます！'
                             '\n\n下の『問い合わせ分類』から選択肢をお選びください。')
    )


def push_summary():

    start_logs = Sample.query \
        .filter((Sample.start_datetime >= datetime.datetime.now() - datetime.timedelta(days=4))).all()

    diffs = [(start_log.end_datetime - start_log.start_datetime).total_seconds() for start_log in start_logs]
    print(diffs)
    average = round(numpy.average(diffs), 1)
    print(average)

    # url = get_chart_url([60, 120, 100])

    url = get_chart_url([int(x) for x in diffs])
    print(url)
    url = "https://i.imgur.com/LCGM2TQ.png"
    line_bot_api.push_message(
        "U0a028f903127e2178bd789b4b4046ba7",
        [TextSendMessage(text=f'本日の平均対応時間は、{average}でした。'),
         ImageSendMessage(original_content_url=url, preview_image_url=url)]
    )


def get_chart_url(data):

    data_str_list = [str(x) for x in data]
    data_str_joined = ",".join(data_str_list)
    print(data_str_joined)
    base_url = "https://chart.apis.google.com/chart?"
    return base_url + f"chs=240x240&chd=t:{data_str_joined}|30,23,73,24,87&" \
                      f"cht=bvg&chco=00ff00,0000ff&chxt=x,y&chxr=0,1,5|1,0,200&chxp=1,0,30,60,90,120,150,180,210" \
                      f"&chtt=fsda&chdl=CB|CB"


add_multimedia_event_handler()

add_group_event_handler()


if __name__ == "__main__":
    sc = BackgroundScheduler()
    sc.add_job(push_summary, 'cron', day_of_week='mon-fri', hour=5, minute=10)
    sc.print_jobs()
    sc.start()

    port = int(os.environ.get('PORT', 8000))
    print(port)
    app.run(debug=True, port=port, host='0.0.0.0')



