# Nidia Smart Battery Recharge

<p align="center">
  <img src="https://img.shields.io/badge/version-2.2.11-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/github/license/antoniobaldassarre/nidia-smart-battery-recharge?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/HACS-Custom-orange?style=for-the-badge" alt="HACS">
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.1+-blue?style=for-the-badge" alt="HA Version">
</p>

**Nidia Smart Battery Recharge** is an intelligent Home Assistant integration that optimizes your home battery charging strategy. It learns your household's consumption patterns, considers solar production forecasts, and automatically decides when and how much to charge from the grid during off-peak hours.

## Why Nidia?

If you have a home battery system with solar panels, you face a daily challenge: **how much should I charge from the grid tonight?**

- Charge too little → You'll need expensive daytime grid power
- Charge too much → You waste energy and miss out on solar production
- Charge every night → Unnecessary costs and battery wear

**Nidia solves this** by intelligently analyzing your consumption patterns and solar forecasts to charge exactly what you need, when you need it.

## Key Features

### Adaptive Learning
- Learns your household's consumption patterns over a 3-week rolling window
- Tracks consumption by day of the week (Mondays vs. Sundays have different patterns!)
- Automatically adapts to changing habits and seasonal variations
- Uses trapezoidal integration for accurate energy tracking

### Solar-Aware Planning
- Integrates today's solar production forecast
- Avoids unnecessary charging when solar will cover your needs
- Calculates the exact energy deficit to charge overnight

### Smart Decision Making
- Decides **IF** charging is needed (not blindly charging every night)
- Calculates **HOW MUCH** to charge based on forecasted needs
- Respects battery reserves and safety margins
- Prevents overcharging and battery degradation

### EV Integration (New in v2.0)
- Input EV energy needs for overnight charging
- Automatic bypass control when battery energy is insufficient
- Configurable timeout protection (1-12 hours)
- Visual feedback on EV charging status

### Economic Savings Tracking (New in v2.1)
- Track money saved by charging at night vs daytime rates
- Support for Italian PUN pricing (F1/F2/F3 tiers)
- Monthly and lifetime savings statistics
- Configurable peak/off-peak rates

### Safe & Configurable
- Minimum SOC reserve to protect battery health
- Safety spread buffer for unexpected consumption
- Automatic shutoff at target SOC or morning cutoff time
- Manual override options for special situations

### Complete Visibility
- Real-time sensors for all metrics
- Detailed reasoning explanations for every decision
- Weekday-specific consumption averages
- Last run summaries and notifications
- **Full diagnostic logging** that always works

### One-Click Controls
- Recalculate plan button to preview tonight's strategy
- Force charge tonight button
- Disable charge tonight button
- Debug logging toggle

## Installation

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

## Configuration

The integration uses a friendly **4-step configuration wizard**:

### Step 1: Core Configuration
- **Inverter Grid Charge Switch**: The switch entity that enables/disables grid charging on your inverter
- **Battery Capacity**: Total usable capacity of your battery system (kWh)
- **Battery SOC Sensor**: Sensor showing current battery State of Charge (0-100%)

### Step 2: Sensors Setup
- **House Load Power Sensor**: Sensor measuring instantaneous house consumption in Watts (used for learning daily patterns)
- **Solar Forecast Today**: Sensor providing today's estimated solar production in kWh

### Step 3: Tuning & Notifications
- **Minimum SOC Reserve** (default: 15%): Battery level always preserved, never counted as available for consumption
- **Safety Spread** (default: 10%): Extra buffer percentage added to calculated charging need
- **Notification Service** (optional): Service to receive morning summaries (e.g., `notify.mobile_app_your_phone`)
- **Charging Window Start** (default: 00:00): When the charging window begins
- **Charging Window End** (default: 07:00): When the charging window ends
- **EV Timeout Hours** (default: 6): How long before EV energy request expires

### Step 4: Pricing Configuration (Optional)
- **Pricing Mode**: Two-tier (peak/off-peak) or Three-tier (F1/F2/F3 Italian PUN)
- **Peak Price** (default: €0.25/kWh): Daytime electricity rate
- **Off-Peak Price** (default: €0.12/kWh): Nighttime electricity rate
- **F1/F2/F3 Rates**: For three-tier Italian PUN pricing

### Optional: EV Integration
- **Bypass Switch Entity**: Switch that enables direct grid-to-EV charging when battery is insufficient

## How It Works

