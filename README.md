# 🔋 Nidia Smart Battery Recharge

<p align="center">
  <img src="https://img.shields.io/github/v/release/antoniobaldassarre/nidia-smart-battery-recharge?style=for-the-badge" alt="Release">
  <img src="https://img.shields.io/github/license/antoniobaldassarre/nidia-smart-battery-recharge?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/HACS-Custom-orange?style=for-the-badge" alt="HACS">
</p>

**Nidia Smart Battery Recharge** is an intelligent Home Assistant integration that optimizes your home battery charging strategy. It learns your household's consumption patterns, considers solar production forecasts, and automatically decides when and how much to charge from the grid during off-peak hours.

## 🎯 Why Nidia?

If you have a home battery system with solar panels, you face a daily challenge: **how much should I charge from the grid tonight?**

- Charge too little → You'll need expensive daytime grid power
- Charge too much → You waste energy and miss out on solar production
- Charge every night → Unnecessary costs and battery wear

**Nidia solves this** by intelligently analyzing your consumption patterns and solar forecasts to charge exactly what you need, when you need it.

## ✨ Key Features

### 🧠 **Adaptive Learning**
- Learns your household's consumption patterns over a 3-week rolling window
- Tracks consumption by day of the week (Mondays vs. Sundays have different patterns!)
- Automatically adapts to changing habits and seasonal variations

### ☀️ **Solar-Aware Planning**
- Integrates tomorrow's solar production forecast
- Avoids unnecessary charging when solar will cover your needs
- Calculates the exact energy deficit to charge overnight

### 🎯 **Smart Decision Making**
- Decides **IF** charging is needed (not blindly charging every night)
- Calculates **HOW MUCH** to charge based on forecasted needs
- Respects battery reserves and safety margins
- Prevents overcharging and battery degradation

### 🔒 **Safe & Configurable**
- Minimum SOC reserve to protect battery health
- Safety spread buffer for unexpected consumption
- Automatic shutoff at target SOC or morning cutoff time
- Manual override options for special situations

### 📊 **Complete Visibility**
- Real-time sensors for all metrics
- Detailed reasoning explanations for every decision
- Weekday-specific consumption averages
- Last run summaries and notifications

### 🔘 **One-Click Testing**
- Recalculate plan button to preview tomorrow's strategy
- Test the algorithm without waiting for midnight
- Understand decisions before they happen

## 📥 Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Go to **Integrations** → **⋮** → **Custom repositories**
3. Add repository URL: `https://github.com/antoniobaldassarre/nidia-smart-battery-recharge`
4. Select **Integration** as category
5. Click **Download** on "Nidia Smart Battery Recharge"
6. **Restart Home Assistant**
7. Go to **Settings** → **Devices & Services** → **Add Integration**
8. Search for "Nidia Smart Battery Recharge" and configure

### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/antoniobaldassarre/nidia-smart-battery-recharge/releases)
2. Extract and copy the `custom_components/night_battery_charger` folder to your Home Assistant's `config/custom_components/` directory
3. Restart Home Assistant
4. Add the integration via **Settings** → **Devices & Services**

## ⚙️ Configuration

The integration uses a friendly **3-step configuration wizard**:

### Step 1: Core Configuration
- **Inverter Grid Charge Switch**: The switch entity that enables/disables grid charging on your inverter
- **Battery Capacity**: Total usable capacity of your battery system (kWh)
- **Battery SOC Sensor**: Sensor showing current battery State of Charge (0-100%)

### Step 2: Sensors Setup
- **House Load Power Sensor**: Sensor measuring instantaneous house consumption in Watts (used for learning daily patterns)
- **Solar Forecast Tomorrow**: Sensor providing tomorrow's estimated solar production in kWh

### Step 3: Tuning & Notifications
- **Minimum SOC Reserve** (default: 15%): Battery level always preserved, never counted as available for consumption
- **Safety Spread** (default: 10%): Extra buffer percentage added to calculated charging need
- **Notification Service** (optional): Service to receive morning summaries (e.g., `notify.mobile_app_your_phone`)

