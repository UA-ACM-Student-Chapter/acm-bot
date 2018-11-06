import json
import os
import random
import requests
import sys
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pymongo import MongoClient

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
  print(request.get_json())
  data = request.get_json()
  log("Received {}".format(data))

  # Used to initially verify a Slack bot
  # if data["type"] == "url_verification":
  #   return data["challenge"]

  event = data["event"]
  flag = True

  if "subtype" in event:
    flag = event["subtype"] not in ["bot_message", "message_changed"]

  if "username" in event:
    flag = flag and event["username"] != bot_name

  if event["type"] == "message" and flag:
    text = str(event.get("text")).lower()
    user = event["user"]
    channel = event["channel"]
    if "id" in user:
      user = user["id"]
    current_workflow = get_current_user_workflow(user)
    if text == "quit":
      say_confirmation = set_current_workflow_item_inactive(user, channel)
      if say_confirmation:
        send_slack_message(channel, "Okay! I forgot what we were talking about.")
      else:
        send_slack_message(channel, "I don't think we were talking about anything in particular.")
    elif current_workflow != None:
      handle_workflow(user, channel, text, current_workflow)
    else:
      if is_admin(event["user"]) and text == "create election":
        send_slack_message(channel, "Okay, tell me the name of the election.")
        update_workflow(user, "get_election_name", True, None)

      elif is_admin(user) and text == "start election":
        prompt_elections_list(channel)
        set_current_workflow_item_inactive(user, channel)
        
      elif is_admin(user) and text == "list election users":
        get_users_subscribed_to_elections(channel)

      elif "election" in text:
        send_slack_message(channel, "You want to vote in the next election? Great! I'll notify you when a position is actively being voted for.")
        subscribe_to_elections(user, channel)

      elif "shirt" in text or "size" in text:
        update_shirt_prompt(channel)

      elif "paid" in text or "due" in text or "pay" in text:
        paid = has_paid(user)
        log(paid)
        paid_data = json.loads(paid)

        if paid_data["success"] == True and paid_data["hasPaid"] == True:
          send_slack_message(channel, "Yes, you have paid!")

        else:
          send_slack_message(channel, "Nope, you haven't paid yet. Do that at http://acm.cs.ua.edu/.")

      else:
        send_slack_message(channel, "Hello. Ask me to update your t-shirt size, or if you've paid your dues.")

  return "ok", 200

# Listener for updating shirt size in database
@app.route("/interactivity", methods=["POST"])
def interactivity():
  # get shirt size and username
  payload = json.loads(request.form.get("payload"))
  log("Received {}".format(payload))

  def update_tshirt():
    size = str(payload["actions"][0].get("value"))
    userid = payload["user"]["id"]
    email = get_email(userid)

    # actually update shirt size and return the result
    requests.post(api_url + "/member/updateshirtsize", json={"email": email, "newShirtSize": size.upper(), "secretKey": secret_key})

    return "Updated t-shirt size to *" + size.upper() + "*, congratulations " + email + "!", 200

  def start_election():
    election_name = payload["actions"][0].get("value")
    set_election_as_active(election_name)
    update_workflow(payload["user"], "election_mode", True, { "election_name": election_name })
    return "Started \"" + election_name + "\". *You can prompt users to vote for a position* by saying 'prompt \"position name\"'. To get the election stats, just say \"stats\". To use the current results of a position's votes to cascade to the next available position, say 'cascade \"position name\". To end the election, say 'stop election'."

  callback_actions = {
    "update_tshirt": update_tshirt,
    "start_election": start_election
  }
  
  return callback_actions[payload["callback_id"]]()  

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

@app.route("/start_election", methods=["POST"])
def start_election():
  payload = json.loads(request.form.get("payload"))
  log("Received {}".format(payload))
  election_name = str(payload["actions"][0].get("value"))
  userid = payload["user"]["id"]
  email = get_email(payload["user"]["id"])

  if is_admin(userid):
    start_election(election_name)
    return "Started election \"" + election_name + "\"."
  
  return "You're an evil, evil person trying to hack an election. Shame on you >:(."

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