### 1. Learning Phase (Continuous)
The integration monitors your **House Load Power Sensor** throughout the day:
- Uses trapezoidal integration for accurate energy calculation
- Stores consumption data by weekday (Monday, Tuesday, etc.)
- Maintains a 3-week rolling history
- Automatically learns your weekly patterns

### 2. Planning & Forecasting Phase (00:01 daily)
Every night at 00:01, the system forecasts today's needs:
- Retrieves historical consumption for today's weekday
- Calculates average consumption from similar past days
- Reads today's solar production forecast from your sensor
- Adds any EV energy requirements
- Calculates the optimal charging strategy:

```
Current Battery Energy = (Current SOC / 100) × Battery Capacity
Reserve Energy = (Min SOC Reserve / 100) × Battery Capacity
Available Energy = Current Battery Energy - Reserve Energy

Net Load = Consumption Forecast + EV Energy - Solar Forecast
Required Energy = Reserve Energy + max(0, Net Load)
Target Energy = Required Energy × (1 + Safety Spread / 100)

Target SOC = min(100%, max(Min SOC Reserve, Target Energy / Battery Capacity × 100))
Charge Needed = max(0, Target Energy - Current Battery Energy)
```

### 3. Execution Phase (00:01 - 07:00)
If charging is needed:
- **00:01**: Turns ON the inverter grid charge switch
- **Monitoring**: Checks battery SOC every minute
- **Auto-shutoff**: Turns OFF when Target SOC is reached OR at 07:00 (whichever comes first)
- **EV Bypass**: If EV energy is requested and battery can't cover it, bypass is activated

### 4. Reporting Phase (07:00)
Every morning:
- Generates a summary of the night's activity
- Updates the "Last Run Summary" sensor
- Sends an optional notification if configured
- Resets EV energy and bypass state
- Starts new consumption tracking day

## Entities Created

### Sensors

| Entity | Description | Unit |
|--------|-------------|------|
| `sensor.nidia_smart_battery_recharge_planned_grid_charge` | Energy planned to charge from grid tonight | kWh |
| `sensor.nidia_smart_battery_recharge_target_soc` | Target battery SOC to reach | % |
| `sensor.nidia_smart_battery_recharge_load_forecast_today` | Forecasted consumption for today | kWh |
| `sensor.nidia_smart_battery_recharge_solar_forecast_today` | Forecasted solar production for today | kWh |
| `sensor.nidia_smart_battery_recharge_last_run_charged_energy` | Actual energy charged in last run | kWh |
| `sensor.nidia_smart_battery_recharge_last_run_summary` | Text summary of last charging session | - |
| `sensor.nidia_smart_battery_recharge_plan_reasoning` | Detailed explanation of current plan | - |
| `sensor.nidia_smart_battery_recharge_min_soc_reserve` | Configured minimum SOC reserve | % |
| `sensor.nidia_smart_battery_recharge_safety_spread` | Configured safety spread | % |
| `sensor.nidia_smart_battery_recharge_current_day_consumption` | Today's tracked consumption so far | kWh |
| `sensor.nidia_smart_battery_recharge_ev_energy_requested` | EV energy requested for tonight | kWh |
| `sensor.nidia_smart_battery_recharge_average_consumption_monday` | Average consumption on Mondays | kWh |
| `sensor.nidia_smart_battery_recharge_average_consumption_tuesday` | Average consumption on Tuesdays | kWh |
| `sensor.nidia_smart_battery_recharge_average_consumption_wednesday` | Average consumption on Wednesdays | kWh |
| `sensor.nidia_smart_battery_recharge_average_consumption_thursday` | Average consumption on Thursdays | kWh |
| `sensor.nidia_smart_battery_recharge_average_consumption_friday` | Average consumption on Fridays | kWh |
| `sensor.nidia_smart_battery_recharge_average_consumption_saturday` | Average consumption on Saturdays | kWh |
| `sensor.nidia_smart_battery_recharge_average_consumption_sunday` | Average consumption on Sundays | kWh |
| `sensor.nidia_smart_battery_recharge_total_savings` | Total money saved by night charging | EUR |
| `sensor.nidia_smart_battery_recharge_monthly_savings` | Current month savings | EUR |
| `sensor.nidia_smart_battery_recharge_lifetime_savings` | All-time savings | EUR |
| `sensor.nidia_smart_battery_recharge_total_energy_charged` | Total energy charged from grid | kWh |
| `sensor.nidia_smart_battery_recharge_peak_price` | Configured peak electricity rate | EUR/kWh |
| `sensor.nidia_smart_battery_recharge_off_peak_price` | Configured off-peak electricity rate | EUR/kWh |
| `sensor.nidia_smart_battery_recharge_charging_window` | Current charging window times | - |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| `binary_sensor.nidia_smart_battery_recharge_charging_scheduled` | Is charging scheduled for tonight? |
| `binary_sensor.nidia_smart_battery_recharge_charging_active` | Is charging currently active? |
| `binary_sensor.nidia_smart_battery_recharge_bypass_active` | Is EV bypass active? |
| `binary_sensor.nidia_smart_battery_recharge_in_charging_window` | Is it currently within 00:00-07:00 window? |
| `binary_sensor.nidia_smart_battery_recharge_ev_timer_active` | Is EV timeout timer running? |

