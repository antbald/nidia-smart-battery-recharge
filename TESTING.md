# Testing Guide - Nidia Smart Battery Recharge

## Automated Tests

### Running Tests

The integration includes comprehensive test suites for all major features:

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/test_v06x_features.py -v

# Run specific test class
python3 -m pytest tests/test_v06x_features.py::TestMinimumConsumptionFallback -v

# Run with coverage
python3 -m pytest tests/ --cov=custom_components.night_battery_charger --cov-report=html
```

### Test Coverage

#### v0.6.x Features Test Suite (`test_v06x_features.py`)

**TestMinimumConsumptionFallback**
- ✅ `test_fallback_applied_when_consumption_low` - Verify fallback when consumption < minimum
- ✅ `test_fallback_not_applied_when_consumption_high` - Verify raw value when consumption >= minimum
- ✅ `test_set_minimum_consumption_fallback` - Verify fallback value can be updated

**TestGetWeekdayAverageMethod**
- ✅ `test_get_weekday_average_method_exists` - Verify public method exists (not private)
- ✅ `test_get_weekday_average_returns_correct_value` - Verify calculation correctness
- ✅ `test_get_weekday_average_no_data_returns_zero` - Verify behavior with no data

**TestConsumptionForecastIntegration**
- ✅ `test_get_consumption_forecast_calls_get_weekday_average` - Verify correct method call
- ✅ `test_main_planning_uses_fallback_protected_forecast` - Verify planning uses fallback

**TestEVIntegration**
- ✅ `test_ev_energy_change_triggers_recalculation` - Verify EV energy triggers replan
- ✅ `test_ev_energy_change_outside_window_ignored` - Verify changes ignored outside window

**TestNumberEntities**
- ✅ `test_ev_energy_number_entity_attributes` - Verify EV Energy entity configuration
- ✅ `test_minimum_consumption_fallback_entity_attributes` - Verify fallback entity config
- ✅ `test_ev_energy_number_triggers_coordinator` - Verify entity calls coordinator
- ✅ `test_minimum_fallback_number_updates_coordinator` - Verify fallback updates

**TestEndToEndScenarios**
- ✅ `test_complete_planning_workflow_with_low_consumption` - Full workflow test
- ✅ `test_complete_ev_integration_workflow` - Full EV integration test

#### EV Integration Test Suite (`test_ev_integration.py`)

**TestEVIntegration**
- ✅ `test_ev_energy_number_creation` - Verify number entity creation
- ✅ `test_bypass_switch_enable` - Verify bypass switch activation
- ✅ `test_bypass_switch_disable` - Verify bypass switch deactivation
- ✅ `test_solar_forecast_today` - Verify today's forecast usage
- ✅ `test_solar_forecast_tomorrow` - Verify tomorrow's forecast usage
- ✅ `test_ev_energy_change_during_window` - Verify recalculation trigger
- ✅ `test_ev_energy_change_outside_window` - Verify no action outside window
- ✅ `test_recalculate_sufficient_energy` - Verify bypass not needed when sufficient
- ✅ `test_recalculate_insufficient_energy` - Verify bypass enabled when insufficient
- ✅ `test_morning_cleanup` - Verify cleanup at 07:00
- ✅ `test_forecast_switching_before_midnight` - Verify tomorrow forecast before 00:00
- ✅ `test_forecast_switching_after_midnight` - Verify today forecast after 00:00

## Manual Testing

### Manual Verification Checklist

After updating to v0.6.4, perform these manual tests:

#### 1. Update Integration
- [ ] HACS → Updates → Nidia Smart Battery Recharge v0.6.4
- [ ] Reload integration or restart Home Assistant

#### 2. Test Recalculate Plan Button
- [ ] Developer Tools → Services
- [ ] Call: `button.press` on `button.night_battery_charger_recalculate_plan`
- [ ] **Expected**: No errors in logs

#### 3. Verify Consumption Fallback
- [ ] Check: `sensor.night_battery_charger_plan_reasoning`
- [ ] **Expected**:
  - If historical data < 10 kWh → "Tomorrow's estimated load is 10.00 kWh"
  - If historical data ≥ 10 kWh → "Tomorrow's estimated load is XX.XX kWh"

#### 4. Verify Logs
- [ ] Settings → System → Logs
- [ ] Search: "Consumption forecast"
- [ ] **Expected** (if data < minimum):
  ```
  WARNING: Consumption forecast 0.92 kWh is below minimum fallback 10.00 kWh, using fallback
  ```

#### 5. Verify Number Entities Visibility
- [ ] Settings → Devices & Services → Nidia Smart Battery Recharge
- [ ] **Expected visible entities**:
  - `number.nidia_smart_battery_recharge_ev_energy`
  - `number.nidia_smart_battery_recharge_minimum_consumption_fallback`

#### 6. Test Minimum Fallback Configuration
- [ ] Set `number.nidia_smart_battery_recharge_minimum_consumption_fallback` to 15.0 kWh
- [ ] Press "Recalculate Plan" button
- [ ] **Expected**: Reasoning shows minimum 15.0 kWh consumption

#### 7. Test EV Integration
- [ ] Set `number.nidia_smart_battery_recharge_ev_energy` to 40.0 kWh during charging window (00:00-07:00)
- [ ] Check logs for "EV energy changed to 40.00 kWh during charging window, triggering recalculation"
- [ ] Verify bypass switch state if energy insufficient

#### 8. Test Scheduled Planning
- [ ] Wait for 22:59 (scheduled planning time)
- [ ] Check logs for "Planning night charge" message
- [ ] Verify reasoning sensor updated with correct consumption (>= minimum)

## Regression Testing

### Known Issues Fixed

#### v0.6.4 - AttributeError Fix
- **Issue**: `'NidiaBatteryManager' object has no attribute '_get_weekday_average'`
- **Test**: Press recalculate button → should NOT raise AttributeError
- **Expected**: Button works without errors

#### v0.6.3 - Fallback Not Applied
- **Issue**: Fallback only worked for EV recalculation, not main planning
- **Test**: Press recalculate with low historical data
- **Expected**: Uses minimum fallback (10 kWh), not raw average (e.g., 0.92 kWh)

#### v0.6.2 - Number Entities Not Visible
- **Issue**: Number entities not appearing in device page
- **Test**: Check device page → entities should be visible
- **Expected**: Both number entities visible and selectable

#### v0.6.1 - No Fallback Protection
- **Issue**: Low historical data caused incorrect charging decisions
- **Test**: Check planning with sparse historical data
- **Expected**: Uses configured minimum, not unrealistically low values

## Performance Testing

### Load Testing

Test with large history datasets:

```python
# Simulate 365 days of history (1 year)
manager._data = {"history": [
    {"weekday": i % 7, "consumption_kwh": 10.0 + (i % 5)}
    for i in range(365)
]}

