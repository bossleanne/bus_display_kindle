import json
import io
import os
import unittest
import urllib.error
from unittest.mock import patch

import bus_kindle
import setup_key


LTA_SAMPLE_SHAPE = {
    "odata.metadata": "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival",
    "BusStopCode": "20251",
    "Services": [
        {
            "ServiceNo": "176",
            "Operator": "SMRT",
            "NextBus": {
                "EstimatedArrival": "2024-08-22T15:27:15+08:00",
                "Load": "SEA",
                "Type": "DD",
            },
            "NextBus2": {
                "EstimatedArrival": "2024-08-22T15:42:48+08:00",
                "Load": "SEA",
                "Type": "DD",
            },
            "NextBus3": {
                "EstimatedArrival": "2024-08-22T15:49:31+08:00",
                "Load": "SEA",
                "Type": "SD",
            },
        },
        {
            "ServiceNo": "78",
            "Operator": "TTS",
            "NextBus": {
                "EstimatedArrival": "2024-08-22T15:29:57+08:00",
                "Load": "SEA",
                "Type": "DD",
            },
            "NextBus2": {
                "EstimatedArrival": "2024-08-22T15:52:01+08:00",
                "Load": "SEA",
                "Type": "DD",
            },
            "NextBus3": {
                "EstimatedArrival": "",
                "Load": "",
                "Type": "",
            },
        },
    ],
}


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


