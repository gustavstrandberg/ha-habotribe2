"""Tests for the HABO Tribe2 API helpers."""

from __future__ import annotations

import asyncio
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types
import unittest


def load_api_module():
    """Load api.py without requiring Home Assistant or httpx to be installed."""

    httpx = types.ModuleType("httpx")

    class HTTPError(Exception):
        pass

    class TimeoutException(HTTPError):
        pass

    class ConnectError(HTTPError):
        pass

    class HTTPStatusError(HTTPError):
        pass

    class AsyncClient:
        def __init__(self, *args, **kwargs):
            pass

    httpx.HTTPError = HTTPError
    httpx.TimeoutException = TimeoutException
    httpx.ConnectError = ConnectError
    httpx.HTTPStatusError = HTTPStatusError
    httpx.AsyncClient = AsyncClient
    sys.modules["httpx"] = httpx

    path = Path(__file__).parents[1] / "custom_components/habo_tribe2/api.py"
    spec = spec_from_file_location("habo_tribe2_api_test", path)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, data="Ok", status_code=200):
        self._data = data
        self.status_code = status_code
        self.content = b"{}"

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeHttpClient:
    def __init__(self, responses=None):
        self.requests = []
        self._responses = list(responses or [])

    async def request(self, method, url, headers=None, **kwargs):
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "kwargs": kwargs,
            }
        )
        if self._responses:
            return self._responses.pop(0)
        return FakeResponse()