## 🔧 How It Works

### 1. 📚 **Learning Phase** (Continuous)
The integration monitors your **House Load Power Sensor** throughout the day:
- Calculates total daily energy consumption (kWh)
- Stores consumption data by weekday (Monday, Tuesday, etc.)
- Maintains a 3-week rolling history
- Automatically learns your weekly patterns

### 2. 🔮 **Forecasting Phase** (22:59 daily)
Every night at 22:59, the system forecasts tomorrow's needs:
- Retrieves historical consumption for tomorrow's weekday
- Calculates average consumption from similar past days
- Reads tomorrow's solar production forecast from your sensor
- Estimates the energy deficit: `Deficit = Consumption - Solar`

### 3. 🧮 **Planning Phase** (22:59 daily)
The algorithm calculates the optimal charging strategy:

```
Current Battery Energy = (Current SOC / 100) × Battery Capacity
Reserve Energy = (Min SOC Reserve / 100) × Battery Capacity
Available Energy = Current Battery Energy - Reserve Energy

Net Load from Battery = Consumption Forecast - Solar Forecast
Required Energy = Reserve Energy + max(0, Net Load from Battery)
Target Energy = Required Energy × (1 + Safety Spread / 100)

Target SOC = min(100%, max(Min SOC Reserve, Target Energy / Battery Capacity × 100))
Charge Needed = max(0, Target Energy - Current Battery Energy)
```

### 4. ⚡ **Execution Phase** (23:59 - 07:00)
If charging is needed:
- **23:59**: Turns ON the inverter grid charge switch
- **Monitoring**: Checks battery SOC every 5 minutes
- **Auto-shutoff**: Turns OFF when Target SOC is reached OR at 07:00 (whichever comes first)
- **Recording**: Saves the actual energy charged for next day's learning

### 5. 📝 **Reporting Phase** (07:00)
Every morning:
- Generates a summary of the night's activity
- Updates the "Last Run Summary" sensor
- Sends an optional notification if configured
- Resets for the next cycle

## 📊 Entities Created

### Sensors

| Entity ID | Description | Unit |
|-----------|-------------|------|
| `sensor.night_charge_planned_grid_energy_kwh` | Energy planned to charge from grid tonight | kWh |
| `sensor.night_charge_target_soc_percent` | Target battery SOC to reach | % |
| `sensor.night_charge_load_forecast_tomorrow_kwh` | Forecasted consumption for tomorrow | kWh |
| `sensor.night_charge_solar_forecast_tomorrow_kwh` | Forecasted solar production for tomorrow | kWh |
| `sensor.night_charge_last_run_charged_energy_kwh` | Actual energy charged in last run | kWh |
| `sensor.night_charge_last_run_summary` | Text summary of last charging session | - |
| `sensor.night_charge_plan_reasoning` | Detailed explanation of current plan | - |
| `sensor.night_charge_min_soc_reserve_percent` | Configured minimum SOC reserve | % |
| `sensor.night_charge_safety_spread_percent` | Configured safety spread | % |
| `sensor.night_charge_avg_consumption_monday` | Average consumption on Mondays | kWh |
| `sensor.night_charge_avg_consumption_tuesday` | Average consumption on Tuesdays | kWh |
| `sensor.night_charge_avg_consumption_wednesday` | Average consumption on Wednesdays | kWh |
| `sensor.night_charge_avg_consumption_thursday` | Average consumption on Thursdays | kWh |
| `sensor.night_charge_avg_consumption_friday` | Average consumption on Fridays | kWh |
| `sensor.night_charge_avg_consumption_saturday` | Average consumption on Saturdays | kWh |
| `sensor.night_charge_avg_consumption_sunday` | Average consumption on Sundays | kWh |

### Binary Sensors

| Entity ID | Description |
|-----------|-------------|
| `binary_sensor.night_charge_scheduled_tonight` | Is charging scheduled for tonight? |
| `binary_sensor.night_charge_active` | Is charging currently active? |

### Buttons

