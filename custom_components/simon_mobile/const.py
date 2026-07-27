"""Constants for the SIMon mobile integration."""

from datetime import timedelta

DOMAIN = "simon_mobile"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

API_BASE_URL = "https://api.simonmobile.de/api"
TOKEN_URL = f"{API_BASE_URL}/token"
GRAPHQL_URL = f"{API_BASE_URL}/graphql"
CLIENT_ID = "simon"
CLIENT_SECRET = "simon"

UPDATE_INTERVAL = timedelta(minutes=15)

