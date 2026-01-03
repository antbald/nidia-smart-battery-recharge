# Changelog

## 2.2.11 - 2026-01-03

### Fixed

- Weekday average consumption sensors now read from synced history, so dashboard bars show actual values

## 2.2.10 - 2026-01-03

### Fixed

- Consumption tracking sensor now pushes UI updates on new power readings, so dashboard values no longer stick at 0

## 0.9.1 - 2025-12-11

### Fixed

- **CRITICAL**: Fixed bypass evaluation and UPDATE notification when EV set before midnight
  - **Issue**: When EV energy was set before 00:01 (e.g., 23:50), v0.9.0 included it in planning but:
    - ❌ Bypass was NOT evaluated → could fail to activate when energy insufficient
    - ❌ UPDATE notification was NOT sent → user didn't see EV details, bypass status, energy balance
  - **Solution**: When EV detected at 00:01, now triggers full `_recalculate_with_ev()` workflow
  - **Result**: User receives both UPDATE notification (detailed EV info) + START notification (plan summary)
  - **Backward Compatible**: Existing behavior for EV set after 00:01 unchanged

**What You Get Now** (when EV set before 00:01):
- ✅ Bypass correctly evaluated (activates if energy available < energy needed)
- ✅ UPDATE notification with: EV kWh requested, bypass status, energy available/needed, plan comparison
- ✅ START notification with final plan summary
- ✅ Consistent behavior whether EV set at 23:50 or 02:30

**Files Modified**:
- `coordinator.py`: Modified `_start_night_charge_window()` to call `_recalculate_with_ev()` when EV pre-set

## 0.9.0 - 2025-12-11

### Added

- **EV Energy Pre-Planning Support**: System now includes EV energy in initial plan if set before 00:01
  - Added `_get_current_ev_energy()` helper method to read persisted EV entity state
  - Modified `_start_night_charge_window()` to check for existing EV value before planning
  - EV energy values set at 23:50 or any time before midnight are now properly included in the 00:01 plan

- **EV Energy State Restoration**: EV energy value now restored after Home Assistant restart
  - Added restoration logic in `async_init()` to recover persisted EV value
  - Prevents loss of EV planning after HA restarts during the night

### Changed

- **Extended Charging Window**: Charging window extended from 00:01-07:00 to 00:00-07:00
  - Eliminates 59-second gap (00:00:01 to 00:00:59) where EV changes were ignored
  - Modified `is_in_charging_window()` to include midnight minute
  - Updated all related comments and docstrings

### Fixed

- **CRITICAL**: Fixed EV energy not being included when set before midnight
  - **Root Cause**: Coordinator always planned with `include_ev=False` at 00:01, ignoring pre-set values
  - **Impact**: Users setting EV energy before midnight (common automation pattern) had values completely ignored
  - **Solution**: System now proactively reads EV entity state at planning time and after HA restart
  - **Backward Compatible**: No breaking changes - existing behavior for EV set after 00:01 unchanged

### Technical Details

**Files Modified**:
- `coordinator.py`: Added STATE_UNKNOWN/STATE_UNAVAILABLE imports, `_get_current_ev_energy()` method, modified `_start_night_charge_window()` and `async_init()`
- `services/ev_integration_service.py`: Extended charging window to 00:00-07:00

**Test Coverage**:
- Added 9 new unit tests in `tests/test_ev_midnight_fix.py`
- Tests cover: valid/invalid/missing EV states, midnight gap, pre-set EV planning, state restoration

## 0.8.3 - 2025-12-04

### Fixed

- **CRITICAL**: Fixed 500 Internal Server Error and missing UI toggles in config flow (final fix)
  - Changed from `bool` to `cv.boolean` for notification flags
  - `cv.boolean` is Home Assistant's standard config validation type that creates proper UI toggle switches
  - Config flow now loads correctly with visible notification toggles

- **Simplified End Notification**: Removed complex early/normal completion distinction
  - Now shows single unified summary: energy charged, SOC change, duration
  - Removed "Target Raggiunto in Anticipo!" and time saved messages
  - User requested simple summary instead of separate messages per completion type

- **No Notification When No Session**: Skip notification entirely if no charging occurred
  - Removed "Finestra di Carica Terminata" message for no-session cases
  - Notifications only sent after actual charging activity

## 0.8.2 - 2025-12-04

### Fixed

- **CRITICAL**: Fixed 500 Internal Server Error in config flow (second attempt)
  - Changed from `BooleanSelector` to simple `bool` type for notification flags
  - `BooleanSelectorConfig()` not available in all Home Assistant versions
  - Using standard `bool` type ensures maximum compatibility across all HA versions
  - Config flow now loads correctly

