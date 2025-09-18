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
        self.ical_urls = os.getenv("ICAL_URL", "").split(",")
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
        self.timezone = os.getenv("TIMEZONE", "Europe/Paris")

        if not self.ical_urls or not self.discord_webhook:
            raise ValueError(
                "ICAL_URL et DISCORD_WEBHOOK_URL doivent être définis dans le .env"
            )

        try:
            self.tz = pytz.timezone(self.timezone)
            logger.info(f"Fuseau horaire configuré: {self.timezone}")
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(
                f"Fuseau horaire inconnu '{self.timezone}', utilisation de 'Europe/Paris'"
            )
            self.tz = pytz.timezone("Europe/Paris")

        self.sent_events_file = "sent_events.json"
        self.sent_events = self.load_sent_events()

        logger.info(f"Initialisation avec {len(self.ical_urls)} agenda(s)")
        logger.info(f"Webhook Discord configuré: {self.discord_webhook[:50]}...")

    def load_sent_events(self) -> Set[str]:
        try:
            if os.path.exists(self.sent_events_file):
                with open(self.sent_events_file, "r") as f:
                    data = json.load(f)
                    # Nettoyer les anciens événements (plus de 24h)
                    cutoff = datetime.now() - timedelta(days=1)
                    cleaned_data = {
                        event_id: timestamp
                        for event_id, timestamp in data.items()
                        if datetime.fromisoformat(timestamp) > cutoff
                    }
                    if len(cleaned_data) != len(data):
                        logger.info(
                            f"Nettoyage: suppression de {len(data) - len(cleaned_data)} anciens événements"
                        )
                        self.save_sent_events(set(cleaned_data.keys()))
                    return set(cleaned_data.keys())
            return set()
        except Exception as e:
            logger.error(f"Erreur lors du chargement des événements envoyés: {e}")
            return set()

    def save_sent_events(self, events: Set[str]):
        try:
            data = {event_id: datetime.now().isoformat() for event_id in events}
            with open(self.sent_events_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des événements envoyés: {e}")

    def fetch_calendar(self, url: str) -> Calendar:
        try:
            logger.debug(f"Récupération du calendrier: {url[:50]}...")
            response = requests.get(url.strip(), timeout=30)
            response.raise_for_status()

            calendar = Calendar.from_ical(response.content)
            logger.debug("Calendrier récupéré avec succès")
            return calendar
        except Exception as e:
            logger.error(
                f"Erreur lors de la récupération du calendrier {url[:50]}: {e}"
            )
            raise

    def get_calendar_name(self, calendar: Calendar) -> str:
        try:
            return str(calendar.get("X-WR-CALNAME", "Agenda"))
        except:
            return "Agenda"

    def is_event_current(self, event) -> bool:
        try:
            now = datetime.now(self.tz)

            dtstart = event.get("dtstart")
            dtend = event.get("dtend")

            if not dtstart:
                return False

            start_dt = dtstart.dt
            end_dt = dtend.dt if dtend else start_dt + timedelta(hours=1)

            if hasattr(start_dt, "date"):
                if hasattr(start_dt, "tzinfo") and start_dt.tzinfo is not None:
                    start_time = start_dt.astimezone(self.tz)
                else:
                    start_time = self.tz.localize(start_dt.replace(tzinfo=None))
            else:
                start_time = self.tz.localize(
                    datetime.combine(start_dt, datetime.min.time())
                )
                end_dt = self.tz.localize(
                    datetime.combine(start_dt, datetime.max.time())
                )

            if hasattr(end_dt, "date"):
                if hasattr(end_dt, "tzinfo") and end_dt.tzinfo is not None:
                    end_time = end_dt.astimezone(self.tz)
                else:
                    end_time = self.tz.localize(end_dt.replace(tzinfo=None))
            else:
                end_time = self.tz.localize(
                    datetime.combine(end_dt, datetime.max.time())
                )

            is_current = start_time <= now <= end_time

            if is_current:
                logger.debug(
                    f"Événement en cours: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} (maintenant: {now.strftime('%H:%M')})"
                )

            return is_current

        except Exception as e:
            logger.error(
                f"Erreur lors de la vérification de l'heure de l'événement: {e}"
            )
            return False

    def create_event_id(self, event, calendar_name: str) -> str:
        try:
            uid = event.get("uid", "")
            summary = str(event.get("summary", ""))
            dtstart = event.get("dtstart")

            if uid:
                return f"{calendar_name}_{uid}"

            if dtstart:
                start_str = str(dtstart.dt)
                return f"{calendar_name}_{summary}_{start_str}"

            return f"{calendar_name}_{summary}_{hash(str(event))}"

        except Exception as e:
            logger.error(f"Erreur lors de la création de l'ID d'événement: {e}")
            return f"{calendar_name}_{hash(str(event))}"

    def send_discord_message(self, message: str):
        try:
            data = {"content": message, "username": "Autonomie Bot"}

            response = requests.post(self.discord_webhook, json=data, timeout=10)
            response.raise_for_status()

            logger.info(f"Message Discord envoyé avec succès: {message[:100]}...")

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du message Discord: {e}")

    def format_datetime(self, dt) -> str:
        try:
            if hasattr(dt, "strftime"):
                if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
                    dt = dt.astimezone(self.tz)
                elif hasattr(dt, "tzinfo") and dt.tzinfo is None:
                    dt = self.tz.localize(dt)

                return dt.strftime("%d/%m/%Y à %H:%M")
            return str(dt)
        except Exception as e:
            logger.debug(f"Erreur formatage datetime: {e}")
            return str(dt)

    def check_autonomie_events(self):
        logger.info("Début de la vérification des événements d'autonomie")
        events_found = 0
        notifications_sent = 0

        for url in self.ical_urls:
            if not url.strip():
                continue

            try:
                calendar = self.fetch_calendar(url)
                calendar_name = self.get_calendar_name(calendar)

                logger.info(f"Vérification du calendrier: {calendar_name}")

                for component in calendar.walk():
                    if component.name == "VEVENT":
                        events_found += 1

                        summary = str(component.get("summary", "")).lower()
                        if "autonomie" not in summary:
                            continue

                        logger.debug(
                            f"Événement d'autonomie trouvé: {component.get('summary', '')}"
                        )

                        if not self.is_event_current(component):
                            continue

                        event_id = self.create_event_id(component, calendar_name)

                        if event_id in self.sent_events:
                            logger.debug(f"Notification déjà envoyée pour: {event_id}")
                            continue

                        course_name = str(component.get("summary", "Cours d'autonomie"))
                        start_time = component.get("dtstart")
                        start_formatted = (
                            self.format_datetime(start_time.dt)
                            if start_time
                            else "maintenant"
                        )

                        message = f"[{calendar_name}] Émarger pour le cours {course_name} à {start_formatted}"

                        self.send_discord_message(message)

                        self.sent_events.add(event_id)
                        notifications_sent += 1

                        logger.info(f"Notification envoyée pour: {course_name}")

            except Exception as e:
                logger.error(
                    f"Erreur lors de la vérification du calendrier {url[:50]}: {e}"
                )

        if notifications_sent > 0:
            self.save_sent_events(self.sent_events)

        logger.info(
            f"Vérification terminée: {events_found} événements analysés, {notifications_sent} notifications envoyées"
        )

    def run_continuous(self, interval_minutes: int = 5):
        logger.info(
            f"Démarrage du service de surveillance (vérification toutes les {interval_minutes} minutes)"
        )

        while True:
            try:
                self.check_autonomie_events()
                logger.info(f"Prochaine vérification dans {interval_minutes} minutes")
                time.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                logger.info("Arrêt du service demandé par l'utilisateur")
                break
            except Exception as e:
                logger.error(f"Erreur inattendue: {e}")
                logger.info("Reprise dans 1 minute...")
                time.sleep(60)


def main():
    try:
        notifier = AutonomieNotifier()

        notifier.run_continuous()

    except Exception as e:
        logger.error(f"Erreur fatale: {e}")


if __name__ == "__main__":
    main()
