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

# Automatischer Login über den Browser-Helfer:
# Die Empfangs-Adresse, an die der Helfer den `code` schickt.
CALLBACK_PATH = f"/api/{DOMAIN}/callback"
# Anmelde-Hilfsseite (Weg "Lesezeichen", ohne Browser-Erweiterung):
# HA liefert selbst eine Seite mit dem Lesezeichen und dem Lidl-Login-Knopf aus.
LOGIN_PATH = f"/api/{DOMAIN}/login"
# Ablage für laufende Login-Vorgänge (flow_id -> Sicherheits-Token)
DATA_FLOW_TOKENS = "flow_tokens"
# Merker, dass die Empfangs-/Hilfsseiten (HTTP-Views) registriert sind
DATA_VIEW_REGISTERED = "view_registered"
