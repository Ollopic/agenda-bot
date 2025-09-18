import requests
import datetime
import pytz
from icalendar import Calendar
import os

ICAL_URL = os.getenv("ICAL_URL")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_calendar_events():
    response = requests.get(ICAL_URL)
    response.raise_for_status()
    return Calendar.from_ical(response.text)

def send_discord_message(message: str):
    payload = {"content": message}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def check_events():
    cal = get_calendar_events()
    now = datetime.datetime.now(pytz.UTC)

    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get("SUMMARY"))
            dtstart = component.get("DTSTART").dt
            dtend = component.get("DTEND").dt

            if isinstance(dtstart, datetime.date) and not isinstance(dtstart, datetime.datetime):
                dtstart = datetime.datetime.combine(dtstart, datetime.time.min, tzinfo=pytz.UTC)
            if isinstance(dtend, datetime.date) and not isinstance(dtend, datetime.datetime):
                dtend = datetime.datetime.combine(dtend, datetime.time.min, tzinfo=pytz.UTC)

            if "autonomie" in summary.lower():
                send_discord_message(f"📅 Emarger pour le cours {summary}")
                return

if __name__ == "__main__":
    check_events()
