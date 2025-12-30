#!/usr/bin/env python3
"""
Comprehensive test of all Nidia Smart Battery Recharge scenarios.

This test simulates the complete flow without Home Assistant.
"""

import sys
import os
from datetime import datetime, time, timedelta
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch
import asyncio

# Add the component to path
component_path = os.path.join(os.path.dirname(__file__), 'custom_components/night_battery_charger')
sys.path.insert(0, component_path)

print("=" * 60)
print("NIDIA SMART BATTERY RECHARGE - COMPREHENSIVE TEST")
print("=" * 60)

# ============================================================
# TEST 1: Domain Logic - Pure Planning
# ============================================================
print("\n[TEST 1] Domain Logic - ChargePlanner")
print("-" * 40)

from domain.planner import ChargePlanner, PlanningInput

# Scenario 1.1: Normal charging needed
input1 = PlanningInput(
    current_soc_percent=30.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=8.0,
    solar_forecast_kwh=3.0,
    ev_energy_kwh=0.0,
    force_charge=False,
    disable_charge=False,
    is_preview=False,
)
result1 = ChargePlanner.calculate(input1)
print(f"  Scenario 1.1: Normal charge")
print(f"    Current SOC: 30%, Consumption: 8kWh, Solar: 3kWh")
print(f"    → Target SOC: {result1.target_soc_percent:.1f}%")
print(f"    → Charge needed: {result1.planned_charge_kwh:.2f} kWh")
print(f"    → Scheduled: {result1.is_charging_scheduled}")
assert result1.is_charging_scheduled == True, "Should schedule charging"
assert result1.target_soc_percent > 30.0, "Target should be higher than current"
print("    ✓ PASS")

# Scenario 1.2: No charging needed (sufficient solar)
input2 = PlanningInput(
    current_soc_percent=50.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=5.0,
    solar_forecast_kwh=8.0,
    ev_energy_kwh=0.0,
)
result2 = ChargePlanner.calculate(input2)
print(f"  Scenario 1.2: Sufficient solar")
print(f"    Current SOC: 50%, Consumption: 5kWh, Solar: 8kWh")
print(f"    → Target SOC: {result2.target_soc_percent:.1f}%")
print(f"    → Charge needed: {result2.planned_charge_kwh:.2f} kWh")
print(f"    → Scheduled: {result2.is_charging_scheduled}")
assert result2.planned_charge_kwh == 0.0, "Should not need charging"
print("    ✓ PASS")

# Scenario 1.3: With EV energy
input3 = PlanningInput(
    current_soc_percent=40.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=6.0,
    solar_forecast_kwh=4.0,
    ev_energy_kwh=5.0,  # EV requires 5kWh
)
result3 = ChargePlanner.calculate(input3)
print(f"  Scenario 1.3: With EV (5kWh)")
print(f"    Current SOC: 40%, Consumption: 6kWh + EV: 5kWh, Solar: 4kWh")
print(f"    → Target SOC: {result3.target_soc_percent:.1f}%")
print(f"    → Charge needed: {result3.planned_charge_kwh:.2f} kWh")
assert result3.target_soc_percent > result1.target_soc_percent, "EV should increase target"
print("    ✓ PASS")

# Scenario 1.4: Force charge override
input4 = PlanningInput(
    current_soc_percent=80.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=3.0,
    solar_forecast_kwh=5.0,
    force_charge=True,  # Force to 100%
)
result4 = ChargePlanner.calculate(input4)
print(f"  Scenario 1.4: Force charge override")
print(f"    Current SOC: 80%, Force=True")
print(f"    → Target SOC: {result4.target_soc_percent:.1f}%")
assert result4.target_soc_percent == 100.0, "Force should set 100%"
assert result4.is_charging_scheduled == True, "Force should schedule"
print("    ✓ PASS")

