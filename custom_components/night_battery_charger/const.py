"""Constants for the Nidia Smart Battery Recharge integration."""

DOMAIN = "night_battery_charger"

# Configuration Keys
CONF_INVERTER_SWITCH = "inverter_switch_entity_id"
CONF_BATTERY_SOC_SENSOR = "battery_soc_sensor_entity_id"
CONF_BATTERY_CAPACITY = "battery_capacity_kwh"
CONF_HOUSE_LOAD_SENSOR = "house_load_power_sensor_entity_id"
CONF_SOLAR_FORECAST_SENSOR = "solar_forecast_sensor_entity_id"
CONF_SOLAR_FORECAST_TODAY_SENSOR = "solar_forecast_today_sensor"
CONF_NOTIFY_SERVICE = "notify_service"

# Notification Flags
CONF_NOTIFY_ON_START = "notify_on_start"
CONF_NOTIFY_ON_UPDATE = "notify_on_update"
CONF_NOTIFY_ON_END = "notify_on_end"

# Tuning Parameters
CONF_MIN_SOC_RESERVE = "min_soc_reserve_percent"
CONF_SAFETY_SPREAD = "safety_spread_percent"
CONF_BATTERY_BYPASS_SWITCH = "battery_bypass_switch"

# Charging Window Configuration (NEW)
CONF_CHARGING_WINDOW_START_HOUR = "charging_window_start_hour"
CONF_CHARGING_WINDOW_START_MINUTE = "charging_window_start_minute"
CONF_CHARGING_WINDOW_END_HOUR = "charging_window_end_hour"
CONF_CHARGING_WINDOW_END_MINUTE = "charging_window_end_minute"

# EV Configuration (NEW)
CONF_EV_TIMEOUT_HOURS = "ev_timeout_hours"

# Energy Pricing Configuration (NEW)
CONF_PRICE_PEAK = "price_peak_eur_kwh"
CONF_PRICE_OFFPEAK = "price_offpeak_eur_kwh"
CONF_PRICE_F1 = "price_f1_eur_kwh"
CONF_PRICE_F2 = "price_f2_eur_kwh"
CONF_PRICE_F3 = "price_f3_eur_kwh"
CONF_PRICING_MODE = "pricing_mode"

# Defaults
DEFAULT_NAME = "Nidia Smart Battery Recharge"
DEFAULT_MIN_SOC_RESERVE = 15.0
DEFAULT_SAFETY_SPREAD = 10.0
DEFAULT_BATTERY_CAPACITY = 10.0
DEFAULT_NOTIFY_ON_START = True
DEFAULT_NOTIFY_ON_UPDATE = True
DEFAULT_NOTIFY_ON_END = True

# Charging Window Defaults (NEW)
DEFAULT_CHARGING_WINDOW_START_HOUR = 0
DEFAULT_CHARGING_WINDOW_START_MINUTE = 1
DEFAULT_CHARGING_WINDOW_END_HOUR = 7
DEFAULT_CHARGING_WINDOW_END_MINUTE = 0

# EV Defaults (NEW)
DEFAULT_EV_TIMEOUT_HOURS = 6

# Pricing Defaults (NEW) - Based on Italian PUN averages 2024
DEFAULT_PRICE_PEAK = 0.25  # €/kWh - F1 daytime peak
DEFAULT_PRICE_OFFPEAK = 0.12  # €/kWh - F3 night off-peak
DEFAULT_PRICE_F1 = 0.25  # Peak hours
DEFAULT_PRICE_F2 = 0.20  # Mid-peak hours
DEFAULT_PRICE_F3 = 0.12  # Off-peak hours
DEFAULT_PRICING_MODE = "two_tier"  # Options: "two_tier", "three_tier"

# Storage
STORAGE_KEY = f"{DOMAIN}.storage"
STORAGE_VERSION = 2  # Incremented for new data structures

# Attributes / Sensor Names
ATTR_PLANNED_CHARGE_KWH = "planned_grid_charge_kwh"
ATTR_TARGET_SOC = "target_soc_percent"
ATTR_LOAD_FORECAST = "load_forecast_kwh"
ATTR_SOLAR_FORECAST = "solar_forecast_kwh"

# Services
SERVICE_RECALCULATE = "recalculate_plan_now"
SERVICE_FORCE_CHARGE = "force_charge_tonight"
SERVICE_DISABLE_CHARGE = "disable_tonight"

# Rate Limiting (NEW)
SERVICE_COOLDOWN_SECONDS = 60  # Minimum time between service calls
POWER_DEBOUNCE_SECONDS = 60  # Minimum time between power updates
POWER_CHANGE_THRESHOLD = 0.05  # 5% change threshold for power updates