def create_election(name, channel):
  store = get_db_connection()
  doc = { 'type': 'election', 'active': False, 'name': name, 'participants': [], 'positions': [] }
  store.db.insert_one(doc)

def update_workflow(username, state, active, data):
  store = get_db_connection()
  doc = { 'type': 'tracked_conversation', 'user': username, 'state': state, "active": True, "data": data }
  store.db.insert_one(doc)

def get_current_user_workflow(user):
  store = get_db_connection()
  return store.db.find_one({"type": "tracked_conversation", "user": user, "active": True}, sort=[('_id', -1)])

def handle_workflow(user, channel, text, workflow):
  def get_election_name():
    create_election(text, channel)
    send_slack_message(channel, "Alright, can you tell me the position names for the \"" + text + "\" election? Just list them like this: \"President\" \"Vice President\" \"Treasurer\"")
    set_current_workflow_item_inactive(user, channel)
    update_workflow(user, "get_position_names", True, None)

  def get_position_names():
    send_slack_message(channel, "Thanks! I won't do anything with that for now. Goodbye!")
    set_current_workflow_item_inactive(user, channel)

  def election_mode():
    if text == "stop election":
      send_slack_message(channel, "Okay, I've ended the election. Here's the results!")
      #give results
      set_current_workflow_item_inactive(user, channel)
    else:
      send_slack_message(channel, "You're currently running an election. To end the election, say 'stop election'. Remember, you can prompt users to vote for a position by saying 'prompt \"position name\"'; to get the election stats, just say \"stats\"; to use the current results of a position's votes to cascade to the next available position, say 'cascade \"position name\".")

  workflows = {
    "get_election_name": get_election_name,
    "get_position_names": get_position_names,
    "election_mode": election_mode
  }

  workflows[workflow["state"]]()

  print("handled workflow" + workflow["state"])

def set_current_workflow_item_inactive(user, channel):
  store = get_db_connection()
  current_workflow = get_current_user_workflow(user)
  if current_workflow != None:
    store.db.update_one({"_id": current_workflow["_id"]}, {"$set": {"active": False}})
    return True
  else:
    return False

def subscribe_to_elections(user, channel):
  store = get_db_connection()
  doc = {"type": "election_subscription", "email": get_email(user), "channel": channel }
  store.db.insert_one(doc)

def get_users_subscribed_to_elections(channel):
  store = get_db_connection()
  users = store.db.find({"type": "election_subscription"}).distinct("email")
  send_slack_message(channel, users)

def get_db_connection():
  client = MongoClient(os.environ['MONGODB_URI'])
  if os.environ["IS_PRODUCTION"].lower() == "true":
    return client.heroku_0hcp48pq
  return client.heroku_j9g2w0v4

def is_admin(user):
  return user == os.environ["ADMIN"]

def prompt_elections_list(channel):
  store = get_db_connection()
  elections = store.db.find({"type": "election"}, sort=[('_id', -1)])
  election_actions = []
  for election in elections:
    print(election)
    election_actions.append({
      "name": "election_name",
      "text": election["name"],
      "type": "button",
      "value": election["name"]
    })
  election_actions.append({
    "name": "election_name",
    "text": "Cancel",
    "type": "button",
    "value": "cancel"
  })
  return sc.api_call(
    "chat.postMessage",
    channel=channel,
    attachments=[
    {
      "title": "Which election do you want to start?",
      "fallback": "I can't start an election for some reason :'(",
      "callback_id": "start_election",
      "color": "#3AA3E3",
      "attachment_type": "default",
      "actions": election_actions
      }
    ]
  )

def set_election_as_active(name):
  store = get_db_connection()
  election = get_election(name)
  if election != None:
    store.db.update_one({"_id": election["_id"]}, {"$set": {"active": False}})
    return True
  else:
    return False

def get_election(name):
  store = get_db_connection()
  return store.db.find_one({"type": "election", "name": name})