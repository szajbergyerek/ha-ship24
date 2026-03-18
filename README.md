# Ship24 Package Tracker — Home Assistant Integration

Track your packages directly in Home Assistant using the [Ship24](https://ship24.com) API.

---

## Features

- Track unlimited packages via Ship24's universal tracking API
- Each package becomes a **sensor entity** with:
  - State: current delivery status (e.g. *In Transit*, *Delivered*)
  - Attributes: tracking number, courier, last event, last location, ETA, full event history
- **Voice assistant ready** — ask Assist / Google / Alexa about all your packages at once
- **`sensor.ship24_package_summary`** — a single sensor whose state is a spoken summary of all packages
- **Dashboard cards** — use Entities, Glance, or Mushroom cards
- **Services** to add/remove packages from automations
- Polling interval: 1 hour

---

## Installation

1. Download or clone this repository
2. Copy the `custom_components/ship24/` folder into your Home Assistant config directory:
   ```
   <ha-config>/custom_components/ship24/
   ```
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration**
5. Search for **Ship24** and follow the setup wizard

---

## Setup

The setup wizard only asks for one thing: your **Ship24 API key**.

Get your key at [app.ship24.com/settings/api](https://app.ship24.com/settings/api).

---

## Adding Packages

### Via the UI (recommended)

1. **Settings → Devices & Services → Ship24 → Configure**
2. Enter one package per line, with an optional friendly name:
   ```
   1Z999AA10123456784:Amazon Order
   RR123456789CN:AliExpress Shoes
   JD014600000000
   ```
3. Click **Submit** — HA reloads and creates sensor entities

The friendly name is shown in the UI and used by voice assistants instead of the tracking number.

### Via Service Call

```yaml
service: ship24.add_package
data:
  tracking_number: "1Z999AA10123456784"
  friendly_name: "Amazon Order"   # optional
```

```yaml
service: ship24.remove_package
data:
  tracking_number: "1Z999AA10123456784"
```

---

## Voice Assistant

Every package is tracked by a sensor (e.g. `sensor.amazon_order` if you set a friendly name).

There is also a **summary sensor** — `sensor.ship24_package_summary` — whose state is a complete spoken description of all packages:

> *"You have 3 packages. Amazon Order is In Transit, last seen in Frankfurt. AliExpress Shoes is Delivered. Package JD014... is Pending."*

### Asking with HA Assist

Add this to your `configuration.yaml` to respond to "where are my packages?":

```yaml
intent_script:
  WhereAreMyPackages:
    speech:
      text: "{{ states('sensor.ship24_package_summary') }}"

conversation:
  intents:
    WhereAreMyPackages:
      - "where are my packages"
      - "where is my package"
      - "what is the status of my packages"
      - "track my packages"
```

### TTS Automation Example

```yaml
automation:
  - alias: "Announce package status"
    trigger:
      - platform: time
        at: "09:00:00"
    condition:
      - condition: template
        value_template: "{{ states('sensor.ship24_package_summary') != 'You have no tracked packages.' }}"
    action:
      - service: tts.speak
        data:
          message: "{{ states('sensor.ship24_package_summary') }}"
```

### Notify on Delivery

```yaml
automation:
  - alias: "Notify when package delivered"
    trigger:
      - platform: state
        entity_id: sensor.amazon_order
        to: "Delivered"
    action:
      - service: notify.mobile_app
        data:
          message: "{{ state_attr('sensor.amazon_order', 'friendly_name') or 'Your package' }} has been delivered!"
```

---

## Sensor Reference

### `sensor.ship24_package_summary`

| Field | Example |
|-------|---------|
| **State** | `You have 2 packages. Amazon Order is In Transit...` |
| `spoken_summary` | Full text (no 255-char limit) |
| `package_count` | `2` |

### `sensor.ship24_<tracking_number>` (per package)

| Field | Example |
|-------|---------|
| **State** | `In Transit` |
| `tracking_number` | `1Z999AA10123456784` |
| `friendly_name` | `Amazon Order` |
| `courier` | `ups` |
| `last_event` | `Departed facility` |
| `last_event_time` | `2024-03-15T14:30:00.000Z` |
| `last_location` | `Frankfurt, DE` |
| `estimated_delivery` | `2024-03-16T00:00:00.000Z` |
| `origin_country` | `US` |
| `destination_country` | `DE` |
| `events` | list of last 10 events |

---

## Supported Status Values

| Status Code | Display |
|-------------|---------|
| `pending` | Pending |
| `info_received` | Info Received |
| `in_transit` | In Transit |
| `out_for_delivery` | Out for Delivery |
| `failed_attempt` | Failed Delivery Attempt |
| `available_for_pickup` | Available for Pickup |
| `delivered` | Delivered |
| `exception` | Exception |
| `expired` | Expired |

---

## Requirements

- Home Assistant 2023.1.0+
- Ship24 API key ([free tier available](https://ship24.com/pricing))