### Number Inputs

| Entity | Description | Range |
|--------|-------------|-------|
| `number.nidia_smart_battery_recharge_ev_energy` | Set EV energy needed tonight | 0-200 kWh |
| `number.nidia_smart_battery_recharge_minimum_consumption_fallback` | Fallback consumption if no history | 0-50 kWh |

### Switches

| Entity | Description |
|--------|-------------|
| `switch.nidia_smart_battery_recharge_debug_logging` | Enable/disable detailed file logging |

### Buttons

| Entity | Description |
|--------|-------------|
| `button.nidia_smart_battery_recharge_recalculate_plan` | Manually trigger plan recalculation |
| `button.nidia_smart_battery_recharge_force_charge_tonight` | Force charge to 100% tonight |
| `button.nidia_smart_battery_recharge_disable_charge_tonight` | Prevent any charging tonight |

## Dashboard Examples

### Modern Dashboard (Mushroom Cards)

A clean, modern dashboard using Mushroom cards:

```yaml
type: vertical-stack
cards:
  # Header with Status
  - type: custom:mushroom-template-card
    primary: Nidia Smart Battery
    secondary: >
      {% if is_state('binary_sensor.nidia_smart_battery_recharge_charging_active', 'on') %}
        Charging Active
      {% elif is_state('binary_sensor.nidia_smart_battery_recharge_charging_scheduled', 'on') %}
        Charging Scheduled Tonight
      {% else %}
        No Charge Needed
      {% endif %}
    icon: mdi:battery-charging-100
    icon_color: >
      {% if is_state('binary_sensor.nidia_smart_battery_recharge_charging_active', 'on') %}
        green
      {% elif is_state('binary_sensor.nidia_smart_battery_recharge_charging_scheduled', 'on') %}
        amber
      {% else %}
        blue
      {% endif %}

  # Action Buttons
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-template-card
        primary: Recalculate
        icon: mdi:refresh
        icon_color: purple
        layout: vertical
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.nidia_smart_battery_recharge_recalculate_plan

      - type: custom:mushroom-template-card
        primary: Force Charge
        icon: mdi:battery-charging-100
        icon_color: green
        layout: vertical
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.nidia_smart_battery_recharge_force_charge_tonight

      - type: custom:mushroom-template-card
        primary: Disable
        icon: mdi:battery-off
        icon_color: red
        layout: vertical
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.nidia_smart_battery_recharge_disable_charge_tonight

  # Tonight's Plan
  - type: custom:mushroom-title-card
    title: Tonight's Plan

  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: sensor.nidia_smart_battery_recharge_planned_grid_charge
        name: Planned
        icon_color: green

      - type: custom:mushroom-entity-card
        entity: sensor.nidia_smart_battery_recharge_target_soc
        name: Target SOC
        icon_color: blue

  # Today's Forecast
  - type: custom:mushroom-title-card
    title: Today's Forecast

  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: sensor.nidia_smart_battery_recharge_load_forecast_today
        name: Consumption
        icon: mdi:home-lightning-bolt
        icon_color: orange

      - type: custom:mushroom-entity-card
        entity: sensor.nidia_smart_battery_recharge_solar_forecast_today
        name: Solar
        icon: mdi:solar-power
        icon_color: amber

  # EV Section
  - type: custom:mushroom-title-card
    title: EV Charging

  - type: horizontal-stack
    cards:
      - type: custom:mushroom-number-card
        entity: number.nidia_smart_battery_recharge_ev_energy
        name: EV Energy
        icon_color: cyan
        display_mode: buttons

      - type: custom:mushroom-entity-card
        entity: binary_sensor.nidia_smart_battery_recharge_bypass_active
        name: Bypass
        icon_color: >
          {{ 'red' if is_state(entity, 'on') else 'grey' }}

  # Economic Savings Section
  - type: custom:mushroom-title-card
    title: Economic Savings

  - type: horizontal-stack
    cards:
      - type: custom:mushroom-template-card
        primary: "€{{ states('sensor.nidia_smart_battery_recharge_monthly_savings') }}"
        secondary: This Month
        icon: mdi:calendar-month
        icon_color: green
        layout: vertical

      - type: custom:mushroom-template-card
        primary: "€{{ states('sensor.nidia_smart_battery_recharge_lifetime_savings') }}"
        secondary: Lifetime
        icon: mdi:piggy-bank
        icon_color: amber
        layout: vertical

      - type: custom:mushroom-template-card
        primary: "{{ states('sensor.nidia_smart_battery_recharge_total_energy_charged') }} kWh"
        secondary: Total Charged
        icon: mdi:battery-charging
        icon_color: blue
        layout: vertical

  # Pricing Info
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: sensor.nidia_smart_battery_recharge_peak_price
        name: Peak Rate
        icon: mdi:currency-eur
        icon_color: red

      - type: custom:mushroom-entity-card
        entity: sensor.nidia_smart_battery_recharge_off_peak_price
        name: Off-Peak Rate
        icon: mdi:currency-eur
        icon_color: green

      - type: custom:mushroom-entity-card
        entity: sensor.nidia_smart_battery_recharge_charging_window
        name: Window
        icon: mdi:clock-outline
        icon_color: purple

  # Plan Reasoning
  - type: markdown
    title: Algorithm Reasoning
    content: |
      {{ states('sensor.nidia_smart_battery_recharge_plan_reasoning') }}

  # Weekly Consumption - Using bar-card
  - type: custom:mushroom-title-card
    title: Weekly Consumption Pattern

  - type: custom:bar-card
    entities:
      - entity: sensor.nidia_smart_battery_recharge_average_consumption_monday
        name: Mon
        color: '#2196F3'
      - entity: sensor.nidia_smart_battery_recharge_average_consumption_tuesday
        name: Tue
        color: '#4CAF50'
      - entity: sensor.nidia_smart_battery_recharge_average_consumption_wednesday
        name: Wed
        color: '#FF9800'
      - entity: sensor.nidia_smart_battery_recharge_average_consumption_thursday
        name: Thu
        color: '#9C27B0'
      - entity: sensor.nidia_smart_battery_recharge_average_consumption_friday
        name: Fri
        color: '#F44336'
      - entity: sensor.nidia_smart_battery_recharge_average_consumption_saturday
        name: Sat
        color: '#009688'
      - entity: sensor.nidia_smart_battery_recharge_average_consumption_sunday
        name: Sun
        color: '#00BCD4'
    max: 30
    height: 30px
    decimal: 0
    positions:
      icon: 'off'
      name: outside
      value: inside
      indicator: 'off'
    unit_of_measurement: kWh
    card_mod:
      style: |
        #states {
          padding-left: 0;
        }
        bar-card-name {
          width: 56px;
          flex: 0 0 56px;
          text-align: left;
          margin-right: 8px;
        }
        bar-card-background {
          flex: 1 1 auto;
        }
        bar-card-value {
          margin-left: auto;
          padding-right: 8px;
          text-align: right;
        }

  # Last Run Summary
  - type: markdown
    title: Last Run Summary
    content: |
      {{ states('sensor.nidia_smart_battery_recharge_last_run_summary') }}
```