| Entity ID | Description |
|-----------|-------------|
| `button.night_charge_recalculate_plan` | Manually trigger plan recalculation (preview tomorrow's plan now) |

## 🎨 Lovelace Dashboard Example

Here's a beautiful, modern vertical dashboard showcasing all the integration's features:

```yaml
type: vertical-stack
cards:
  # Header Card with Status
  - type: custom:mushroom-template-card
    primary: Nidia Smart Battery
    secondary: >
      {% if is_state('binary_sensor.night_charge_active', 'on') %}
        🔌 Charging Active
      {% elif is_state('binary_sensor.night_charge_scheduled_tonight', 'on') %}
        ⏰ Charging Scheduled Tonight
      {% else %}
        ✓ No Charge Needed
      {% endif %}
    icon: mdi:battery-charging-100
    icon_color: >
      {% if is_state('binary_sensor.night_charge_active', 'on') %}
        green
      {% elif is_state('binary_sensor.night_charge_scheduled_tonight', 'on') %}
        amber
      {% else %}
        blue
      {% endif %}
    tap_action:
      action: more-info

  # Quick Action Button
  - type: custom:mushroom-template-card
    primary: Recalculate Plan
    secondary: Preview tomorrow's charging strategy
    icon: mdi:calculator
    icon_color: purple
    tap_action:
      action: call-service
      service: button.press
      service_data:
        entity_id: button.night_charge_recalculate_plan

  # Tonight's Plan
  - type: custom:mushroom-title-card
    title: Tonight's Plan
    subtitle: What will happen at 23:59

  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: sensor.night_charge_planned_grid_energy_kwh
        name: Planned Charge
        icon: mdi:battery-arrow-up
        icon_color: green

      - type: custom:mushroom-entity-card
        entity: sensor.night_charge_target_soc_percent
        name: Target SOC
        icon: mdi:battery-check
        icon_color: blue

  # Tomorrow's Forecast
  - type: custom:mushroom-title-card
    title: Tomorrow's Forecast
    subtitle: Predicted consumption and solar production

  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: sensor.night_charge_load_forecast_tomorrow_kwh
        name: Consumption
        icon: mdi:home-lightning-bolt
        icon_color: orange

      - type: custom:mushroom-entity-card
        entity: sensor.night_charge_solar_forecast_tomorrow_kwh
        name: Solar
        icon: mdi:solar-power
        icon_color: amber

  # Plan Reasoning
  - type: markdown
    title: 🧠 Algorithm Reasoning
    content: |
      {{ states('sensor.night_charge_plan_reasoning') }}
    card_mod:
      style: |
        ha-card {
          border-radius: 12px;
          border: 2px solid rgba(var(--rgb-primary-color), 0.2);
        }

  # Weekly Consumption Pattern
  - type: custom:mushroom-title-card
    title: Weekly Consumption Pattern
    subtitle: Average consumption by day of the week

  - type: custom:apexcharts-card
    graph_span: 7d
    span:
      start: day
    header:
      show: false
    series:
      - entity: sensor.night_charge_avg_consumption_monday
        name: Mon
        type: column
        color: '#1976d2'
      - entity: sensor.night_charge_avg_consumption_tuesday
        name: Tue
        type: column
        color: '#388e3c'
      - entity: sensor.night_charge_avg_consumption_wednesday
        name: Wed
        type: column
        color: '#f57c00'
      - entity: sensor.night_charge_avg_consumption_thursday
        name: Thu
        type: column
        color: '#7b1fa2'
      - entity: sensor.night_charge_avg_consumption_friday
        name: Fri
        type: column
        color: '#c62828'
      - entity: sensor.night_charge_avg_consumption_saturday
        name: Sat
        type: column
        color: '#00796b'
      - entity: sensor.night_charge_avg_consumption_sunday
        name: Sun
        type: column
        color: '#0097a7'

  # Last Run Summary
  - type: markdown
    title: 📝 Last Run Summary
    content: |
      {{ states('sensor.night_charge_last_run_summary') }}
    card_mod:
      style: |
        ha-card {
          border-radius: 12px;
          background: rgba(var(--rgb-primary-color), 0.05);
        }

  # Configuration
  - type: custom:mushroom-title-card
    title: Configuration
    subtitle: Current algorithm settings

  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: sensor.night_charge_min_soc_reserve_percent
        name: Min Reserve
        icon: mdi:battery-lock
        icon_color: red

      - type: custom:mushroom-entity-card
        entity: sensor.night_charge_safety_spread_percent
        name: Safety Buffer
        icon: mdi:shield-check
        icon_color: green
```

### Alternative: Simple Dashboard (No Custom Cards Required)

If you don't have custom cards installed, here's a clean alternative using only built-in Home Assistant cards:

```yaml
type: vertical-stack
cards:
  # Status Overview
  - type: glance
    title: Night Charge Status
    entities:
      - entity: binary_sensor.night_charge_scheduled_tonight
        name: Scheduled
      - entity: binary_sensor.night_charge_active
        name: Active
      - entity: sensor.night_charge_planned_grid_energy_kwh
        name: Planned
      - entity: sensor.night_charge_target_soc_percent
        name: Target SOC

  # Recalculate Button
  - type: button
    entity: button.night_charge_recalculate_plan
    name: Recalculate Plan Now
    icon: mdi:calculator
    tap_action:
      action: toggle

  # Forecasts
  - type: entities
    title: Tomorrow's Forecast
    entities:
      - entity: sensor.night_charge_load_forecast_tomorrow_kwh
        name: Load Forecast
        icon: mdi:home-lightning-bolt
      - entity: sensor.night_charge_solar_forecast_tomorrow_kwh
        name: Solar Forecast
        icon: mdi:solar-power

  # Plan Details
  - type: markdown
    title: Plan Reasoning
    content: >
      {{ states('sensor.night_charge_plan_reasoning') }}

  # Weekly Pattern
  - type: entities
    title: Weekly Consumption Averages
    entities:
      - sensor.night_charge_avg_consumption_monday
      - sensor.night_charge_avg_consumption_tuesday
      - sensor.night_charge_avg_consumption_wednesday
      - sensor.night_charge_avg_consumption_thursday
      - sensor.night_charge_avg_consumption_friday
      - sensor.night_charge_avg_consumption_saturday
      - sensor.night_charge_avg_consumption_sunday

  # Last Run
  - type: markdown
    title: Last Run Summary
    content: >
      {{ states('sensor.night_charge_last_run_summary') }}

  # Settings
  - type: entities
    title: Configuration
    entities:
      - sensor.night_charge_min_soc_reserve_percent
      - sensor.night_charge_safety_spread_percent
```

### Required Custom Cards (for advanced dashboard)

To use the advanced dashboard example, install these custom cards via HACS:

- [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) - Beautiful, modern card designs
- [ApexCharts Card](https://github.com/RomRider/apexcharts-card) - For the weekly consumption chart
- [Card Mod](https://github.com/thomasloven/lovelace-card-mod) - For styling enhancements (optional)

## 🛠️ Services

### `night_battery_charger.recalculate_plan_now`
Immediately recalculate the charging plan using current data. Useful for testing or after changing settings.

**Example:**
```yaml
service: night_battery_charger.recalculate_plan_now
```

### `night_battery_charger.force_charge_tonight`
Override the algorithm and force charging tonight to 100% SOC, regardless of forecasts.

**Example:**
```yaml
service: night_battery_charger.force_charge_tonight
```

**Use case:** You know tomorrow will be cloudy or you'll have higher than usual consumption.

### `night_battery_charger.disable_tonight`
Prevent any charging tonight, even if the algorithm recommends it.

**Example:**
```yaml
service: night_battery_charger.disable_tonight
```

**Use case:** You want to use all battery capacity for self-consumption or grid export.

## 🔍 Understanding the Plan Reasoning

The `sensor.night_charge_plan_reasoning` provides a human-readable explanation of every decision. Here's how to interpret it:

### Example 1: No Charging Needed
```
Planned 0.00 kWh grid charge. Tomorrow's estimated load is 10.00 kWh,
with 15.51 kWh solar forecast. Target SOC: 16.5%.
```

**Interpretation:**
- Solar production (15.51 kWh) exceeds consumption (10.00 kWh)
- No grid charging needed
- Battery will be recharged by solar during the day
- Target SOC is minimum reserve (16.5% ≈ your configured 15% + small safety margin)

### Example 2: Charging Required
```
Planned 8.50 kWh grid charge. Tomorrow's estimated load is 25.00 kWh,
with 12.00 kWh solar forecast. Target SOC: 85.3%.
```

**Interpretation:**
- Consumption (25 kWh) exceeds solar (12 kWh) by 13 kWh
- Need to charge 8.50 kWh from grid tonight
- This will bring battery to 85.3% SOC
- Accounts for reserve (15%) + safety spread (10%)

### Example 3: Force Charged
```
[FORCED BY USER] Planned 15.00 kWh grid charge. Tomorrow's estimated load is 20.00 kWh,
with 18.00 kWh solar forecast. Target SOC: 100.0%.
```

**Interpretation:**
- User manually forced charging via service
- Will charge to 100% regardless of forecasts
- Overrides normal algorithm logic

## ❓ FAQ

### How long does it take to learn my patterns?
The integration starts learning immediately but needs **at least 3-7 days** of data for each weekday to make accurate forecasts. After 3 weeks, it has comprehensive data for all days of the week.

### What if I don't have a solar forecast sensor?
You can use a static helper sensor with a fixed value (e.g., 0 kWh if you don't have solar, or your average production). The integration will still optimize based on consumption patterns.

### Can I change settings after initial setup?
Yes! Go to **Settings** → **Devices & Services** → **Nidia Smart Battery Recharge** → **Configure** to modify any parameter.

### What happens during the learning phase?
The integration operates conservatively, using the average of all available history. As more data accumulates, forecasts become more accurate and weekday-specific.

### Will it damage my battery?
No. The integration respects your configured **Minimum SOC Reserve** to prevent deep discharges and includes a **Safety Spread** buffer to avoid frequent charge/discharge cycles.

### Can I use it with time-of-use tariffs?
Yes! The integration is designed for this use case. It charges during off-peak hours (23:59-07:00) and minimizes expensive daytime grid usage.

### Does it work with Huawei/Growatt/SolarEdge/Victron inverters?
Yes, as long as your inverter exposes:
1. A switch to enable/disable grid charging
2. A battery SOC sensor
3. Power consumption sensors

The integration is **inverter-agnostic**.

## 🐛 Troubleshooting

### The plan shows "No plan calculated yet"
- Press the **Recalculate Plan** button to trigger an immediate calculation
- Wait until 22:59 for the automatic nightly calculation
- Check that all required sensors are available and have valid values

### Charging doesn't start at 23:59
- Verify the **Inverter Grid Charge Switch** entity is correct
- Check Home Assistant logs for errors
- Ensure the switch is not controlled by other automations
- Verify `binary_sensor.night_charge_scheduled_tonight` is `on`

### Forecasts seem inaccurate
- Ensure at least 7-14 days of learning data
- Check that the **House Load Power Sensor** is measuring correctly (should be in Watts)
- Verify the sensor measures **house load only**, not including solar production
- Review weekly averages in `sensor.night_charge_avg_consumption_*` sensors

### Battery charges to wrong SOC
- Check **Safety Spread** percentage (higher = more charging)
- Review **Minimum SOC Reserve** setting
- Verify **Battery Capacity** is configured correctly
- Read `sensor.night_charge_plan_reasoning` for calculation details

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by the need for smarter home energy management
- Built with ❤️ for the Home Assistant community
- Thanks to all contributors and testers

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/antoniobaldassarre/nidia-smart-battery-recharge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/antoniobaldassarre/nidia-smart-battery-recharge/discussions)
- **Documentation**: [Full Documentation](https://github.com/antoniobaldassarre/nidia-smart-battery-recharge)

---

**Made with ☀️ and 🔋 by the Home Assistant community**
