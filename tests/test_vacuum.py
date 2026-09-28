"""Exercise the USB vacuum boundary without opening a physical device."""

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from almond_axol.serve.vacuum import install_vacuum_routes
from almond_axol.serve.vacuum_relay import VacuumRelay


class VacuumTests(unittest.TestCase):
    def test_release_pulses_vent_then_cleans_up(self):
        writes = []
        relay = VacuumRelay(writer=writes.append)
        with patch("almond_axol.serve.vacuum_relay.time.sleep") as sleep:
            self.assertFalse(relay.release()["commanded_on"])
        self.assertEqual(writes, [[(2, False), (1, True)], [(2, False), (1, False)]])
        sleep.assert_called_once_with(0.4)

    def test_release_failure_still_attempts_off(self):
        relay = VacuumRelay()
        with patch.object(
            relay, "_writer", side_effect=[OSError("unplugged"), None]
        ) as writer:
            with self.assertRaises(OSError):
                relay.release()
        self.assertEqual(writer.call_args_list[-1].args[0], [(2, False), (1, False)])
        self.assertIsNone(relay.status()["commanded_on"])

    def test_order_and_frames(self):
        writes = []
        relay = VacuumRelay(writer=writes.append)
        self.assertIsNone(relay.status()["commanded_on"])
        self.assertTrue(relay.set(True)["commanded_on"])
        self.assertFalse(relay.set(False)["commanded_on"])
        self.assertEqual(writes, [[(1, False), (2, True)], [(2, False), (1, False)]])
        self.assertEqual(relay.frame(2, True), bytes.fromhex("a00201a3"))

    def test_failure_clears_commanded_state(self):
        relay = VacuumRelay(writer=lambda _: None)
        relay.set(True)
        with patch.object(relay, "_writer", side_effect=OSError("unplugged")):
            with self.assertRaises(OSError):
                relay.set(False)
        self.assertIsNone(relay.status()["commanded_on"])
        self.assertEqual(relay.status()["error"], "unplugged")

    def test_api(self):
        writes = []
        relay = VacuumRelay(writer=writes.append)
        app = FastAPI()
        with (
            patch.dict("os.environ", AXOL_SUCTION_DEVICE="/fake/relay"),
            patch("almond_axol.serve.vacuum.VacuumRelay", return_value=relay),
        ):
            install_vacuum_routes(app)
        with TestClient(app) as client:
            self.assertIsNone(client.get("/api/vacuum").json()["commanded_on"])
            self.assertEqual(writes, [])
            with patch("almond_axol.serve.vacuum_relay.time.sleep"):
                self.assertFalse(
                    client.post("/api/vacuum/release").json()["commanded_on"]
                )
            self.assertTrue(
                client.post("/api/vacuum", json={"on": True}).json()["commanded_on"]
            )
            self.assertFalse(
                client.post("/api/vacuum", json={"on": False}).json()["commanded_on"]
            )
            self.assertEqual(
                client.post("/api/vacuum", json={"on": "false"}).status_code, 422
            )
            with patch.object(relay, "_writer", side_effect=OSError("unplugged")):
                self.assertEqual(
                    client.post("/api/vacuum", json={"on": False}).status_code, 503
                )

    def test_unconfigured(self):
        app = FastAPI()
        with patch.dict("os.environ", AXOL_SUCTION_DEVICE=""):
            install_vacuum_routes(app)
        with TestClient(app) as client:
            self.assertFalse(client.get("/api/vacuum").json()["enabled"])
            self.assertEqual(client.post("/api/vacuum/release").status_code, 503)
            self.assertEqual(
                client.post("/api/vacuum", json={"on": True}).status_code, 503
            )
