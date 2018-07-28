import json
import os
import random
import requests
import sys
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Flask, request
from slackclient import SlackClient

app = Flask(__name__)
slack_token = os.environ["SLACK_BOT_TOKEN"]
bot_name = os.environ["BOT_NAME"]
api_url = os.environ["API_URL"]
secret_key = os.environ["SECRET_KEY"]
sc = SlackClient(slack_token)

# Webhook for all requests
@app.route("/", methods=["POST"])
def webhook():
  data = request.get_json()
  log("Received {}".format(data))
  event = data["event"]
  flag = False
  if "subtype" in event:
    flag = event["subtype"] not in ["bot_message", "message_changed"]
  if "username" in event:
    flag = flag and event["username"] != bot_name
  if event["type"] == "message" and flag:
    text = str(event.get("text")).lower()
    if "shirt" in text or "size" in text:
      update_shirt_prompt(event["channel"])
    elif "paid" in text or "due" in text or "pay" in text:
      paid = has_paid(event["user"])
      log(paid)
      paid_data = json.loads(paid)
      if paid_data["success"] == True and paid_data["hasPaid"] == True:
        send_slack_message(event["channel"], "Yes, you have paid!")
      else:
        send_slack_message(event["channel"], "Nope, you haven't paid yet. Do that at http://acm.cs.ua.edu/.")
    else:
      send_slack_message(event["channel"], "Hello. Ask me to update your t-shirt size, or if you've paid your dues.")
  return "ok", 200

# Listener for updating shirt size in database
@app.route("/update_shirt", methods=["POST"])
def update_shirt():
  # get shirt size and username
  payload = json.loads(request.form.get("payload"))
  log("Received {}".format(payload))
  size = str(payload["actions"][0].get("value"))
  userid = payload["user"]["id"]
  email = get_email(userid)

  # actually update shirt size and return the result
  requests.post(api_url + "/member/updateshirtsize", json={"email": email, "newShirtSize": size.upper(), "secretKey": secret_key})
  return "Updated t-shirt size to *" + size.upper() + "*, congratulations " + email + "!", 200

# Listener for reminders
@app.route("/remind", methods=["GET"])
def remind_hook():
  # TODO: add secret code
  r = requests.get(api_url + "/semester/unpaid", headers = { "secretKey": secret_key })
  unpaid = r.json()["unpaid"]
  for member in unpaid:
    email = str(member["crimsonEmail"])
    user = get_user(email)
    if (user != "not_found"):
      if (email == "magarwal@crimson.ua.edu"): # TODO: remove this condition
        dm = open_dm(user)
        if dm["ok"]:
          channel = dm["channel"]["id"]
          send_slack_message(channel, "Pay your dues. :)")

# Simple wrapper for sending a Slack message
def send_slack_message(channel, message):
  return sc.api_call(
    "chat.postMessage",
    channel=channel,
    text=message
  )

# Opens DM with a user
def open_dm(id):
  return sc.api_call(
    "im.open",
    user=id
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

# Returns the user ID for an email address
def get_user(email):
  user = sc.api_call(
    "users.lookupByEmail",
    email=email
  )
  return user["user"]["id"] if user["ok"] else "not_found"

# Add hasPaid functionality
def has_paid(id):
  email = get_email(id)
  paid = requests.post(api_url + "/member/ispaid", json={"email": email, "secretKey": secret_key})
  return paid.text

# Debug
def log(msg):
  print(str(msg))
  sys.stdout.flush()