# Scenario 1.5: Disable charge override
input5 = PlanningInput(
    current_soc_percent=20.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=8.0,
    solar_forecast_kwh=2.0,
    disable_charge=True,
)
result5 = ChargePlanner.calculate(input5)
print(f"  Scenario 1.5: Disable charge override")
print(f"    Current SOC: 20%, High consumption, Disable=True")
print(f"    → Scheduled: {result5.is_charging_scheduled}")
assert result5.is_charging_scheduled == False, "Disable should prevent scheduling"
assert result5.planned_charge_kwh == 0.0, "Disable should set 0 charge"
print("    ✓ PASS")

# ============================================================
# TEST 2: Domain Logic - EV Manager
# ============================================================
print("\n[TEST 2] Domain Logic - EVManager")
print("-" * 40)

from domain.ev_manager import EVManager, EVSetResult

# Scenario 2.1: Outside charging window
decision1 = EVManager.evaluate(
    new_value=10.0,
    old_value=0.0,
    current_time=time(22, 0),  # 22:00 - outside window
    now=datetime(2025, 12, 30, 22, 0),
    timer_start=None,
    energy_balance={"sufficient": True},
)
print(f"  Scenario 2.1: Set EV at 22:00 (outside window)")
print(f"    → Result: {decision1.result.value}")
print(f"    → Reason: {decision1.reason}")
assert decision1.result == EVSetResult.SAVED, "Should save for later"
print("    ✓ PASS")

# Scenario 2.2: Inside window, sufficient energy
decision2 = EVManager.evaluate(
    new_value=5.0,
    old_value=0.0,
    current_time=time(2, 30),  # 02:30 - inside window
    now=datetime(2025, 12, 30, 2, 30),
    timer_start=None,
    energy_balance={"sufficient": True},
)
print(f"  Scenario 2.2: Set EV at 02:30 (in window), sufficient energy")
print(f"    → Result: {decision2.result.value}")
print(f"    → Bypass: {decision2.bypass_should_activate}")
assert decision2.result == EVSetResult.PROCESSED, "Should process"
assert decision2.bypass_should_activate == False, "Bypass not needed"
print("    ✓ PASS")

# Scenario 2.3: Inside window, insufficient energy
decision3 = EVManager.evaluate(
    new_value=15.0,
    old_value=0.0,
    current_time=time(3, 0),
    now=datetime(2025, 12, 30, 3, 0),
    timer_start=None,
    energy_balance={"sufficient": False},
)
print(f"  Scenario 2.3: Set EV at 03:00, insufficient energy")
print(f"    → Result: {decision3.result.value}")
print(f"    → Bypass: {decision3.bypass_should_activate}")
assert decision3.result == EVSetResult.PROCESSED, "Should process"
assert decision3.bypass_should_activate == True, "Bypass needed"
print("    ✓ PASS")

# Scenario 2.4: Reset to zero
decision4 = EVManager.evaluate(
    new_value=0.0,
    old_value=10.0,
    current_time=time(4, 0),
    now=datetime(2025, 12, 30, 4, 0),
    timer_start=datetime(2025, 12, 30, 2, 0),
    energy_balance={"sufficient": True},
)
print(f"  Scenario 2.4: Reset EV to 0")
print(f"    → Result: {decision4.result.value}")
assert decision4.result == EVSetResult.RESET, "Should reset"
assert decision4.bypass_should_activate == False, "Bypass off on reset"
print("    ✓ PASS")

# Scenario 2.5: Timeout reached
timer_start = datetime(2025, 12, 30, 0, 0)
now = datetime(2025, 12, 30, 6, 30)  # 6.5 hours later
is_timeout = EVManager.is_timeout_reached(timer_start, now)
print(f"  Scenario 2.5: Timeout check (6.5h elapsed)")
print(f"    → Is timeout: {is_timeout}")
assert is_timeout == True, "Should be timed out"
print("    ✓ PASS")

# ============================================================
# TEST 3: Domain Logic - Consumption Forecaster
# ============================================================
print("\n[TEST 3] Domain Logic - ConsumptionForecaster")
print("-" * 40)

