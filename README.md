## Lancer le projet :

```bash
git clone https://github.com/Ollopic/agenda-bot.git
touch sent_events.json
cp .env.example .env
```

Editer le fichier `.env` pour y ajouter vos URL de calendrier iCal et de webhook Discord puis lancer le projet avec la commande :

```bash
docker-compose up -d
```

## Config env

- `ICAL_URL` : URL du calendrier iCal à surveiller (séparées par des virgules pour plusieurs URL)
  
**Exemple :**
  
```env
ICAL_URL=https://exemple.com/calendrier1.ics,https://exemple.com/calendrier2.ics
```

- `DISCORD_WEBHOOK_URL` : URL du webhook Discord où envoyer les notifications

- `TIMEZONE` : Fuseau horaire pour l'affichage des dates (par défaut `Europe/Paris`)
- `ROLE_ID_DAS` : ID du rôle Discord à mentionner pour les événements liés au DAS
- `ROLE_ID_ASR` : ID du rôle Discord à mentionner pour les événements liés au ASR

**Exemple :**
  
```env
ROLE_ID_DAS=123456789012345678
ROLE_ID_ASR=987654321098765432
```