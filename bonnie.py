import os
import requests
from ast import literal_eval
import json
from flask import Flask, request, jsonify, render_template
from flask_httpauth import HTTPBasicAuth
import heroku3
from twilio.rest import Client
from database import get_connection, release_connection

app = Flask(__name__)
auth = HTTPBasicAuth()
# Twilio Account SID and Auth Token
twilio_account_sid = os.environ['TWILIO_ACCOUNT_SID']
twilio_auth_token = os.environ['TWILIO_AUTH_TOKEN']

# Twilio phone number
twilio_phone_number = os.environ['TWILIO_PHONE_NUMBER']

# OpenAI API key from Heroku env
openai_api_key = os.environ['openai_api_key']

def get_user_status(phone_number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM user_statuses WHERE phone_number = %s", (phone_number,))
    row = cur.fetchone()
    release_connection(conn)
    return row[0] if row else None

def set_user_status(phone_number, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO user_statuses (phone_number, status) VALUES (%s, %s) ON CONFLICT (phone_number) DO UPDATE SET status = %s", (phone_number, status, status))
    conn.commit()
    release_connection(conn)

@app.route('/a', methods=['POST'])
def webhook():
    incoming_msg = request.form.get('Body')
    sender = request.form.get('From')
    user_status = get_user_status(sender)
    invalid_starts = ["Loved “", "Liked “", "Disliked “", "Laughed “", "Emphasized “", "Questioned “"]
    if any(incoming_msg.startswith(phrase) for phrase in invalid_starts):
            return jsonify({'error': 'Just a reaction'}), 469
    if incoming_msg.strip().lower() in ('start', 'unstop'):
        return jsonify({'error': 'default Twilio terms'}), 420
    else:
        if user_status is None:
            if incoming_msg.strip().lower() == 'agree':
                reply(sender,"Thanks for agreeing! What can I help you with? -Bonnie")
                set_user_status(sender, 'active')
                return jsonify({'success': True}), 201
            else:
                reply(sender,"Bonnie here! Before we continue, reply AGREE to acknowledge our T&C (hyperlink) to start chatting. -Bonnie")
                return jsonify({'success': True}), 202
        else:
            conversation_history = fetch_conversation_history(sender)
            response_text = generate_response(incoming_msg, conversation_history)
            reply(sender, response_text)

            return jsonify({'success': True}), 200

def generate_response(text,conversation_history):
    system_message = {
    "role": "system",
    "content": "You're Bonnie, the AI companion of SuperBonsai world. Avoid responses that are violent, hateful, sexual, dangerous, and avoid harmful bias and controversy. Use Gen-Z language and tone. Ensure responses under 100 tokens."
    }
    user_message = {"role": "user", "content": text}
    messages = [system_message] + conversation_history + [user_message]
    response = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={'Content-Type': 'application/json', 
                'Authorization': f'Bearer {openai_api_key}'},
        json={
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 100
        }
    )
    print(f"API response: {response.json()}")
    response_text = response.json()['choices'][0]['message']['content']
    return response_text + " -Bonnie"

def reply(sender,response_text):
    twilio_client = Client(twilio_account_sid, twilio_auth_token)
    twilio_client.messages.create(
        body=response_text,
        from_=twilio_phone_number,
        to=sender
    )

def fetch_conversation_history(sender):
    twilio_client = Client(twilio_account_sid, twilio_auth_token)
    messages = twilio_client.messages.list(
        to=twilio_phone_number, from_=sender, limit=5
    )
    conversation_history = []
    for message in messages[::-1]:  # Reverse the order of messages, as they are returned in reverse chronological order
        if message.direction == "inbound":
            role = "user"
        else:
            role = "assistant"
        conversation_history.append({"role": role, "content": message.body})

    return conversation_history

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

# Receive a payload from Postscript when they text "Bonnie" and reply with a text from our Twilio number
@app.route('/postscript', methods=['POST'])
def send_AI():
    # Get the raw data of the request body as bytes and decode to string
    raw_data = request.data
    body = raw_data.decode('utf-8')

    # Print the body to the console
    print(f"Received request: {body}")

    # Parse the string into a Python data structure (in this case, a dictionary)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        try:
            payload = literal_eval(body)
        except ValueError as e:
            print(f"ValueError when parsing as literal: {e}")
            payload = {}
    phone_number = payload.get('phone_number')
    print(phone_number)
    AI_TC = 'Hi, I’m Bonnie! Before we can talk, you must read over the SuperBonsai Terms and Conditions (https://superbonsai.com/pages/ai-tos). Reply with ‘AGREE’, to accept the terms and conditions.\nLook forward to chatting! '
    twilio_client = Client(twilio_account_sid, twilio_auth_token)
    twilio_client.messages.create(
        body=AI_TC,
        from_=twilio_phone_number,
        to=phone_number
    )
    print (AI_TC)
    return jsonify({'success': True}), 200

@app.route('/logs')
@auth.login_required
def display_logs():
    heroku_api_key = os.environ['HEROKU_API_KEY']
    heroku_app_name = os.environ['HEROKU_APP_NAME']

    heroku_conn = heroku3.from_key(heroku_api_key)
    app = heroku_conn.apps()[heroku_app_name]

    logs = app.get_log(lines=100)  # Retrieve the last 100 log lines

    return render_template('logs.html', logs=logs)

def verify_password(username, password):
    # Replace these values with your desired username and password
    if password == "cock" and username=="big":
        return True
    return False

@auth.verify_password
def verify_password_decorator(username, password):
    return verify_password(username, password)