class BusKindleTests(unittest.TestCase):
    def test_fetch_bus_arrivals_calls_lta_with_account_key(self):
        payload = {"Services": [{"ServiceNo": "265"}]}

        def fake_urlopen(request, timeout, context):
            self.assertEqual(timeout, 12)
            self.assertIsNotNone(context)
            self.assertIn("/v3/BusArrival?", request.full_url)
            self.assertIn("BusStopCode=12345", request.full_url)
            self.assertIn("ServiceNo=265", request.full_url)
            self.assertEqual(request.headers["Accountkey"], "test-key")
            return FakeResponse(json.dumps(payload).encode("utf-8"))

        with patch.dict(os.environ, {"LTA_ACCOUNT_KEY": "test-key"}):
            with patch("urllib.request.urlopen", fake_urlopen):
                self.assertEqual(bus_kindle.fetch_bus_arrivals("12345", "265"), payload)

    def test_normalise_services_accepts_lta_v3_sample_shape(self):
        services = bus_kindle.normalise_services(LTA_SAMPLE_SHAPE)

        self.assertEqual([service["service"] for service in services], ["176", "78"])
        self.assertEqual(services[0]["arrivals"][0]["load"], "Seats")
        self.assertEqual(services[1]["arrivals"][2]["minutes"], "-")

    def test_fetch_weather_condition_uses_area_forecast(self):
        payload = {
            "items": [
                {
                    "forecasts": [
                        {"area": "Bishan", "forecast": "Cloudy"},
                        {"area": "REMOVED_WEATHER_AREA", "forecast": "Partly Cloudy"},
                    ]
                }
            ]
        }

        def fake_urlopen(request, timeout, context):
            self.assertEqual(timeout, 12)
            self.assertIsNotNone(context)
            return FakeResponse(json.dumps(payload).encode("utf-8"))

        with patch("urllib.request.urlopen", fake_urlopen):
            self.assertEqual(bus_kindle.fetch_weather_condition("REMOVED_WEATHER_AREA"), "Partly Cloudy")

    def test_weather_icon_for_condition(self):
        self.assertEqual(bus_kindle.weather_icon_for("Partly Cloudy (Night)"), "☁")
        self.assertEqual(bus_kindle.weather_icon_for("Light Rain"), "☂")
        self.assertEqual(bus_kindle.weather_icon_for("Thundery Showers"), "⚡")

    def test_render_page_contains_stop_address_and_arrivals(self):
        html = bus_kindle.render_page(
            "12345",
            "My Bus Stop",
            None,
            60,
            {
                "Services": [
                    {
                        "ServiceNo": "265",
                        "Operator": "SBST",
                        "NextBus": {"EstimatedArrival": "", "Load": "SEA"},
                        "NextBus2": {"EstimatedArrival": "", "Load": "SDA"},
                        "NextBus3": {"EstimatedArrival": "", "Load": "LSD"},
                    }
                ]
            },
            None,
        ).decode("utf-8")

        self.assertNotIn("<h1>My Bus Stop</h1>", html)
        self.assertNotIn("Stop 12345", html)
        self.assertIn('<h1 class="greeting-text">大家好，欢迎来到REMOVED_PRIVATE_TEXT</h1>', html)
        self.assertRegex(
            html,
            r'<h1 class="greeting-text greeting-time">今天是新加坡时间：[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4} · \d{2}:\d{2}</h1>',
        )
        self.assertIn('<div class="weather-icon">○</div>', html)
        self.assertLess(html.index('class="greeting-copy"'), html.index('class="weather-icon"'))
        self.assertIn("巴士到达时间", html)
        self.assertIn('<main class="services bus-panel">', html)
        self.assertRegex(html, r"最后更新：\d{2}:\d{2}:\d{2}")
        self.assertIn('class="refresh-link"', html)
        self.assertIn(">refresh</a>", html)
        self.assertIn('<div class="service-no">265</div>', html)
        self.assertIn('<div class="arrival">', html)
        self.assertIn("Seats", html)
        self.assertIn("Standing", html)
        self.assertIn("Limited", html)
        self.assertIn("REMOVED_REMINDER_TEXT", html)
        self.assertIn('content="60"', html)

    def test_friendly_error_explains_lta_unauthorized(self):
        error = urllib.error.HTTPError(
            "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b"Unauthorized"),
        )

        try:
            self.assertIn("LTA DataMall rejected the AccountKey", bus_kindle.friendly_error(error))
        finally:
            error.close()

    def test_render_page_supports_landscape_layout(self):
        html = bus_kindle.render_page(
            "12345",
            "My Bus Stop",
            None,
            60,
            {"Services": []},
            None,
            "horizontal",
        ).decode("utf-8")

        self.assertIn('<body class="landscape">', html)
        self.assertIn('<div class="page">', html)
        self.assertIn("rotate(90deg)", html)
        self.assertIn("scale(1.1)", html)
        self.assertIn("width: 1072px;", html)
        self.assertIn("min-height: 585px;", html)
        self.assertIn("layout=landscape", html)
        self.assertIn("body.landscape footer", html)
        self.assertIn("Add ?layout=landscape for horizontal mode.", html)

    def test_render_page_can_show_viewport_debug_panel(self):
        html = bus_kindle.render_page(
            "12345",
            "My Bus Stop",
            None,
            60,
            {"Services": []},
            None,
            "landscape",
            True,
        ).decode("utf-8")

        self.assertIn('<section class="debug-panel">', html)
        self.assertIn('id="viewport-size"', html)
        self.assertIn("debug=1", html)

    def test_load_dotenv_does_not_override_existing_environment(self):
        with patch.dict(os.environ, {"LTA_ACCOUNT_KEY": "existing-key"}, clear=False):
            bus_kindle.load_dotenv(".env.example")
            self.assertEqual(os.environ["LTA_ACCOUNT_KEY"], "existing-key")

    def test_default_stop_and_address_can_come_from_environment(self):
        with patch.dict(os.environ, {"BUS_STOP": "98765", "BUS_ADDRESS": "Example Stop"}, clear=False):
            self.assertEqual(bus_kindle.default_stop(), "98765")
            self.assertEqual(bus_kindle.default_address(), "Example Stop")

    def test_normalise_layout_accepts_horizontal_aliases(self):
        self.assertEqual(bus_kindle.normalise_layout("horizontal"), "landscape")
        self.assertEqual(bus_kindle.normalise_layout("wide"), "landscape")
        self.assertEqual(bus_kindle.normalise_layout("portrait"), "portrait")

    def test_parse_refresh_falls_back_to_30_seconds(self):
        self.assertEqual(bus_kindle.DEFAULT_REFRESH_SECONDS, 30)
        self.assertEqual(bus_kindle.parse_refresh("not-a-number"), 30)

    def test_setup_key_accepts_full_env_line(self):
        self.assertEqual(setup_key.normalise_key("LTA_ACCOUNT_KEY=abc123"), "abc123")
        self.assertEqual(setup_key.normalise_key("abc123"), "abc123")


if __name__ == "__main__":
    unittest.main()
