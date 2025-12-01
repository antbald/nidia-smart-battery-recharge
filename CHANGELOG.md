# Changelog

## 0.7.0 - 2025-12-01

### BREAKING CHANGES

⚠️ **This release contains breaking changes that require manual intervention**

#### 1. Timing Change: 23:59 → 00:01
- **Previous**: Charging planning started at 23:59 (the day before)
- **New**: Charging planning starts at 00:01 (already in the target day)
- **Impact**: More reliable behavior, eliminates bugs with midnight transitions
- **Action Required**: None - timing adjusts automatically

#### 2. Sensor Names Changed: "Tomorrow" → "Today"
- **Previous Sensors**:
  - `sensor.night_charge_load_forecast_tomorrow_kwh`
  - `sensor.night_charge_solar_forecast_tomorrow_kwh`
- **New Sensors**:
  - `sensor.night_charge_load_forecast_today_kwh`
  - `sensor.night_charge_solar_forecast_today_kwh`
- **Impact**: Dashboard configurations using old sensor names will show "unavailable"
- **Action Required**: Update your Lovelace dashboards to use new sensor names (see README.md for updated examples)

#### 3. EV Integration Window Updated
- **Previous**: EV recalculation window was 23:59-07:00
- **New**: EV recalculation window is 00:01-07:00
- **Impact**: EV energy changes between 23:59 and 00:01 will be ignored (minimal impact)
- **Action Required**: None

### Added

- **Modular Service Architecture**: Complete refactoring with specialized services
  - `LearningService`: Manages consumption tracking and historical data
  - `ForecastService`: Handles energy predictions
  - `PlanningService`: Calculates optimal charging strategy
  - `ExecutionService`: Controls inverter and hardware
  - `EVIntegrationService`: Manages EV charging integration
- **Data Models**: Clean DTOs for data transfer between services
- **Better Logging**: More detailed and structured logging throughout
- **Improved Code Organization**: Reduced coordinator from 661 to 368 lines (-44%)

### Changed

- **Timing Schedule**: Charging window now 00:01-07:00 (was 23:59-07:00)
- **Forecast Logic**: Always use current day forecasts (eliminated `use_today` parameter complexity)
- **Code Structure**: Services-based architecture for better maintainability and testing

### Fixed

- **Midnight Transition Bugs**: Eliminated issues with EV updates after midnight
- **Forecast Accuracy**: Predictions now always match the target day
- **Code Complexity**: Reduced coupling and improved separation of concerns

### Upgrading

1. **Backup** your configuration before upgrading
2. **Update** the integration through HACS or manual installation
3. **Restart** Home Assistant
4. **Update dashboards** - replace sensor references: `_tomorrow_kwh` → `_today_kwh`
5. **Verify** sensors are showing data (check Developer Tools → States)

---

## 0.6.5

- **Testing**: Added comprehensive EV time logic verification test suite
  - 353 lines of exhaustive testing covering all time scenarios
  - Verified time logic `use_today = current_time < time(23, 59)` is CORRECT
  - 6 real-world EV charging scenarios tested
  - 11 edge cases verified (23:59, midnight, boundaries)
  - All tests pass - confirms integration works correctly
- **Documentation**: Detailed time logic analysis and troubleshooting guide
  - Explains how forecast switching works (today vs tomorrow)
  - Diagnostic steps for troubleshooting EV integration issues
  - Log analysis guide for identifying sensor problems

## 0.6.4

- **Fix**: Critical bug fix for v0.6.3 - method name mismatch causing runtime error
  - Fixed `AttributeError: 'NidiaBatteryManager' object has no attribute '_get_weekday_average'`
  - Changed call from `self._get_weekday_average()` to `self.get_weekday_average()`
  - Recalculate Plan button now works correctly

## 0.6.3

- **Fix**: Minimum consumption fallback now properly applied in main planning logic
  - Fixed regression where fallback was only applied during EV recalculation
  - Main planning (button press, scheduled 22:59) now uses fallback-protected forecast
  - Removed redundant `_calculate_load_forecast()` method
  - Unified consumption forecast logic to use `_get_consumption_forecast_value()` everywhere
  - When historical consumption < minimum threshold, system now correctly uses fallback value
  - Warning logged when fallback is applied for transparency

## 0.6.2

- **Fix**: Number entities now properly visible in Home Assistant UI
  - Removed manual `entity_id` assignment that conflicted with `has_entity_name`
  - Added explicit `entity_category = None` to ensure entities appear in main UI
  - Entities now correctly discoverable by other integrations and automations

## 0.6.1

- **New**: `number.night_battery_charger_minimum_consumption_fallback` entity for consumption forecast protection
  - Configurable minimum consumption threshold (default: 10 kWh)
  - User-adjustable range: 0-50 kWh in 0.5 kWh steps
  - Automatically applied when historical consumption forecast is below threshold
  - Prevents incorrect charging decisions when insufficient historical data is available
- **Fix**: Consumption forecast now uses fallback value when historical data is missing or too low
  - Logged warning when fallback is applied for transparency
  - Ensures safe operation during initial setup or data gaps

## 0.6.0

- **New**: `number.night_charge_ev_energy` entity for external load integration (e.g., EV charging)
  - Writable by external integrations to communicate additional energy needs during the night
  - Automatically triggers recalculation when value changes during charging window (23:59-07:00)
  - Resets to 0 at 07:00 each morning
- **New**: Dynamic recalculation during night (23:59-07:00)
  - System monitors EV energy sensor and recalculates charging plan automatically
  - Adjusts target SOC and bypass switch based on new energy requirements
- **New**: Battery bypass switch support (optional configuration)
  - Prevents battery discharge when activated
  - Automatically enabled when insufficient energy for home + EV loads
  - Automatically disabled at 07:00
- **New**: Solar forecast today sensor (required configuration)
  - Used for recalculations after midnight (00:00-07:00)
  - Ensures accurate planning when operating in the target day
- **Improvement**: Forecast switching at midnight
  - Before midnight: uses tomorrow's solar forecast and tomorrow's consumption
  - After midnight: uses today's solar forecast and today's consumption
  - Provides accurate recalculations regardless of time
- **Documentation**: Added EV integration guide in README with automation examples

## 0.5.2

- **New**: Added `sensor.night_charge_current_day_consumption_kwh` to track real-time daily consumption
  - Shows the energy consumed so far today (resets at midnight)
  - Updates automatically as the house load sensor changes
  - Useful for verifying the integration is learning consumption patterns
  - Helps understand if the tracking system is working correctly

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