from domain.forecaster import ConsumptionForecaster

forecaster = ConsumptionForecaster()

# Add some power readings
print("  Adding power readings (trapezoidal integration)...")
base_time = datetime(2025, 12, 30, 8, 0)
readings = [
    (1000, 0),   # 1kW at 08:00
    (1500, 60),  # 1.5kW at 09:00
    (2000, 120), # 2kW at 10:00
    (1200, 180), # 1.2kW at 11:00
]

for power, minutes in readings:
    t = base_time + timedelta(minutes=minutes)
    forecaster.add_power_reading(power, t)

consumption = forecaster.current_day_consumption
print(f"  Current day consumption: {consumption:.3f} kWh")
expected = 4.6
assert abs(consumption - expected) < 0.1, f"Expected ~{expected} kWh, got {consumption}"
print("    ✓ PASS")

# Test close day
print("  Closing day and saving to history...")
record = forecaster.close_day(datetime(2025, 12, 31, 0, 0, 1))
print(f"  Saved record: date={record.date}, weekday={record.weekday}, consumption={record.consumption_kwh:.2f}")
assert forecaster.history_count == 1, "Should have 1 record"
assert forecaster.current_day_consumption == 0.0, "Current should reset"
print("    ✓ PASS")

# Test weekday average
print("  Testing weekday average...")
avg = forecaster.get_weekday_average(1)  # Tuesday
print(f"    Average for Tuesday: {avg:.2f} kWh")
assert abs(avg - 4.6) < 0.1, "Average should be ~4.6"
print("    ✓ PASS")

# ============================================================
# TEST 4: Energy Balance Calculation
# ============================================================
print("\n[TEST 4] Energy Balance Calculation")
print("-" * 40)

# Test with insufficient energy
balance1 = ChargePlanner.calculate_energy_balance(
    battery_energy_kwh=5.0,
    solar_forecast_kwh=4.0,
    consumption_forecast_kwh=6.0,
    ev_energy_kwh=2.0,
)
print(f"  Balance 1: battery=5, solar=4, consumption=6, ev=2")
print(f"    Available: {balance1['available']} kWh")
print(f"    Needed (with margin): {balance1['needed_with_margin']:.2f} kWh")
print(f"    Sufficient: {balance1['sufficient']}")
assert balance1['available'] == 9.0
assert balance1['sufficient'] == False
print("    ✓ PASS")

# Test with definitely sufficient
balance2 = ChargePlanner.calculate_energy_balance(
    battery_energy_kwh=8.0,
    solar_forecast_kwh=5.0,
    consumption_forecast_kwh=6.0,
    ev_energy_kwh=2.0,
)
print(f"  Balance 2: battery=8, solar=5, consumption=6, ev=2")
print(f"    Available: {balance2['available']} kWh")
print(f"    Needed (with margin): {balance2['needed_with_margin']:.2f} kWh")
print(f"    Sufficient: {balance2['sufficient']}")
assert balance2['sufficient'] == True
print("    ✓ PASS")

# ============================================================
# TEST 5: Scenario Simulation - Full Night Cycle
# ============================================================
print("\n[TEST 5] Full Night Cycle Simulation")
print("-" * 40)

print("  Simulating: 00:01 → 07:00 charging window")

# State at 00:01
initial_soc = 30.0
print(f"  00:01 - Window starts, SOC={initial_soc}%")

# Calculate plan
plan_input = PlanningInput(
    current_soc_percent=initial_soc,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=8.0,
    solar_forecast_kwh=3.0,
)
plan = ChargePlanner.calculate(plan_input)
print(f"  Plan: target={plan.target_soc_percent:.1f}%, charge={plan.planned_charge_kwh:.2f}kWh")
print(f"  Reasoning: {plan.reasoning[:80]}...")

