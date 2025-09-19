import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Set

import pytz
import requests
from icalendar import Calendar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("autonomie_notifier.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class AutonomieNotifier:
    def __init__(self):
        self.ical_urls = [
            url.strip() for url in os.getenv("ICAL_URL", "").split(",") if url.strip()
        ]
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
        self.tz = self._setup_timezone(os.getenv("TIMEZONE", "Europe/Paris"))
        self.ROLE_ID_DAS = os.getenv("ROLE_ID_DAS", "ROLE_ID_DAS")
        self.ROLE_ID_ASR = os.getenv("ROLE_ID_ASR", "ROLE_ID_ASR")

        if not self.ical_urls or not self.discord_webhook:
            raise ValueError("ICAL_URL et DISCORD_WEBHOOK_URL doivent être définis")

        self.sent_events_file = "sent_events.json"
        self.sent_events = self._load_sent_events()

        logger.info(
            f"Initialisation: {len(self.ical_urls)} agenda(s), timezone: {self.tz.zone}"
        )

    def _setup_timezone(self, timezone_str: str) -> pytz.BaseTzInfo:
        try:
            return pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(
                f"Timezone '{timezone_str}' inconnue, utilisation d'Europe/Paris"
            )
            return pytz.timezone("Europe/Paris")

    def _load_sent_events(self) -> Set[str]:
        if not os.path.exists(self.sent_events_file):
            return set()

        try:
            with open(self.sent_events_file, "r") as f:
                data = json.load(f)

            # Nettoyer les événements de plus de 24h
            cutoff = datetime.now() - timedelta(days=1)
            cleaned = {
                event_id: timestamp
                for event_id, timestamp in data.items()
                if datetime.fromisoformat(timestamp) > cutoff
            }

            if len(cleaned) != len(data):
                logger.info(
                    f"Nettoyage: {len(data) - len(cleaned)} anciens événements supprimés"
                )
                self._save_sent_events(set(cleaned.keys()))

            return set(cleaned.keys())

        except Exception as e:
            logger.error(f"Erreur chargement événements: {e}")
            return set()

    def _save_sent_events(self, events: Set[str]):
        try:
            data = {event_id: datetime.now().isoformat() for event_id in events}
            with open(self.sent_events_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")

    def _fetch_calendar(self, url: str) -> Calendar:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Calendar.from_ical(response.content)

    def _normalize_datetime(self, dt) -> datetime:
        if hasattr(dt, "date"):  # datetime object
            if dt.tzinfo is None:
                return self.tz.localize(dt)
            return dt.astimezone(self.tz)
        else:  # date object
            return self.tz.localize(datetime.combine(dt, datetime.min.time()))

    def _is_event_current(self, event) -> bool:
        try:
            now = datetime.now(self.tz)

            dtstart = event.get("dtstart")
            if not dtstart:
                return False

            start_time = self._normalize_datetime(dtstart.dt)

            dtend = event.get("dtend")
            if dtend:
                end_time = self._normalize_datetime(dtend.dt)
            else:
                end_time = start_time + timedelta(hours=1)

            return start_time <= now <= end_time

        except Exception as e:
            logger.error(f"Erreur vérification heure événement: {e}")
            return False

    def _create_event_id(self, event, calendar_name: str) -> str:
        uid = event.get("uid", "")
        if uid:
            return f"{calendar_name}_{uid}"

        summary = str(event.get("summary", ""))
        dtstart = event.get("dtstart")
        start_str = str(dtstart.dt) if dtstart else "no_time"

        return f"{calendar_name}_{summary}_{start_str}"

    def _send_discord_message(self, message: str, calendar_name: str):
        mention = "@everyone"
        if "DAS" in calendar_name.upper():
            mention = f"<@&{self.ROLE_ID_DAS}>"
        elif "ASR" in calendar_name.upper():
            mention = f"<@&{self.ROLE_ID_ASR}>"
        data = {"content": f"{mention} {message}", "username": "Autonomie Bot"}
        response = requests.post(self.discord_webhook, json=data, timeout=10)
        response.raise_for_status()
        logger.info(f"Message Discord envoyé: {message[:100]}...")

    def _format_datetime(self, dt) -> str:
        try:
            normalized_dt = self._normalize_datetime(dt)
            return normalized_dt.strftime("%d/%m/%Y à %H:%M")
        except:
            return str(dt)

    def check_autonomie_events(self):
        logger.info("Vérification des événements d'autonomie")
        events_found = notifications_sent = 0

        for url in self.ical_urls:
            try:
                calendar = self._fetch_calendar(url)
                calendar_name = str(calendar.get("X-WR-CALNAME", "Agenda"))

                logger.info(f"Vérification: {calendar_name}")

                for component in calendar.walk():
                    if component.name != "VEVENT":
                        continue

                    events_found += 1
                    summary = str(component.get("summary", "")).lower()

                    if "autonomie" not in summary:
                        continue

                    if not self._is_event_current(component):
                        continue

                    event_id = self._create_event_id(component, calendar_name)
                    if event_id in self.sent_events:
                        continue

                    course_name = str(component.get("summary", "Cours d'autonomie"))
                    start_time = component.get("dtstart")
                    start_formatted = (
                        self._format_datetime(start_time.dt)
                        if start_time
                        else "maintenant"
                    )

                    message = f"[{calendar_name}] Émarger pour le cours {course_name} à {start_formatted}"
                    self._send_discord_message(message, calendar_name)

                    self.sent_events.add(event_id)
                    notifications_sent += 1
                    logger.info(f"Notification envoyée: {course_name}")

            except Exception as e:
                logger.error(f"Erreur calendrier {url[:50]}: {e}")

        if notifications_sent > 0:
            self._save_sent_events(self.sent_events)

        logger.info(
            f"Terminé: {events_found} événements, {notifications_sent} notifications"
        )

    def run_continuous(self, interval_minutes: int = 5):
        logger.info(f"Surveillance démarrée (intervalle: {interval_minutes} min)")

        while True:
            try:
                self.check_autonomie_events()
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                logger.info("Arrêt demandé")
                break
            except Exception as e:
                logger.error(f"Erreur inattendue: {e}")
                time.sleep(60)  # Attendre 1 min avant de reprendre


def main():
    try:
        notifier = AutonomieNotifier()
        notifier.run_continuous()
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")


if __name__ == "__main__":
    main()
