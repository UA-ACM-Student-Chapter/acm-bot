import json
import os
import random
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
  log('Recieved {}'.format(data))
  event = data['event']
  if (event.get('type') == 'message' and event.get('username') != bot_name):
    send_slack_message(event['channel'], "Hello")
  return "ok", 200


# Simple wrapper for sending a Slack message
def send_slack_message(channel, message):
  return sc.api_call(
    "chat.postMessage",
    channel=channel,
    text=message
  )

# Debug
def log(msg):
  print(str(msg))
  sys.stdout.flush()
