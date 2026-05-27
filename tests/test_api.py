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
    status_code = 200
    content = b'"Ok"'

    def raise_for_status(self):
        return None

    def json(self):
        return "Ok"


class FakeHttpClient:
    def __init__(self):
        self.requests = []

    async def request(self, method, url, headers=None, **kwargs):
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "kwargs": kwargs,
            }
        )
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
        self.assertEqual(lock.smartbox.zigbee_channel, 14)

    def test_lock_and_unlock_do_not_send_pin(self):
        fake_client = FakeHttpClient()
        client = self.api.HaboTribe2Client(
            base_url="https://example.test/api/v1",
            username="user@example.test",
            password="secret",
            client=fake_client,
        )
        client._token = "token"

        asyncio.run(client.async_lock("gateway-1", 123))
        asyncio.run(client.async_unlock("gateway-1", 123))

        lock_request = fake_client.requests[0]
        unlock_request = fake_client.requests[1]

        self.assertNotIn("pin", lock_request["kwargs"].get("params", {}))
        self.assertNotIn("pin", unlock_request["kwargs"].get("params", {}))
        self.assertEqual(unlock_request["kwargs"]["params"], {"timeout": 5000})


if __name__ == "__main__":
    unittest.main()
