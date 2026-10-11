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

SERVICE_SEND_RECIPE = "send_recipe"
ATTR_URL = "url"
ATTR_RECIPE = "recipe"
ATTR_RECIPE_ID = "recipe_id"
ATTR_DRY_RUN = "dry_run"

EVENT_RECIPE_SENT = f"{DOMAIN}_recipe_sent"