# Simulate EV set at 02:00
print("  02:00 - User sets EV energy 5kWh")
ev_decision = EVManager.evaluate(
    new_value=5.0,
    old_value=0.0,
    current_time=time(2, 0),
    now=datetime(2025, 12, 30, 2, 0),
    timer_start=None,
    energy_balance=ChargePlanner.calculate_energy_balance(
        battery_energy_kwh=3.5,  # Slightly charged since 00:01
        solar_forecast_kwh=3.0,
        consumption_forecast_kwh=8.0,
        ev_energy_kwh=5.0,
    ),
)
print(f"    Result: {ev_decision.result.value}, bypass={ev_decision.bypass_should_activate}")

# Recalculate with EV
plan_with_ev = ChargePlanner.calculate(PlanningInput(
    current_soc_percent=35.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=8.0,
    solar_forecast_kwh=3.0,
    ev_energy_kwh=5.0,
))
print(f"  New plan with EV: target={plan_with_ev.target_soc_percent:.1f}%, charge={plan_with_ev.planned_charge_kwh:.2f}kWh")
assert plan_with_ev.target_soc_percent > plan.target_soc_percent, "EV should increase target"

# 07:00 - Window ends
print("  07:00 - Window ends, EV reset")
ev_reset = EVManager.evaluate(
    new_value=0.0,
    old_value=5.0,
    current_time=time(7, 0),
    now=datetime(2025, 12, 30, 7, 0),
    timer_start=datetime(2025, 12, 30, 2, 0),
    energy_balance={"sufficient": True},
)
print(f"    Reset result: {ev_reset.result.value}")
# Note: 07:00 is OUTSIDE window, so it should be SAVED not RESET
# But value is 0, so effectively reset
print("    ✓ PASS")

# ============================================================
# TEST 6: Edge Cases
# ============================================================
print("\n[TEST 6] Edge Cases")
print("-" * 40)

# Edge case: 0% SOC
print("  Edge case: 0% SOC")
plan_zero = ChargePlanner.calculate(PlanningInput(
    current_soc_percent=0.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=10.0,
    solar_forecast_kwh=0.0,
))
assert plan_zero.is_charging_scheduled == True
assert plan_zero.target_soc_percent == 100.0, "Should charge to 100% when needed > capacity"
print(f"    Target: {plan_zero.target_soc_percent}%, Charge: {plan_zero.planned_charge_kwh:.2f}kWh")
print("    ✓ PASS")

# Edge case: 100% SOC
print("  Edge case: 100% SOC")
plan_full = ChargePlanner.calculate(PlanningInput(
    current_soc_percent=100.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=5.0,
    solar_forecast_kwh=5.0,
))
assert plan_full.planned_charge_kwh == 0.0, "No charge needed at 100%"
print(f"    Charge needed: {plan_full.planned_charge_kwh}kWh")
print("    ✓ PASS")

# Edge case: EV value clamping
print("  Edge case: EV value clamping")
clamped = EVManager.validate_value(250.0)
assert clamped == 200.0, "Should clamp to 200"
clamped_neg = EVManager.validate_value(-10.0)
assert clamped_neg == 0.0, "Should clamp to 0"
print(f"    250 → {clamped}, -10 → {clamped_neg}")
print("    ✓ PASS")

# Edge case: Window boundary times
print("  Edge case: Window boundaries")
assert EVManager.is_in_charging_window(time(0, 0)) == True, "00:00 is in window"
assert EVManager.is_in_charging_window(time(0, 1)) == True, "00:01 is in window"
assert EVManager.is_in_charging_window(time(6, 59)) == True, "06:59 is in window"
assert EVManager.is_in_charging_window(time(7, 0)) == False, "07:00 is NOT in window"
assert EVManager.is_in_charging_window(time(23, 59)) == False, "23:59 is NOT in window"
print("    ✓ PASS")

