# HABO Tribe2 Smart Lock for Home Assistant

Custom Home Assistant integration for the HABO Tribe2 Smart Lock cloud service.

This repository contains a Home Assistant config-flow integration for the HABO
Tribe2 cloud API.

## Feature Coverage

Implemented:

- Login with email/password: `POST /account/login`
- Lock discovery: `GET /doorlocks`
- Lock and unlock commands using SmartBox gateway ID, lock address, and the
  Admin PIN returned by the cloud lock list
- Operating mode changes for Normal, Privacy, and Passage
- Door open/closed, connectivity, battery estimate, voltage, and last-seen state
- Additional lock detail sensors for model, serial number, firmware, states, RSSI,
  TX power, runtime counters, and event counters when the cloud provides them
- SmartBox sensors for model, serial number, firmware, state, network details,
  DNS, ZigBee channel, and ZigBee PanID when the cloud provides them
- Recent event log sensors for each lock and SmartBox, with the latest event as
  the sensor state and recent entries as readable attributes
- Diagnostics for connectivity, battery and optional request metadata

Public Habo material describes the Smartbox as the bridge between the Tribe2
lock and cloud service, so the integration stores Smartbox/device identifiers
for each configured lock.

## Data Sources

The integration uses the cloud calls that are known to be safe and useful for
normal Home Assistant operation.

`GET /doorlocks` is used for lock state and lock details. This is the same data
shown by the Doorlock Info view, including model, serial number, firmware,
lock/door/bolt state, operating mode, RSSI, TX power, battery voltage, access
entries, and fingerprint metadata when the cloud provides them.

`GET /doorlocks/{gateway_id}/{lock_addr}/attr?attr=65527` is used for Doorlock
Info counters. The response is decoded into total run time, open time, and
unlock events.

`GET /gw/list` is used for SmartBox identity, firmware, state, ZigBee channel,
and ZigBee PanID.

`GET /gw/{gateway_id}/config/get-ip?nicType=Eth` or `nicType=Wifi` is used for
SmartBox network details. The interface is selected from the SmartBox state when
possible.

`GET /logs/?take=200` is used for recent lock and SmartBox event log sensors.
Each event log sensor shows the latest matching event as its state and exposes
the recent matching entries as attributes.

## Install with Marketplace

Home Assistant 2026.11 and later include [Marketplace](https://www.home-assistant.io/integrations/marketplace/), which replaces HACS.

1. As an administrator, open **Settings > Marketplace**.
2. Select **Add from link**, enter `gustavstrandberg/ha-habotribe2` under **GitHub link**, and select **Add**.
3. If prompted for a type, select **Integration** and then **Add**.
4. Open **HABO Tribe2 Smart Lock** and select **Install**. Confirm the version.
5. Restart Home Assistant.
6. Add **HABO Tribe2 Smart Lock** from
   **Settings > Devices & services > Add integration**.

## Manual install

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

## Diagnostics and troubleshooting

Diagnostics are available from the integration or device menu in Home Assistant.
Diagnostics include connectivity and battery status. The integration options can
also include timestamps, HTTP methods and status codes for the last 20 successful
requests. Existing installations using a custom API address must be re-added
using the official HABO endpoint. Review any existing voice assistant exposure
for the operating mode selector, which can enable Passage mode.

## Implemented cloud calls

```text
POST /account/login
GET /doorlocks
GET /gw/list
GET /gw/{gateway_id}/config/get-ip?nicType={Eth|Wifi}
GET /logs/?take=200
GET /doorlocks/{gateway_id}/{lock_addr}/attr?attr=65527
POST /doorlocks/{gateway_id}/{lock_addr}/lock?pin={admin_pin}
POST /doorlocks/{gateway_id}/{lock_addr}/unlock?pin={admin_pin}&timeout=5000
POST /doorlocks/{gateway_id}/{lock_addr}/attr?attr=65317
```

Operating mode payloads for attribute `65317`:

```text
normal:  "AA=="
privacy: "Ag=="
passage: "BA=="
```

## Releases

The integration version is defined in
`custom_components/habo_tribe2/manifest.json`. GitHub releases use matching
version tags so Marketplace can offer stable updates.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
