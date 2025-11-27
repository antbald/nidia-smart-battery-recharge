"""Constants for the Nidia Smart Battery Recharge integration."""

DOMAIN = "night_battery_charger"

# Configuration Keys
CONF_INVERTER_SWITCH = "inverter_switch_entity_id"
CONF_BATTERY_SOC_SENSOR = "battery_soc_sensor_entity_id"
CONF_BATTERY_CAPACITY = "battery_capacity_kwh"
CONF_HOUSE_LOAD_SENSOR = "house_load_power_sensor_entity_id"
CONF_SOLAR_FORECAST_SENSOR = "solar_forecast_sensor_entity_id"
CONF_NOTIFY_SERVICE = "notify_service"

# Tuning Parameters
CONF_MIN_SOC_RESERVE = "min_soc_reserve_percent"
CONF_SAFETY_SPREAD = "safety_spread_percent"

# Defaults
DEFAULT_NAME = "Nidia Smart Battery Recharge"
DEFAULT_MIN_SOC_RESERVE = 15.0
DEFAULT_SAFETY_SPREAD = 10.0
DEFAULT_BATTERY_CAPACITY = 10.0

# Storage
STORAGE_KEY = f"{DOMAIN}.storage"
STORAGE_VERSION = 1

# Attributes / Sensor Names
ATTR_PLANNED_CHARGE_KWH = "planned_grid_charge_kwh"
ATTR_TARGET_SOC = "target_soc_percent"
ATTR_LOAD_FORECAST = "load_forecast_kwh"
ATTR_SOLAR_FORECAST = "solar_forecast_kwh"

# Services
SERVICE_RECALCULATE = "recalculate_plan_now"
SERVICE_FORCE_CHARGE = "force_charge_tonight"
SERVICE_DISABLE_CHARGE = "disable_tonight"
