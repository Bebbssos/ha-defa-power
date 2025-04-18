# DEFA Power Home Assistant Actions

This document describes the actions (services) available in the DEFA Power EV Charger integration for Home Assistant.

## Available Actions

The integration provides several actions that can be called from automations, scripts, or the Developer Tools > Services panel in Home Assistant.

> **Important:** When calling any of these actions, you must specify the target device. The target should be set to the specific connector you want to control, not the overall chargepoint. Each connector is represented as a separate device in Home Assistant.

### Set Current Limit

Action: `defa_power.set_current_limit`

Sets the maximum charging current for the charger.

| Field         | Required | Description              |
| ------------- | -------- | ------------------------ |
| current_limit | Yes      | Current limit in amperes |

### Set Eco Mode

Action: `defa_power.set_eco_mode`

Configures the eco mode settings for optimized charging.

| Field               | Required | Description                          |
| ------------------- | -------- | ------------------------------------ |
| active              | Yes      | Enable or disable eco mode           |
| hours_to_charge     | Yes      | Number of hours required to charge   |
| pickup_time_enabled | Yes      | Enable or disable pickup time        |
| pickup_time_mon     | No       | Pickup time on Monday (0-23 hour)    |
| pickup_time_tue     | No       | Pickup time on Tuesday (0-23 hour)   |
| pickup_time_wed     | No       | Pickup time on Wednesday (0-23 hour) |
| pickup_time_thu     | No       | Pickup time on Thursday (0-23 hour)  |
| pickup_time_fri     | No       | Pickup time on Friday (0-23 hour)    |
| pickup_time_sat     | No       | Pickup time on Saturday (0-23 hour)  |
| pickup_time_sun     | No       | Pickup time on Sunday (0-23 hour)    |

### Start Charging

Action: `defa_power.start_charging`

Starts the charging process.

### Stop Charging

Action: `defa_power.stop_charging`

Stops the charging process.

### Reset Charger

Action: `defa_power.reset_charger`

Resets the charger.

| Field | Required | Description                  |
| ----- | -------- | ---------------------------- |
| type  | Yes      | Reset type: "soft" or "hard" |

## Example Action Call

```yaml
service: defa_power.set_current_limit
target:
  device:
    - device_id: abc123 # ID of the connector device
data:
  current_limit: 16
```

## Finding Device IDs

To find the device ID of your connector:

1. Go to **Settings** > **Devices & Services** in Home Assistant
2. Find and click on the DEFA Power integration
3. Look for the connector device under the integration
4. The device ID can be found in the device details or in the URL when viewing the device
