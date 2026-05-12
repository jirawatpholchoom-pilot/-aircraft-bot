import os
import google.generativeai as genai
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
import json

app = Flask(__name__)

configuration = Configuration(
    access_token=os.environ['LINE_CHANNEL_ACCESS_TOKEN']
)
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])

genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel('gemini-1.5-flash')

def get_aircraft_info(aircraft_name):
    response = model.generate_content(f"""ให้ข้อมูลเครื่องบิน "{aircraft_name}" เป็นภาษาไทย ในรูปแบบ JSON ดังนี้:
{{
  "name": "ชื่อเต็มรุ่น",
  "manufacturer": "ผู้ผลิต",
  "type": "ประเภท",
  "first_flight": "ปีที่บินครั้งแรก",
  "specs": {{
    "length": "ความยาว (เมตร)",
    "wingspan": "ช่วงปีก (เมตร)",
    "max_speed": "ความเร็วสูงสุด (กม./ชม.)",
    "range": "พิสัยบิน (กม.)",
    "ceiling": "เพดานบิน (ฟุต)",
    "engines": "จำนวนและชนิดเครื่องยนต์"
  }},
  "capacity": {{
    "passengers": "จำนวนผู้โดยสาร",
    "cargo": "น้ำหนักบรรทุก (ตัน)"
  }},
  "description": "คำอธิบายสั้นๆ 2-3 ประโยค",
  "image_search": "คำค้นหารูปภาพภาษาอังกฤษ",
  "found": true
}}
ตอบเฉพาะ JSON เท่านั้น ไม่ต้องมี markdown""")
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)

def create_flex_message(info):
    image_url = f"https://source.unsplash.com/800x400/?{info['image_search'].replace(' ', '+')},aircraft"
    flex_content = {
        "type": "bubble",
        "size": "giga",
        "hero": {
            "type": "image",
            "url": image_url,
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover"
        },
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a237e",
            "contents": [
                {"type": "text", "text": "✈️ " + info['name'], "color": "#ffffff", "size": "lg", "weight": "bold", "wrap": True},
                {"type": "text", "text": info['manufacturer'] + " | " + info['type'], "color": "#90caf9", "size": "sm"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": info['description'], "wrap": True, "size": "sm", "color": "#555555"},
                {"type": "separator"},
                {"type": "text", "text": "📐 สมรรถนะ", "weight": "bold", "size": "md", "color": "#1a237e"},
                *[{"type": "box", "layout": "horizontal", "contents": [
                    {"type": "text", "text": label, "size": "sm", "color": "#888888", "flex": 3},
                    {"type": "text", "text": value, "size": "sm", "weight": "bold", "flex": 4, "wrap": True}
                ]} for label, value in [
                    ("ความยาว", info['specs']['length']),
                    ("ช่วงปีก", info['specs']['wingspan']),
                    ("ความเร็วสูงสุด", info['specs']['max_speed']),
                    ("พิสัยบิน", info['specs']['range']),
                    ("เพดานบิน", info['specs']['ceiling']),
                    ("เครื่องยนต์", info['specs']['engines']),
                ]],
                {"type": "separator"},
                {"type": "text", "text": "📦 ความจุ", "weight": "bold", "size": "md", "color": "#1a237e"},
                *[{"type": "box", "layout": "horizontal", "contents": [
                    {"type": "text", "text": label, "size": "sm", "color": "#888888", "flex": 3},
                    {"type": "text", "text": value, "size": "sm", "weight": "bold", "flex": 4}
                ]} for label, value in [
                    ("ผู้โดยสาร", info['capacity']['passengers']),
                    ("บรรทุกสินค้า", info['capacity']['cargo']),
                ]],
                {"type": "separator"},
                {"type": "text", "text": "🗓️ บินครั้งแรก: " + info['first_flight'], "size": "sm", "color": "#666666"}
            ]
        }
    }
    return FlexMessage(
        alt_text=f"ข้อมูลเครื่องบิน {info['name']}",
        contents=FlexContainer.from_dict(flex_content)
    )

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        try:
            info = get_aircraft_info(user_text)
            flex_msg = create_flex_message(info)
            line_bot_api.reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=[flex_msg])
            )
        except Exception as e:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="⚠️ เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง")]
                )
            )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