## 0.8.1 - 2025-12-04

### Fixed

- **CRITICAL**: Fixed 500 Internal Server Error in config flow
  - Added explicit `BooleanSelectorConfig()` to notification flag selectors
  - Ensures compatibility across Home Assistant versions
  - Config flow now loads correctly

## 0.8.0 - 2025-12-04

### Added

- **Comprehensive Notification System**: 3 types of detailed notifications with individual on/off flags
  - **Start Notification (00:01)**: Sent when system calculates night charge plan
    - Shows charging scheduled: SOC current→target, energy to charge, estimated duration, forecasts, reasoning
    - Shows no charge needed: Current SOC, surplus energy, daily forecasts
  - **Update Notification (00:01-07:00)**: Sent when EV integration changes energy requirements
    - Shows bypass activated: EV energy, energy balance, old→new target, bypass reason
    - Shows sufficient energy: EV energy, old→new target, no bypass needed
  - **End Notification**: Sent when charging completes
    - Early completion: Target reached before 07:00, shows time saved
    - Normal completion: Charging finished at 07:00, full summary with energy charged and duration

- **Configuration Flags**: 3 independent switches to enable/disable each notification type
  - `notify_on_start` - Notify at charge plan calculation (default: True)
  - `notify_on_update` - Notify on EV energy updates (default: True)
  - `notify_on_end` - Notify at charge completion (default: True)
  - All flags available in integration options UI with full translations (EN/IT)

- **NotificationService**: New specialized service for managing notifications
  - Centralized notification logic with best-effort delivery
  - Graceful error handling - failures logged but don't block execution
  - Italian messages with emoji for mobile readability (🔋, 📊, 📈, 🚗, ⚡, ⚠️, ✅)

- **Comprehensive Testing**: Full test coverage for notification system
  - 18 unit tests in `test_notification_service.py`
  - 4 integration tests in `test_coordinator.py`
  - Tests for all notification types, flag handling, and message formatting

### Changed

- **Service Integration**: NotificationService injected into ExecutionService and EVIntegrationService
  - Early completion notifications sent directly from ExecutionService when target reached
  - EV update notifications sent from EVIntegrationService on plan recalculation
  - Clean dependency injection pattern for testability

### Technical Details

- **Files Added**:
  - `custom_components/night_battery_charger/services/notification_service.py` (313 lines)
  - `tests/test_notification_service.py` (554 lines)

- **Files Modified**:
  - `coordinator.py` - Integrated NotificationService, added start notification
  - `execution_service.py` - Added early completion notification support
  - `ev_integration_service.py` - Added EV update notification
  - `config_flow.py` - Added 3 notification flag selectors
  - `const.py` - Added notification flag constants
  - `strings.json`, `translations/en.json`, `translations/it.json` - Added translations
  - `tests/test_coordinator.py` - Added 4 integration tests

### Notes

- **Backward Compatible**: All notification flags default to True, no breaking changes
- **Optional**: Notifications only sent if `notify_service` is configured
- **Best Effort**: Notification failures are logged but don't affect charging operations
- **Mobile Optimized**: Messages formatted with emoji and structured sections for readability

## 0.7.3 - 2025-12-01

### Fixed

- **CRITICAL**: Fixed missing `for_preview` parameter in night charge planning
  - Night charge at 00:01 was not explicitly setting `for_preview=False`
  - This caused incorrect forecast selection and prevented charging from starting
  - Now explicitly sets `for_preview=False` for all real-time operations (00:01-07:00)
  - Preview mode (`for_preview=True`) is only used for manual recalculation button
  - Affected locations:
    - `_start_night_charge_window()` - main 00:01 planning
    - `async_handle_ev_energy_change()` - EV updates during charging window
    - `ev_integration_service._recalculate_with_ev()` - EV recalculations

## 0.7.2 - 2025-12-01

### Fixed

- **Tests**: Updated test suite for new service architecture
  - Fixed test_coordinator.py to use new service-based APIs
  - Updated test_sensor.py with renamed sensors (tomorrow → today)
  - All core functionality tests now passing (18/21 passing)
  - Note: Some advanced EV integration tests may need Home Assistant environment

## 0.7.1 - 2025-12-01

### Fixed

- **Preview Functionality**: Recalculate Plan button now correctly shows forecasts for TOMORROW
  - Previously showed today's forecasts, which was incorrect for preview purposes
  - Users press this button during the day to preview the upcoming night
  - Now uses tomorrow's solar forecast and tomorrow's consumption forecast
  - Reasoning text now says "Tomorrow's estimated load" instead of "Today's" in preview mode
  - Affects: Recalculate Plan button, Force Charge service, Disable Charge service

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