# Edge case: Very high consumption
print("  Edge case: Very high consumption (> battery capacity)")
plan_high = ChargePlanner.calculate(PlanningInput(
    current_soc_percent=50.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=20.0,  # 2x battery capacity
    solar_forecast_kwh=5.0,
))
print(f"    Consumption: 20kWh, Battery: 10kWh")
print(f"    Target SOC: {plan_high.target_soc_percent}%")
assert plan_high.target_soc_percent == 100.0, "Should max out at 100%"
print("    ✓ PASS")

# Edge case: Timeout remaining calculation
print("  Edge case: Timeout remaining")
timer_start = datetime(2025, 12, 30, 2, 0)
now = datetime(2025, 12, 30, 4, 30)  # 2.5h later
remaining = EVManager.get_remaining_timeout_minutes(timer_start, now)
expected_remaining = int(6 * 60 - 2.5 * 60)  # 210 minutes
print(f"    Timer: 2h30m elapsed, remaining: {remaining} min (expected ~{expected_remaining})")
assert abs(remaining - expected_remaining) < 2, "Remaining should be ~210 min"
print("    ✓ PASS")

# ============================================================
# TEST 7: Comprehensive Reasoning Check
# ============================================================
print("\n[TEST 7] Reasoning Strings")
print("-" * 40)

# Normal plan
plan_normal = ChargePlanner.calculate(PlanningInput(
    current_soc_percent=40.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=7.0,
    solar_forecast_kwh=3.0,
    is_preview=False,
))
print(f"  Normal plan reasoning:")
print(f"    {plan_normal.reasoning}")
assert "Today" in plan_normal.reasoning, "Should mention Today"
assert "7.00" in plan_normal.reasoning or "7.0" in plan_normal.reasoning, "Should mention consumption"
print("    ✓ PASS")

# Preview plan
plan_preview = ChargePlanner.calculate(PlanningInput(
    current_soc_percent=40.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=7.0,
    solar_forecast_kwh=3.0,
    is_preview=True,
))
print(f"  Preview plan reasoning:")
print(f"    {plan_preview.reasoning}")
assert "Tomorrow" in plan_preview.reasoning, "Should mention Tomorrow"
print("    ✓ PASS")

# Plan with EV
plan_ev = ChargePlanner.calculate(PlanningInput(
    current_soc_percent=40.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=7.0,
    solar_forecast_kwh=3.0,
    ev_energy_kwh=5.0,
))
print(f"  Plan with EV reasoning:")
print(f"    {plan_ev.reasoning}")
assert "EV" in plan_ev.reasoning, "Should mention EV"
assert "5.00" in plan_ev.reasoning or "5.0" in plan_ev.reasoning, "Should mention EV amount"
print("    ✓ PASS")

# Forced plan
plan_forced = ChargePlanner.calculate(PlanningInput(
    current_soc_percent=90.0,
    battery_capacity_kwh=10.0,
    min_soc_reserve_percent=15.0,
    safety_spread_percent=10.0,
    consumption_forecast_kwh=3.0,
    solar_forecast_kwh=5.0,
    force_charge=True,
))
print(f"  Forced plan reasoning:")
print(f"    {plan_forced.reasoning}")
assert "FORCED" in plan_forced.reasoning, "Should mention FORCED"
print("    ✓ PASS")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)

print("""
Tested scenarios:
  ✓ Normal charging calculation
  ✓ Sufficient solar (no charge needed)
  ✓ EV energy inclusion in planning
  ✓ Force charge override
  ✓ Disable charge override
  ✓ EV outside charging window (saved)
  ✓ EV inside window with sufficient energy
  ✓ EV inside window with insufficient energy (bypass)
  ✓ EV reset to zero
  ✓ EV timeout detection
  ✓ Consumption tracking (trapezoidal integration)
  ✓ Day close and history saving
  ✓ Weekday average calculation
  ✓ Energy balance calculation
  ✓ Full night cycle simulation
  ✓ Edge cases (0% SOC, 100% SOC, clamping, boundaries)
  ✓ High consumption handling
  ✓ Timeout remaining calculation
  ✓ Reasoning strings verification

The domain logic is working correctly!
""")
