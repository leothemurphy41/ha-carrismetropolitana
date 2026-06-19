"""Constants for Carris Metropolitana integration."""

DOMAIN = "carrismetropolitana"
DEFAULT_NAME = "Carris Metropolitana"

# Configuration keys
CONF_MUNICIPALITY_IDS = "municipality_ids"
CONF_LINE_IDS = "line_ids"
CONF_STOP_IDS = "stop_ids"

# Platform
PLATFORMS = ["sensor"]

# API settings
API_BASE_URL = "https://api.carrismetropolitana.pt/v2"
API_TIMEOUT = 30  # seconds
API_RETRY_ATTEMPTS = 3
API_RETRY_DELAY = 5  # seconds

# Update interval
UPDATE_INTERVAL_MINUTES = 1

# Sensor defaults
DEFAULT_ARRIVALS_TO_SHOW = 5
DEFAULT_MAX_ALERTS = 10
DEFAULT_STOP_ICON = "mdi:bus-stop"
DEFAULT_LINE_ICON = "mdi:bus"
DEFAULT_ALERT_ICON = "mdi:alert-circle"

# State strings
STATE_NO_SERVICE = "Sem serviço"
STATE_NO_ALERTS = "Sem alertas"
STATE_UNKNOWN = "Desconhecido"

# Attributes
ATTR_STOP_ID = "stop_id"
ATTR_LINE_ID = "line_id"
ATTR_ARRIVALS = "arrivals"
ATTR_VEHICLES = "vehicles"
ATTR_ALERTS = "alerts"
ATTR_NEXT_ARRIVALS = "next_arrivals"
ATTR_TOTAL_ARRIVALS = "total_arrivals"
ATTR_TOTAL_VEHICLES = "total_vehicles"
ATTR_TOTAL_ALERTS = "total_alerts"

# Device info
MANUFACTURER = "Carris Metropolitana"
MODEL = "API v2"
CONFIGURATION_URL = "https://www.carrismetropolitana.pt"

# Logging
LOG_LEVEL_DEFAULT = "INFO"
LOG_LEVEL_DEBUG = "DEBUG"
