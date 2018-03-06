import json
import os
import random
import requests
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Flask, request
from slackclient import SlackClient

app = Flask(__name__)
slack_token = os.environ["SLACK_BOT_TOKEN"]
bot_name = os.environ["BOT_NAME"]
sc = SlackClient(slack_token)

# Webhook for all requests
@app.route('/', methods=['POST'])
def webhook():
  data = request.get_json()
  log('Received {}'.format(data))
  event = data['event']
  flag = True
  if 'subtype' in event:
    flag = event['subtype'] not in ['bot_message', 'message_changed']
  if event['type'] == 'message' and flag:
    text = str(event.get('text')).lower()
    if 'shirt' in text or 'size' in text:
      update_shirt_prompt(event['channel'])
    else if 'paid' in text:
      send_slack_message(event['channel'], has_paid(event['user']))
    else:
      send_slack_message(event['channel'], "Hello")
  return "ok", 200

# Listener for updating shirt size in database
@app.route('/update_shirt', methods=['POST'])
def update_shirt():
  # get shirt size and username
  payload = json.loads(request.form.get("payload"))
  log('Received {}'.format(payload))
  size = str(payload["actions"][0].get("value"))
  userid = payload["user"]["id"]
  email = get_email(userid)

  # actually update shirt size and return the result
  requests.post(os.environ["API_URL"] + "/member/updateshirtsize", data={"email": email, "newShirtSize": size.upper()})
  return "Updated t-shirt size to *" + size.upper() + "*, congratulations " + email + "!", 200

# Simple wrapper for sending a Slack message
def send_slack_message(channel, message):
  return sc.api_call(
    "chat.postMessage",
    channel=channel,
    text=message
  )

# Button-based input for asking shirt size
def update_shirt_prompt(channel):
  return sc.api_call(
    "chat.postMessage",
    channel=channel,
    attachments=[
    {
      "title": "What's your t-shirt size?",
      "fallback": "You are unable to choose a t-shirt size",
      "callback_id": "update_tshirt",
      "color": "#3AA3E3",
      "attachment_type": "default",
      "actions": [
          {
            "name": "size",
            "text": "XS",
            "type": "button",
            "value": "xs"
          },
          {
            "name": "size",
            "text": "S",
            "type": "button",
            "value": "s"
          },
          {
            "name": "size",
            "text": "M",
            "type": "button",
            "value": "m"
          },
          {
            "name": "size",
            "text": "L",
            "type": "button",
            "value": "l"
          },
          {
            "name": "size",
            "text": "XL",
            "type": "button",
            "value": "xl"
          },
          {
            "name": "size",
            "text": "XXL",
            "type": "button",
            "value": "xxl"
          }
        ]
      }
    ]
  )

# Returns the email address for a user iD
def get_email(id):
  userlist = sc.api_call("users.list")
  for member in userlist["members"]:
    if member["id"] == id:
      return member["profile"]["email"] 
  return "failure@you"

# TODO: add hasPaid functionality
def has_paid(id):
  email = get_email(id)
  paid = requests.post(os.environ["API_URL"] + "/member/ispaid", data={"email": email})
  return paid

# TODO: add reminders functionality

# Debug
def log(msg):
  print(str(msg))
  sys.stdout.flush()