# Test performance
import time
start = time.time()
consumption = manager._get_consumption_forecast_value(for_today=False)
duration = time.time() - start

# Expected: < 100ms for 365 records
assert duration < 0.1
```

### Memory Testing

Verify no memory leaks during continuous operation:

1. Monitor integration memory usage over 24 hours
2. Trigger multiple recalculations (every 5 minutes)
3. Expected: Stable memory footprint (~10-20 MB)

## Continuous Integration

### Pre-commit Checks

Before committing changes:

```bash
# Syntax validation
python3 -m py_compile custom_components/night_battery_charger/*.py

# Run all tests
python3 -m pytest tests/ -v

# Check code formatting (optional)
black custom_components/night_battery_charger/
```

### Release Checklist

Before creating a new release:

1. [ ] All automated tests passing
2. [ ] Manual verification completed
3. [ ] CHANGELOG.md updated
4. [ ] manifest.json version bumped
5. [ ] No syntax errors in Python files
6. [ ] Translations updated (EN + IT)
7. [ ] Documentation updated if needed

## Troubleshooting Tests

### Test Failures

**pytest not found**
```bash
pip3 install pytest pytest-asyncio
```

**Import errors**
```bash
# Tests require Home Assistant dependencies
# Mock testing is preferred to avoid this
```

**Async test failures**
```bash
# Ensure pytest-asyncio is installed
pip3 install pytest-asyncio
```

## Test Maintenance

### Adding New Tests

When adding new features:

1. Create test file: `tests/test_<feature_name>.py`
2. Follow existing test patterns (mock HA, config entry)
3. Test both success and failure cases
4. Include end-to-end scenario tests
5. Update this TESTING.md with new tests

### Test Best Practices

- ✅ Use mocks for Home Assistant dependencies
- ✅ Test edge cases (no data, invalid data, etc.)
- ✅ Test async operations properly
- ✅ Use descriptive test names
- ✅ Include docstrings explaining what each test verifies
- ✅ Group related tests in classes
- ✅ Use fixtures for common setup