### Simple Dashboard (No Custom Cards)

A functional dashboard using only built-in Home Assistant cards:

```yaml
type: vertical-stack
cards:
  # Status Overview
  - type: glance
    title: Nidia Smart Battery Status
    entities:
      - entity: binary_sensor.nidia_smart_battery_recharge_charging_scheduled
        name: Scheduled
      - entity: binary_sensor.nidia_smart_battery_recharge_charging_active
        name: Active
      - entity: sensor.nidia_smart_battery_recharge_planned_grid_charge
        name: Planned
      - entity: sensor.nidia_smart_battery_recharge_target_soc
        name: Target

  # Control Buttons
  - type: horizontal-stack
    cards:
      - type: button
        entity: button.nidia_smart_battery_recharge_recalculate_plan
        name: Recalculate
        icon: mdi:refresh
        tap_action:
          action: toggle

      - type: button
        entity: button.nidia_smart_battery_recharge_force_charge_tonight
        name: Force
        icon: mdi:battery-charging-100
        tap_action:
          action: toggle

      - type: button
        entity: button.nidia_smart_battery_recharge_disable_charge_tonight
        name: Disable
        icon: mdi:battery-off
        tap_action:
          action: toggle

  # EV Energy Input
  - type: entities
    title: EV Charging
    entities:
      - entity: number.nidia_smart_battery_recharge_ev_energy
        name: EV Energy Needed
      - entity: binary_sensor.nidia_smart_battery_recharge_bypass_active
        name: Bypass Active
      - entity: binary_sensor.nidia_smart_battery_recharge_ev_timer_active
        name: EV Timer Active

  # Economic Savings
  - type: glance
    title: Economic Savings
    entities:
      - entity: sensor.nidia_smart_battery_recharge_monthly_savings
        name: Month
      - entity: sensor.nidia_smart_battery_recharge_lifetime_savings
        name: Lifetime
      - entity: sensor.nidia_smart_battery_recharge_total_energy_charged
        name: Charged

  - type: entities
    title: Pricing Configuration
    entities:
      - entity: sensor.nidia_smart_battery_recharge_peak_price
        name: Peak Rate (€/kWh)
        icon: mdi:currency-eur
      - entity: sensor.nidia_smart_battery_recharge_off_peak_price
        name: Off-Peak Rate (€/kWh)
        icon: mdi:currency-eur
      - entity: sensor.nidia_smart_battery_recharge_charging_window
        name: Charging Window
        icon: mdi:clock-outline

  # Forecasts
  - type: entities
    title: Today's Forecast
    entities:
      - entity: sensor.nidia_smart_battery_recharge_load_forecast_today
        name: Load Forecast
        icon: mdi:home-lightning-bolt
      - entity: sensor.nidia_smart_battery_recharge_solar_forecast_today
        name: Solar Forecast
        icon: mdi:solar-power

  # Plan Details
  - type: markdown
    title: Plan Reasoning
    content: >
      {{ states('sensor.nidia_smart_battery_recharge_plan_reasoning') }}

  # Weekly Pattern - Using gauge cards for visual representation
  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.nidia_smart_battery_recharge_average_consumption_monday
        name: Mon
        min: 0
        max: 30
        severity:
          green: 0
          yellow: 15
          red: 25
      - type: gauge
        entity: sensor.nidia_smart_battery_recharge_average_consumption_tuesday
        name: Tue
        min: 0
        max: 30
        severity:
          green: 0
          yellow: 15
          red: 25
      - type: gauge
        entity: sensor.nidia_smart_battery_recharge_average_consumption_wednesday
        name: Wed
        min: 0
        max: 30
        severity:
          green: 0
          yellow: 15
          red: 25
      - type: gauge
        entity: sensor.nidia_smart_battery_recharge_average_consumption_thursday
        name: Thu
        min: 0
        max: 30
        severity:
          green: 0
          yellow: 15
          red: 25

  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.nidia_smart_battery_recharge_average_consumption_friday
        name: Fri
        min: 0
        max: 30
        severity:
          green: 0
          yellow: 15
          red: 25
      - type: gauge
        entity: sensor.nidia_smart_battery_recharge_average_consumption_saturday
        name: Sat
        min: 0
        max: 30
        severity:
          green: 0
          yellow: 15
          red: 25
      - type: gauge
        entity: sensor.nidia_smart_battery_recharge_average_consumption_sunday
        name: Sun
        min: 0
        max: 30
        severity:
          green: 0
          yellow: 15
          red: 25

  # Last Run
  - type: markdown
    title: Last Run Summary
    content: >
      {{ states('sensor.nidia_smart_battery_recharge_last_run_summary') }}

  # Settings
  - type: entities
    title: Configuration
    entities:
      - entity: sensor.nidia_smart_battery_recharge_min_soc_reserve
        name: Min SOC Reserve
      - entity: sensor.nidia_smart_battery_recharge_safety_spread
        name: Safety Spread
      - entity: number.nidia_smart_battery_recharge_minimum_consumption_fallback
        name: Min Consumption Fallback
      - entity: switch.nidia_smart_battery_recharge_debug_logging
        name: Debug Logging
```

