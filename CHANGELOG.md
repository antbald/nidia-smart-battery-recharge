# Changelog

## 0.5.1

- **New**: Added button entity `button.night_charge_recalculate_plan` to manually trigger plan calculation
  - Allows you to preview what the integration will do tomorrow with current data
  - Useful for testing and understanding the algorithm's decisions
  - Updates `sensor.night_charge_plan_reasoning` immediately when pressed
- **Testing**: Added 2 new tests for button entity (21 total tests, all passing)
- **Translations**: Added button translations for English and Italian

## 0.5.0

- **New**: Added 7 new sensors showing average consumption for each day of the week (Monday through Sunday)
  - `sensor.night_charge_avg_consumption_monday`
  - `sensor.night_charge_avg_consumption_tuesday`
  - `sensor.night_charge_avg_consumption_wednesday`
  - `sensor.night_charge_avg_consumption_thursday`
  - `sensor.night_charge_avg_consumption_friday`
  - `sensor.night_charge_avg_consumption_saturday`
  - `sensor.night_charge_avg_consumption_sunday`
- **Testing**: Comprehensive test suite added with 19 tests covering:
  - Multi-step configuration flow
  - Sensor and binary sensor creation
  - Integration setup and teardown
  - Service handlers
  - Coordinator business logic
- **Testing**: Enhanced fixtures for better integration testing
- **Improvement**: Code organization improved for better maintainability

## 0.4.1

- **Note**: The sensor selector already accepts all sensor entities (no device_class filter). If you can't see your combined/helper sensors in the dropdown:
  1. Restart Home Assistant completely to reload the integration
  2. Clear your browser cache (Ctrl+F5 or Cmd+Shift+R)
  3. Delete and re-add the integration if the issue persists
- **Clarification**: Combined sensors (like those created with "Combine state of multiple entities" helper) should be visible as long as they have `domain: sensor`.

## 0.4.0

- **Fix**: Removed `device_class="power"` filter from house load sensor to allow selecting any sensor including helpers.
- **Improvement**: Notification service now uses a dropdown selector showing all available notify services instead of manual text input.
- **Important**: After updating, you MUST restart Home Assistant to reload the config flow code.

## 0.3.1

- **Fix**: Config flow completely rewritten following the working pattern from ha-ev-smart-charger.
- **Fix**: Multi-step wizard now works correctly with instance attributes instead of _data dictionary.
- **Fix**: Step indicators (1/3, 2/3, 3/3) now display correctly.

## 0.3.0

- **Fix**: Config flow now correctly shows multi-step wizard (Core → Sensors → Tuning).
- **New**: Added Italian translation (it.json) for Italian users.
- **New**: Added strings.json for proper translation support.
- **Improvement**: Field descriptions now appear correctly under each input field.

## 0.2.2

- **UI Improvement**: Added detailed descriptions for every configuration field in the UI.

## 0.2.1

- **UI Improvement**: Used native Home Assistant selectors (Sliders, Boxes) for numeric inputs in Config and Options flow.
- **UI Improvement**: Added units of measurement to configuration fields.

## 0.2.0

- **New**: Added `sensor.night_charge_plan_reasoning` to explain the algorithm's decision.
- **Improvement**: Redesigned Config Flow with multiple steps (Core, Sensors, Tuning) and better descriptions.
- **Docs**: Updated README with a better Dashboard example.

## 0.1.0

- Initial release.
- Core logic for learning, forecasting, and planning.
- Config flow and options flow.
- Sensors and binary sensors.
- Services for manual control.
