# Nidia Smart Battery Recharge

A Home Assistant custom integration that optimizes night-time grid charging of home batteries based on learned household consumption and solar forecast.

## Features

- **Smart Planning**: Decides *if* and *how much* to charge from the grid to minimize daytime grid usage.
- **Adaptive Learning**: Learns your household's daily consumption patterns over a 3-week rolling window.
- **Solar Aware**: Incorporates next-day solar forecasts to avoid overcharging.
- **Safety First**: Configurable safety spread and minimum SOC reserves.
- **Fully Autonomous**: Handles everything from forecasting to controlling the inverter switch.
- **Notifications**: Sends a morning summary of the night's charging activity.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant.
2. Go to "Integrations" > "Custom repositories".
3. Add this repository URL: `https://github.com/antoniobaldassarre/nidia-smart-battery-recharge`
4. Select "Integration" as the category.
5. Click "Add" and then install "Nidia Smart Battery Recharge".
6. Restart Home Assistant.

### Manual Installation

1. Download the `night_battery_charger` folder from the `custom_components` directory in this repository.
2. Copy it to your Home Assistant's `custom_components` directory.
3. Restart Home Assistant.

## Configuration

1. Go to **Settings** > **Devices & Services**.
2. Click **Add Integration** and search for "Nidia Smart Battery Recharge".
3. Follow the configuration wizard:
   - **Inverter Grid Charge Switch**: The switch entity that enables grid charging on your inverter.
   - **Battery SOC Sensor**: Your battery's State of Charge sensor (%).
   - **Battery Capacity**: Total usable capacity of your battery in kWh.
   - **House Load Power Sensor**: Sensor measuring house consumption in Watts (excluding PV).
   - **Solar Forecast Tomorrow**: Sensor providing the total solar energy forecast for the next day (kWh).
   - **Notification Service**: (Optional) Service to notify, e.g., `notify.mobile_app_my_phone`.
   - **Minimum SOC Reserve**: The battery level that should always be preserved (%).
   - **Safety Spread**: Extra buffer percentage to charge above the calculated need.

## How It Works

1. **Learning**: The integration continuously monitors your house load power sensor to calculate daily energy consumption (kWh) for each day of the week. It maintains a 3-week history.
2. **Forecasting**: Every night at 22:59, it predicts tomorrow's consumption based on historical data for that specific weekday.
3. **Planning**:
   - It takes the **Forecasted Load** and subtracts the **Forecasted Solar Production**.
   - It calculates the **Required Energy** to cover the deficit, ensuring the **Minimum SOC Reserve** is respected.
   - It adds a **Safety Spread** buffer.
   - It determines the **Target SOC** and the **Energy to Charge** from the grid.
4. **Execution**:
   - If charging is needed, it turns ON the inverter's grid charge switch at **23:59**.
   - It monitors the battery SOC.
   - It turns OFF the switch when the **Target SOC** is reached or at **07:00** (whichever comes first).
5. **Reporting**: A summary is generated (and optionally sent via notification) in the morning.

## Lovelace Dashboard Example

Here is a complete example using a `vertical-stack` card to group everything together. This configuration uses standard Home Assistant cards (Entities, Gauge, Markdown).

```yaml
type: vertical-stack
cards:
  - type: tile
    entity: binary_sensor.night_charge_active
    name: Night Charge Status
    icon: mdi:battery-charging
    color: blue

  - type: entities
    title: Planning & Forecast
    entities:
      - entity: binary_sensor.night_charge_scheduled_tonight
        name: Scheduled Tonight
      - entity: sensor.night_charge_planned_grid_energy_kwh
        name: Planned Charge
      - entity: sensor.night_charge_target_soc_percent
        name: Target SOC
      - entity: sensor.night_charge_load_forecast_tomorrow_kwh
        name: Load Forecast (Tomorrow)
      - entity: sensor.night_charge_solar_forecast_tomorrow_kwh
        name: Solar Forecast (Tomorrow)

  - type: markdown
    title: Algorithm Reasoning
    content: >
      {{ states('sensor.night_charge_plan_reasoning') }}

  - type: markdown
    title: Last Run Summary
    content: >
      {{ states('sensor.night_charge_last_run_summary') }}
```

## Services

- `night_battery_charger.recalculate_plan_now`: Force an immediate recalculation of the plan.
- `night_battery_charger.force_charge_tonight`: Force the system to charge tonight (targets 100% SOC).
- `night_battery_charger.disable_tonight`: Prevent charging for the upcoming night.

## License

MIT
