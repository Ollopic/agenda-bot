from icalendar import Calendar
import datetime
import os
import pytz
import requests
import time

ICAL_URL = os.getenv("ICAL_URL")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_calendar_events():
    response = requests.get(ICAL_URL)
    response.raise_for_status()
    return Calendar.from_ical(response.text)

def send_discord_message(message: str):
    payload = {"content": message}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

NOTIFIED_EVENTS_FILE = "notified_events.txt"

def load_notified_events():
    if not os.path.exists(NOTIFIED_EVENTS_FILE):
        return set()
    with open(NOTIFIED_EVENTS_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_notified_event(event_id):
    with open(NOTIFIED_EVENTS_FILE, "a") as f:
        f.write(event_id + "\n")

def check_events():
    cal = get_calendar_events()
    notified_events = load_notified_events()
    now = datetime.datetime.now(pytz.UTC)

    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get("SUMMARY"))
            uid = str(component.get("UID"))
            dtstart = component.get("DTSTART").dt

            if isinstance(dtstart, datetime.date) and not isinstance(dtstart, datetime.datetime):
                dtstart = datetime.datetime.combine(dtstart, datetime.time.min, tzinfo=pytz.UTC)

            if (
                "autonomie" in summary.lower()
                and uid not in notified_events
                and dtstart > now
            ):
                send_discord_message(f"📅 Emarger pour le cours {summary}")
                save_notified_event(uid)

if __name__ == "__main__":
    while True:
        check_events()
        time.sleep(60)  # 1 minute
