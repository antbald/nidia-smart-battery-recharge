# Changelog

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
