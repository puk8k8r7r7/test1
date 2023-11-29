from flask import Flask, request, abort, render_template
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import TextSendMessage, MessageEvent, TextMessage
import os
import json
import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

app = Flask(__name__)
static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

# Line Bot
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# Google Calendar API 设置
SCOPES = ['https://www.googleapis.com/auth/calendar']
creds = None

if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json')

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)

    with open('token.json', 'w') as token:
        token.write(creds.to_json())

service = build('calendar', 'v3', credentials=creds)

# Line Notify 设置
LINE_NOTIFY_TOKEN = 'your_line_notify_token'  # 替换为你的 Line Notify token

# Line Notify 函数
def line_notify_message(msg):
    line_notify_api = 'https://notify-api.line.me/api/notify'
    headers = {'Authorization': 'Bearer ' + LINE_NOTIFY_TOKEN}
    payload = {'message': msg}
    requests.post(line_notify_api, headers=headers, data=payload)

# Callback 路由
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 处理文字消息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    GPT_answer = GPT_response(msg)

    # 创建日历事件
    create_calendar_event("Event Title", "Event Description", datetime.now() + timedelta(days=1))

    # 发送 Line Notify 通知
    send_line_notify("Event Reminder: Tomorrow is the event!")

    line_bot_api.reply_message(event.reply_token, TextSendMessage(GPT_answer))

# 创建日历事件函数
def create_calendar_event(title, description, start_time):
    event = {
        'summary': title,
        'description': description,
        'start': {
            'dateTime': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'timeZone': 'Asia/Taipei',
        },
        'end': {
            'dateTime': (start_time + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S'),
            'timeZone': 'Asia/Taipei',
        },
    }

    calendar_id = 'primary'  # 可使用 'primary' 作为默认日历
    service.events().insert(calendarId=calendar_id, body=event).execute()

# 发送 Line Notify 通知函数
def send_line_notify(message):
    line_notify_api = 'https://notify-api.line.me/api/notify'
    headers = {'Authorization': 'Bearer ' + LINE_NOTIFY_TOKEN}
    payload = {'message': message}
    requests.post(line_notify_api, headers=headers, data=payload)

# 处理 Postback 事件
@handler.add(PostbackEvent)
def handle_postback(event):
    print(event.postback.data)

# 处理 MemberJoined 事件
@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name
    message = TextSendMessage(text=f'{name}欢迎加入')
    line_bot_api.reply_message(event.reply_token, message)

# GPT 响应函数
def GPT_response(text):
    response = openai.Completion.create(model="text-davinci-003", prompt=text, temperature=0.5, max_tokens=500)
    answer = response['choices'][0]['text'].replace('
