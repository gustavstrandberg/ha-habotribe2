# HABO Tribe2 Smart Lock for Home Assistant

Custom Home Assistant integration for the HABO Tribe2 Smart Lock cloud service.

This repository contains a Home Assistant config-flow integration for the HABO
Tribe2 cloud API.

## Feature Coverage

Implemented:

- Login with email/password: `POST /account/login`
- Lock discovery: `GET /doorlocks`
- Lock and unlock commands using SmartBox gateway ID and lock address
- Operating mode changes for Normal, Privacy, and Passage
- Door open/closed, connectivity, battery estimate, voltage, and last-seen state
- Additional lock detail sensors for model, serial number, firmware, states, RSSI,
  TX power, runtime counters, and event counters when the cloud provides them
- SmartBox sensors for model, serial number, firmware, state, network details,
  DNS, ZigBee channel, and ZigBee PanID when the cloud provides them
- Diagnostics with password, PIN, token, and username redacted

Public Habo material describes the Smartbox as the bridge between the Tribe2
lock and cloud service, so the integration stores Smartbox/device identifiers
for each configured lock.

## Install

Copy `custom_components/habo_tribe2` into your Home Assistant config directory:

```text
config/
  custom_components/
    habo_tribe2/
```

Restart Home Assistant, then add **HABO Tribe2 Smart Lock** from
**Settings > Devices & services > Add integration**.

The setup flow asks for:

- Email address
- Password

After login, the integration fetches `/doorlocks` and lets you choose the lock
to add. Add the integration once per lock if the account has multiple locks.

Optional per-lock settings are available from the integration options:

- Command PIN, used only by this integration when sending lock/unlock commands

## Implemented cloud calls

```text
POST /account/login
GET /doorlocks
POST /doorlocks/{gateway_id}/{lock_addr}/lock
POST /doorlocks/{gateway_id}/{lock_addr}/unlock?timeout=5000
POST /doorlocks/{gateway_id}/{lock_addr}/attr?attr=65317
```

If a command PIN is configured in options, lock and unlock commands include it
as `pin={pin}`.

Operating mode payloads for attribute `65317`:

```text
normal:  "AA=="
privacy: "Ag=="
passage: "BA=="
```


## Production test checklist

Start with a lock you can physically access.

1. Install the integration and restart Home Assistant.
2. Add the integration from **Settings > Devices & services**.
3. Verify the lock, door, connected, battery, and operating mode entities appear.
4. Confirm the mobile app and Home Assistant show the same lock/door state.
5. Test refresh-only behavior first by opening/closing the door and waiting for polling.
6. Test `unlock`, then verify the physical door and mobile app state.
7. Test `lock`, then verify the physical door and mobile app state.
8. Test Normal/Privacy/Passage mode changes only when someone is near the lock.
9. Download diagnostics if behavior differs; secrets should be redacted.

Known production-test limits:

- State is cloud polling, not MQTT push, so updates can lag by up to the polling interval.
- Battery percentage is estimated from the `vrm` voltage-like field. Values
  outside a plausible lock battery range are ignored instead of shown as mV.
- HABO sometimes returns code `305` / `Busy`; Home Assistant reports this as a clean service error.
