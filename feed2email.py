#!/usr/bin/env python3

# vim: set ai et ts=4 sw=4:

# feed2email.py
# (c) Aleksander Alekseev 2016-2017
# http://eax.me/

import feedparser

from smtplib import SMTP
# from smtplib import SMTP_SSL as SMTP
from email.mime.text import MIMEText
from contextlib import contextmanager
import signal
import getpass
import hashlib
import time
import sys
import re

server = 'smtp.yandex.ru'
port = 587 # 25
login = "YOUR_SENDER_LOGIN"
from_addr = "NEWS <YOUR_SENDER_LOGIN@yandex.ru>"
receiver = "YOUR_EMAIL"
processed_urls_fname = "processed-urls.txt"
feed_list_fname = "feed-list.txt"
# change to True before first run or you will receive A LOT of emails
# then change back to False
fake_send = False
sleep_time = 60*5 # seconds
net_timeout = 20 # seconds
smtp_retry_time = 30 # seconds
smtp_retries_num = 5

# >>> import hashlib
# >>> hashlib.sha1(b"qwerty").hexdigest()
# 'b1b3773a05c0ed0176787a4f1574ff0075f7521e'
pwhash = 'YOUR_PASSWORD_SHA1_HASH'

# FUNCS

class TimeoutException(Exception): pass

@contextmanager
def timeout_sec(seconds):
  def signal_handler(signum, frame):
    raise TimeoutException(Exception("Timed out!"))
  signal.signal(signal.SIGALRM, signal_handler)
  signal.alarm(seconds)
  try:
    yield
  finally:
    signal.alarm(0)

def file_to_list(fname):
  rslt = []
  with open(fname, "r") as f:
    rslt = [x for x in f.read().split("\n") if x.strip() != "" ]
  return rslt

# MAIN

password = getpass.getpass("SMTP Password: ")

if hashlib.sha1(bytearray(password, 'utf-8')).hexdigest() != pwhash:
  print("Invalid password", file = sys.stderr)
  sys.exit(1)

while True:
  feed_list = file_to_list(feed_list_fname)
  # filter comments
  feed_list = [ x for x in feed_list if not re.match("(?i)\s*#", x) ]
  keep_urls = 1000*len(feed_list)
  processed_urls = []

  try:
    processed_urls = file_to_list(processed_urls_fname)
  except FileNotFoundError:
    pass

  print("Processing {} feeds...".format(len(feed_list)))

  for feed in feed_list:
    print(feed)
    f = None
    try:
      with timeout_sec(net_timeout):
        f = feedparser.parse(feed)
    except TimeoutException:
      print("ERROR: Timeout!")
      continue

    feed_title = f['feed'].get('title', '(NO TITLE)')
    feed_link = f['feed'].get('link', '(NO LINK)')

    for entry in f['entries']:
      if entry['link'] in processed_urls:
        continue

      subject = "{title} | {feed_title} ({feed_link})".format(
          title = entry.get('title', '(NO TITLE'),
          feed_title = feed_title,
          feed_link = feed_link
        )
      print(subject)
      summary = entry.get('summary', '(NO SUMMARY)')
      body = "{summary}\n\n{link}\n\nSource feed: {feed}".format(
          summary = summary[:256],
          link = entry['link'],
          feed = feed
        )
      print(body)
      print("-------")

      msg = MIMEText(body, 'plain')
      msg['Subject'] = subject
      msg['From'] = from_addr
      msg['To'] = receiver

      if not fake_send:
        for attempt in range(1, smtp_retries_num+1):
          try:
            with timeout_sec(net_timeout), SMTP(server, port) as conn:
              conn.starttls()
              conn.login(login, password)
              conn.sendmail(from_addr, [receiver], msg.as_string())
            break
          except Exception as exc:
            print(("Failed to send email {}/{} - {}, " +
                  "retrying in {} seconds").format(
                    attempt, smtp_retries_num, exc,
                    smtp_retry_time
                  )
            )
            time.sleep(smtp_retry_time)

      processed_urls = [ entry['link'] ] + processed_urls

  with open(processed_urls_fname, "w") as urls_file:
    urls_file.write("\n".join(processed_urls[:keep_urls]))

  print("Sleeping {} seconds...".format(sleep_time))
  time.sleep(sleep_time)

