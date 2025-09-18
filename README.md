## Lancer le projet :

```bash
git clone https://github.com/Ollopic/agenda-bot.git
touch notified_events.txt
cp .env.example .env
```

Editer le fichier `.env` pour y ajouter vos URL de calendrier iCal et de webhook Discord puis lancer le projet avec la commande :

```bash
docker-compose up -d
```