### Compact Card (Single Entity Card)

For users who want a minimal footprint:

```yaml
type: entities
title: Nidia Smart Battery
show_header_toggle: false
entities:
  - type: section
    label: Status
  - entity: binary_sensor.nidia_smart_battery_recharge_charging_scheduled
  - entity: binary_sensor.nidia_smart_battery_recharge_charging_active
  - entity: binary_sensor.nidia_smart_battery_recharge_in_charging_window
  - type: section
    label: Tonight's Plan
  - entity: sensor.nidia_smart_battery_recharge_planned_grid_charge
  - entity: sensor.nidia_smart_battery_recharge_target_soc
  - entity: sensor.nidia_smart_battery_recharge_charging_window
  - type: section
    label: Forecast
  - entity: sensor.nidia_smart_battery_recharge_load_forecast_today
  - entity: sensor.nidia_smart_battery_recharge_solar_forecast_today
  - type: section
    label: EV
  - entity: number.nidia_smart_battery_recharge_ev_energy
  - entity: binary_sensor.nidia_smart_battery_recharge_bypass_active
  - type: section
    label: Savings
  - entity: sensor.nidia_smart_battery_recharge_monthly_savings
  - entity: sensor.nidia_smart_battery_recharge_lifetime_savings
  - entity: sensor.nidia_smart_battery_recharge_total_energy_charged
  - type: section
    label: Pricing
  - entity: sensor.nidia_smart_battery_recharge_peak_price
  - entity: sensor.nidia_smart_battery_recharge_off_peak_price
  - type: section
    label: Controls
  - entity: button.nidia_smart_battery_recharge_recalculate_plan
  - entity: button.nidia_smart_battery_recharge_force_charge_tonight
  - entity: button.nidia_smart_battery_recharge_disable_charge_tonight
```