class ApiParsingTest(unittest.TestCase):
    def setUp(self):
        self.api = load_api_module()

    def test_implausible_battery_voltage_is_ignored(self):
        lock = self.api._parse_lock_state(
            {
                "id": 1,
                "gatewayId": "gateway-1",
                "name": "Front Door",
                "info": {
                    "addr": 123,
                    "lockState": 1,
                    "doorState": 0,
                    "boltState": 1,
                    "opMode": 0,
                    "schMode": 0,
                    "vrm": 21352,
                },
            }
        )

        self.assertIsNone(lock.voltage_mv)
        self.assertIsNone(lock.battery_level)

    def test_reasonable_battery_voltage_is_used(self):
        lock = self.api._parse_lock_state(
            {
                "id": 1,
                "gatewayId": "gateway-1",
                "name": "Front Door",
                "info": {
                    "addr": 123,
                    "lockState": 1,
                    "doorState": 0,
                    "boltState": 1,
                    "opMode": 0,
                    "schMode": 0,
                    "vrm": 4968,
                },
            }
        )

        self.assertEqual(lock.voltage_mv, 4968)
        self.assertIsInstance(lock.battery_level, int)

    def test_gateway_data_is_attached_to_lock(self):
        lock = self.api._parse_lock_state(
            {
                "id": 1,
                "gatewayId": "gateway-1",
                "name": "Front Door",
                "info": {
                    "addr": 123,
                    "lockState": 1,
                    "doorState": 0,
                    "boltState": 1,
                    "opMode": 0,
                    "schMode": 0,
                    "vrm": 6556,
                },
            }
        )
        gateway = self.api._parse_gateway_state(
            {
                "id": "gateway-1",
                "name": "HABO SmartBox",
                "serialNumber": "HG11ZB0122020185",
                "mqttPayload": {
                    "model": "HABO SmartBox V1",
                    "firmwareVersion": 68159766,
                    "state": "OnlineWifi",
                    "channel": 14,
                    "panID": 40785,
                },
            }
        )

        self.api._with_gateway(lock, gateway)

        self.assertEqual(lock.smartbox.name, "HABO SmartBox")
        self.assertEqual(lock.smartbox.model, "HABO SmartBox V1")
        self.assertEqual(lock.smartbox.firmware_version, "1.1.0.2326")
        self.assertEqual(lock.smartbox.zigbee_channel, 14)
        self.assertEqual(lock.smartbox.zigbee_pan_id, "9F51")

    def test_gateway_firmware_version_is_decoded(self):
        gateway = self.api._parse_gateway_state(
            {
                "id": "gateway-1",
                "mqttPayload": {
                    "firmwareVersion": 70271976,
                },
            }
        )

        self.assertEqual(gateway.firmware_version, "1.3.1.1000")

    def test_gateway_pan_id_is_formatted_as_hex(self):
        gateway = self.api._parse_gateway_state(
            {
                "id": "gateway-1",
                "mqttPayload": {
                    "panID": 54302,
                },
            }
        )

        self.assertEqual(gateway.zigbee_pan_id, "D41E")

    def test_gateway_ip_config_populates_network_sensors(self):
        gateway = self.api._parse_gateway_state({"id": "gateway-1"})

        self.api._with_gateway_ip_config(
            gateway,
            self.api._parse_gateway_ip_config(
                {
                    "isStatic": False,
                    "addressString": "192.168.10.27",
                    "subnetMaskString": "255.255.255.0",
                    "gatewayString": "192.168.10.1",
                    "dnS1String": "192.168.10.1",
                    "dnS2String": "0.0.0.0",
                }
            ),
        )

        self.assertEqual(gateway.mode, "dhcp")
        self.assertEqual(gateway.address, "192.168.10.27")
        self.assertEqual(gateway.subnet, "255.255.255.0")
        self.assertEqual(gateway.gateway, "192.168.10.1")
        self.assertEqual(gateway.dns_main, "192.168.10.1")
        self.assertEqual(gateway.dns_backup, "0.0.0.0")

    def test_gateway_nic_type_uses_wifi_for_wifi_state(self):
        wifi_gateway = self.api._parse_gateway_state(
            {
                "id": "gateway-1",
                "mqttPayload": {"state": "OnlineWifi"},
            }
        )
        ethernet_gateway = self.api._parse_gateway_state(
            {
                "id": "gateway-2",
                "mqttPayload": {"state": "OnlineEth"},
            }
        )

        self.assertEqual(self.api._gateway_nic_type(wifi_gateway), "Wifi")
        self.assertEqual(self.api._gateway_nic_type(ethernet_gateway), "Eth")

    def test_lock_info_attr_populates_runtime_counters(self):
        lock = self.api._parse_lock_state(
            {
                "id": 1,
                "gatewayId": "gateway-1",
                "name": "Front Door",
                "info": {
                    "addr": 123,
                    "lockState": 1,
                    "doorState": 0,
                    "boltState": 1,
                    "opMode": 0,
                    "schMode": 0,
                    "vrm": 6556,
                },
            }
        )

        self.api._with_lock_info(
            lock,
            self.api._parse_lock_info_attr("S1JRAVcnEQByBAAAvQYAAA=="),
        )

        self.assertEqual(lock.total_run_time, 22106699)
        self.assertEqual(lock.open_time, 1124183)
        self.assertEqual(lock.unlock_events, 1138)

    def test_lock_last_seen_uses_child_updates_when_missing_on_lock(self):
        lock = self.api._parse_lock_state(
            {
                "id": 1,
                "gatewayId": "gateway-1",
                "name": "Front Door",
                "info": {
                    "addr": 123,
                    "lockState": 1,
                    "doorState": 0,
                    "boltState": 1,
                    "opMode": 0,
                    "schMode": 0,
                    "vrm": 6556,
                },
                "openings": [
                    {"lastUpdate": "2026-05-27T08:00:00"},
                    {"lastUpdate": "2026-05-27T09:00:00"},
                ],
                "fingerprints": [
                    {"lastUpdate": "2026-05-27T08:30:00"},
                ],
            }
        )

        self.assertEqual(lock.last_seen, "2026-05-27T09:00:00")

    def test_admin_pin_is_read_from_admin_opening(self):
        lock = self.api._parse_lock_state(
            {
                "id": 1,
                "gatewayId": "gateway-1",
                "name": "Front Door",
                "info": {
                    "addr": 123,
                    "lockState": 1,
                    "doorState": 0,
                    "boltState": 1,
                    "opMode": 0,
                    "schMode": 0,
                    "vrm": 6556,
                },
                "openings": [
                    {"doorlockUserId": 42, "pin": "111111"},
                    {"doorlockUserId": 0, "pin": "123456"},
                ],
            }
        )

        self.assertEqual(lock.admin_pin, "123456")

    def test_lock_and_unlock_send_admin_pin(self):
        fake_client = FakeHttpClient()
        client = self.api.HaboTribe2Client(
            base_url="https://example.test/api/v1",
            username="user@example.test",
            password="secret",
            client=fake_client,
        )
        client._token = "token"

        asyncio.run(client.async_lock("gateway-1", 123, pin="123456"))
        asyncio.run(client.async_unlock("gateway-1", 123, pin="123456"))

        lock_request = fake_client.requests[0]
        unlock_request = fake_client.requests[1]

        self.assertEqual(lock_request["kwargs"]["params"], {"pin": "123456"})
        self.assertEqual(unlock_request["kwargs"]["params"], {"timeout": 5000, "pin": "123456"})

    def test_api_response_logging_is_disabled_by_default(self):
        fake_client = FakeHttpClient([FakeResponse({"state": "ok"})])
        client = self.api.HaboTribe2Client(
            base_url="https://example.test/api/v1",
            username="user@example.test",
            password="secret",
            client=fake_client,
        )
        client._token = "token"

        data = asyncio.run(client._request("GET", "/doorlocks"))

        self.assertEqual(data, {"state": "ok"})
        self.assertEqual(client.recent_json_responses, [])

    def test_api_response_logging_keeps_latest_json_responses(self):
        fake_client = FakeHttpClient(
            [
                FakeResponse({"first": True}),
                FakeResponse(
                    {
                        "second": True,
                        "token": "secret-token",
                        "openings": [{"pin": "123456"}],
                    }
                ),
            ]
        )
        client = self.api.HaboTribe2Client(
            base_url="https://example.test/api/v1",
            username="user@example.test",
            password="secret",
            client=fake_client,
            enable_response_logging=True,
            response_log_limit=1,
        )
        client._token = "token"

        asyncio.run(client._request("GET", "/doorlocks", params={"take": 1}))
        asyncio.run(client._request("GET", "/logs/", params={"take": 2}))

        responses = client.recent_json_responses
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["method"], "GET")
        self.assertEqual(responses[0]["path"], "/logs/")
        self.assertEqual(responses[0]["params"], {"take": 2})
        self.assertEqual(responses[0]["status_code"], 200)
        self.assertEqual(
            responses[0]["response"],
            {
                "second": True,
                "token": "**REDACTED**",
                "openings": [{"pin": "**REDACTED**"}],
            },
        )
        self.assertIn("timestamp", responses[0])

    def test_event_logs_are_filtered_for_lock_and_gateway(self):
        lock = self.api._parse_lock_state(
            {
                "id": 1,
                "gatewayId": "gateway-1",
                "name": "Front Door",
                "info": {
                    "addr": 123,
                    "lockState": 1,
                    "doorState": 0,
                    "boltState": 1,
                    "opMode": 0,
                    "schMode": 0,
                    "vrm": 4968,
                },
            }
        )
        events = self.api._parse_event_logs(
            [
                {
                    "id": 1,
                    "date": "2026-05-27T08:00:00+00:00",
                    "logOwnerId": "owner-1",
                    "severity": "Info",
                    "type": "MQTT_EVT",
                    "text": "HABO SmartBox. Front Door - Locked",
                    "payload": {
                        "gateway": "gateway-1",
                        "device": 123,
                        "eventCode": "EvtOpLock",
                        "eventTitle": "Front Door - Locked",
                        "eventType": "Doorlock",
                    },
                },
                {
                    "id": 2,
                    "date": "2026-05-27T07:59:00+00:00",
                    "severity": "Info",
                    "type": "MQTT_EVT",
                    "text": "HABO SmartBox. The SmartBox is online",
                    "payload": {
                        "gateway": "gateway-1",
                        "device": None,
                        "eventCode": "EvtOnlineWifi",
                        "eventTitle": "The SmartBox is online",
                        "eventType": "Gateway",
                    },
                },
                {
                    "id": 3,
                    "date": "2026-05-27T07:58:00+00:00",
                    "severity": "Info",
                    "type": "MQTT_EVT",
                    "text": "Other lock",
                    "payload": {
                        "gateway": "gateway-1",
                        "device": 999,
                        "eventCode": "EvtOpUnlock",
                    },
                },
            ]
        )

        self.api._with_events(lock, events)

        self.assertEqual(len(lock.events), 1)
        self.assertEqual(lock.events[0].event_code, "EvtOpLock")
        self.assertEqual(lock.events[0].log_owner_id, "owner-1")
        self.assertEqual(len(lock.smartbox_events), 1)
        self.assertEqual(lock.smartbox_events[0].event_code, "EvtOnlineWifi")


if __name__ == "__main__":
    unittest.main()
