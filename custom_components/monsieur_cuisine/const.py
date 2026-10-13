"""Konstanten der Monsieur-Cuisine-Integration."""
from datetime import timedelta

DOMAIN = "monsieur_cuisine"

# Anmeldung (Tecpal-Sitzung aus dem Lidl-Login)
CONF_JWT = "jwt"
CONF_USER_ID = "user_id"
CONF_COMPANION_APP_ID = "companion_app_id"
CONF_LIDL_REFRESH_TOKEN = "lidl_refresh_token"
CONF_REFRESH_TOKEN = "refresh_token"  # alt (v1), nur zur Abwärtskompatibilität

UPDATE_INTERVAL = timedelta(minutes=15)

# Konto-Daten (Einkaufsliste, Wochenplaner) – ändern sich selten, daher
# ruhiger Abruf.
DATA_ACCOUNT = "account"
ACCOUNT_UPDATE_INTERVAL = timedelta(minutes=30)
# Wochenplaner-Vorschaufenster (Tage ab heute) für den Zustand des Kalenders.
# Die API erlaubt höchstens ~1 Monat Spanne, deshalb unter 31 bleiben.
PLANNER_WINDOW_DAYS = 30

# Live-Status über gRPC (Push, kein Abruf-Intervall)
DATA_LIVE = "live"
# Nur dieses Modell liefert einen Rahmen, den wir deuten können.
LIVE_MODEL = "MC3.0"
# Wiederverbinden mit wachsender Wartezeit (Sekunden)
LIVE_RETRY_START = 5
LIVE_RETRY_MAX = 300
# Nach so langer Stille gilt der Live-Status als veraltet (das Gerät schaltet
# sich selbst ab, dann kommt einfach nichts mehr).
LIVE_STALE_AFTER = timedelta(minutes=10)

SERVICE_SEND_RECIPE = "send_recipe"
ATTR_URL = "url"
ATTR_RECIPE = "recipe"
ATTR_RECIPE_ID = "recipe_id"
ATTR_DRY_RUN = "dry_run"

EVENT_RECIPE_SENT = f"{DOMAIN}_recipe_sent"

# Login über den Browser-Helfer:
# Die Empfangs-Adresse, an die der Helfer den `code` schickt.
CALLBACK_PATH = f"/api/{DOMAIN}/callback"
# Ablage für laufende Login-Vorgänge (flow_id -> Sicherheits-Token)
DATA_FLOW_TOKENS = "flow_tokens"
# Flow-IDs, bei denen der Abschluss-Schritt schon betreten wurde. Nötig, weil
# Dialog und Empfangs-Adresse ihn beide aufrufen könnten: wer zuerst drin ist,
# beansprucht ihn, der andere hält sich still raus.
DATA_FLOW_FINISHING = "flow_finishing"
# Merker, dass die Empfangs-Adresse (HTTP-View) registriert ist
DATA_VIEW_REGISTERED = "view_registered"