### Required Custom Cards

For the advanced Mushroom dashboard, install via HACS:

- [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) - Beautiful, modern card designs
- [Bar Card](https://github.com/custom-cards/bar-card) - For the weekly consumption visualization

## Understanding the Plan Reasoning

The `sensor.nidia_smart_battery_recharge_plan_reasoning` provides a human-readable explanation of every decision:

### Example 1: No Charging Needed
```
Planned 0.00 kWh grid charge. Today's estimated load is 10.00 kWh,
with 15.51 kWh solar forecast. Target SOC: 16.5%.
```

**Interpretation:**
- Solar production (15.51 kWh) exceeds consumption (10.00 kWh)
- No grid charging needed
- Battery will be recharged by solar during the day

### Example 2: Charging Required
```
Planned 8.50 kWh grid charge. Today's estimated load is 25.00 kWh,
with 12.00 kWh solar forecast. Target SOC: 85.3%.
```

**Interpretation:**
- Consumption (25 kWh) exceeds solar (12 kWh) by 13 kWh
- Need to charge 8.50 kWh from grid tonight
- Accounts for reserve (15%) + safety spread (10%)

### Example 3: With EV Energy
```
Planned 15.00 kWh grid charge (includes 10.00 kWh EV).
Today's estimated load is 20.00 kWh, with 18.00 kWh solar forecast.
Target SOC: 95.0%. Bypass: OFF (battery sufficient).
```

**Interpretation:**
- EV needs 10 kWh
- Battery has enough capacity to cover EV + consumption
- No bypass needed

### Example 4: EV with Bypass
```
Planned 5.00 kWh grid charge (includes 30.00 kWh EV - BYPASS ACTIVE).
Today's estimated load is 15.00 kWh, with 10.00 kWh solar forecast.
Target SOC: 100.0%. Bypass: ON (battery insufficient for EV).
```

**Interpretation:**
- EV needs 30 kWh but battery can only provide ~5 kWh
- Bypass activated - EV charges directly from grid

## EV Charging Feature

The EV integration allows you to specify energy needs for overnight vehicle charging:

### How to Use

1. **Set EV Energy**: Use `number.nidia_smart_battery_recharge_ev_energy` to specify how much energy your EV needs
2. **Automatic Processing**:
   - During charging window (00:00-07:00): Plan is immediately recalculated
   - Outside window: Value is saved for the next charging window
3. **Bypass Logic**: If battery cannot provide enough energy for consumption + EV, the bypass switch activates
4. **Timeout Protection**: A 6-hour timeout ensures the EV value is cleared if not manually reset

### Energy Balance Calculation

The system calculates whether bypass is needed:

```
Available = Battery Capacity × (Current SOC - Reserve SOC) / 100
Net Load = Consumption Forecast - Solar Forecast
Remaining After Load = Available - Net Load
Sufficient for EV = Remaining After Load >= EV Energy × 1.15 (15% margin)
```

## FAQ

### How long does it take to learn my patterns?
The integration starts learning immediately but needs **at least 3-7 days** of data for each weekday to make accurate forecasts. After 3 weeks, it has comprehensive data for all days of the week.

### What if I don't have a solar forecast sensor?
You can use a static helper sensor with a fixed value (e.g., 0 kWh if you don't have solar). The integration will still optimize based on consumption patterns.

### Can I change settings after initial setup?
Yes! Go to **Settings** → **Devices & Services** → **Nidia Smart Battery Recharge** → **Configure** to modify any parameter.

### What happens during the learning phase?
The integration uses the `Minimum Consumption Fallback` value (default: 10 kWh) until enough history is collected.

### Will it damage my battery?
No. The integration respects your configured **Minimum SOC Reserve** to prevent deep discharges and includes a **Safety Spread** buffer.

### Can I use it with time-of-use tariffs?
Yes! The integration is designed for this use case. It charges during off-peak hours (00:01-07:00) and minimizes expensive daytime grid usage.

### Does it work with Huawei/Growatt/SolarEdge/Victron inverters?
Yes, as long as your inverter exposes:
1. A switch to enable/disable grid charging
2. A battery SOC sensor
3. Power consumption sensors

The integration is **inverter-agnostic**.

### How do I check the logs?
1. Enable **Debug Logging** switch
2. Logs are stored in `config/nidia_logs/YYYY/MM/DD/` with daily rotation
3. Check Home Assistant logs for important events (always logged)

## Troubleshooting

### The plan shows "No plan yet"
- Press the **Recalculate Plan** button to trigger an immediate calculation
- Wait until 00:01 for the automatic nightly calculation
- Check that all required sensors are available and have valid values

### Charging doesn't start at 00:01
- Verify the **Inverter Grid Charge Switch** entity is correct
- Check Home Assistant logs for errors
- Ensure the switch is not controlled by other automations
- Verify `binary_sensor.nidia_smart_battery_recharge_charging_scheduled` is `on`

### Forecasts seem inaccurate
- Ensure at least 7-14 days of learning data
- Check that the **House Load Power Sensor** is measuring correctly (should be in Watts)
- Verify the sensor measures **house load only**, not including solar production
- Review weekly averages in the dashboard

### EV bypass not activating
- Check that **Bypass Switch Entity** is configured
- Verify `number.nidia_smart_battery_recharge_ev_energy` has a value > 0
- Check `binary_sensor.nidia_smart_battery_recharge_in_charging_window` is `on`

### Nothing in the logs
- Enable **Debug Logging** switch
- Important events are **always** logged to Home Assistant logs regardless of switch
- Check `config/nidia_logs/` directory for detailed file logs

## Architecture (v2.0)

The v2.0 release features a complete architecture refactoring:

```
custom_components/night_battery_charger/
├── core/
│   ├── state.py      # Single Source of Truth for all state
│   ├── events.py     # Event bus for traceable communication
│   └── hardware.py   # Hardware abstraction with retry logic
├── domain/
│   ├── planner.py    # Pure planning logic (100% testable)
│   ├── ev_manager.py # Pure EV decision logic
│   └── forecaster.py # Consumption learning with trapezoidal integration
├── entities/         # Factory-based entity definitions
├── logging/          # Unified logging (always works)
└── coordinator.py    # Thin orchestration layer
```

Key improvements:
- **Single Source of Truth**: All state in one place
- **Event-driven**: All state changes are logged and traceable
- **Pure domain logic**: Business logic has no Home Assistant dependencies
- **Hardware abstraction**: Retry logic for reliable inverter control
- **Factory-based entities**: Add new sensors with one line of code

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by the need for smarter home energy management
- Built for the Home Assistant community
- Thanks to all contributors and testers

## Support

- **Issues**: [GitHub Issues](https://github.com/antoniobaldassarre/nidia-smart-battery-recharge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/antoniobaldassarre/nidia-smart-battery-recharge/discussions)

---

**Made for the Home Assistant community**
