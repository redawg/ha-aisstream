# AISstream Vessel Tracker

A Home Assistant custom integration that tracks vessels in real-time using the [AISstream.io](https://aisstream.io) WebSocket API.

Each tracked vessel appears as a `device_tracker` entity on your Home Assistant map, with position, speed, heading, and voyage data updated live as AIS messages are received.

[![HACS Action](https://github.com/redawg/ha-aisstream/actions/workflows/action.yml/badge.svg)](https://github.com/redawg/ha-aisstream/actions/workflows/action.yml)
[![Validate with hassfest](https://github.com/redawg/ha-aisstream/actions/workflows/hassfest.yml/badge.svg)](https://github.com/redawg/ha-aisstream/actions/workflows/hassfest.yml)

---

## Features

- Real-time vessel tracking via a persistent WebSocket connection
- One `device_tracker` entity per MMSI, shown on the Home Assistant map
- Automatic reconnection with exponential backoff if the connection drops
- Entity attributes populated from both `PositionReport` and `ShipStaticData` AIS messages:

| Attribute | Description |
|---|---|
| `sog` | Speed over ground (knots) |
| `cog` | Course over ground (degrees) |
| `true_heading` | True heading (degrees) |
| `navigational_status` | AIS navigational status code |
| `rate_of_turn` | Rate of turn |
| `call_sign` | Vessel call sign |
| `ship_type` | AIS ship type code |
| `destination` | Declared destination port |
| `eta` | Estimated time of arrival |
| `draught` | Maximum static draught (metres) |
| `imo` | IMO vessel number |

---

## Requirements

- A free [AISstream.io](https://aisstream.io) account and API key
- The MMSI number(s) of the vessel(s) you want to track
- Home Assistant 2023.1 or later

> **Note on coverage:** AISstream.io primarily uses terrestrial (land-based) AIS receivers with a range of roughly 40–60 nautical miles from shore. Vessels in open ocean or mid-sea positions may not appear until they approach a coastline.

---

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → **⋮** → **Custom repositories**
3. Add `https://github.com/redawg/ha-aisstream` with category **Integration**
4. Search for **AISstream** and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/aisstream/` folder into your Home Assistant config's `custom_components/` directory
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **AISstream**
3. Enter your API key and one or more MMSI numbers (comma-separated)

To find an MMSI, look up the vessel on [MarineTraffic](https://www.marinetraffic.com) or [VesselFinder](https://www.vesselfinder.com) and note the 9-digit MMSI from its details page.

---

## Finding an active vessel

If a vessel shows no updates, it is most likely outside terrestrial AIS receiver range. Check [MarineTraffic](https://www.marinetraffic.com) to confirm the vessel's current position — if it is mid-ocean, wait until it approaches a port or coastline.

Areas with especially dense coverage where updates are near-continuous:
- English Channel
- North Sea
- Singapore Strait
- US East Coast ports (New York, Baltimore, Savannah)

---

## License

MIT
