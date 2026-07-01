#!/usr/bin/env python3
"""
Kindle-friendly Singapore bus arrival display.

Run this on a computer on the same Wi-Fi as your Kindle, then open:
  http://YOUR_COMPUTER_IP:8080/

Set your LTA DataMall API key in .env first:
  python3 setup_key.py
"""

from __future__ import annotations

import html
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


DEFAULT_STOP = "00000"
DEFAULT_ADDRESS = "My Bus Stop"
DEFAULT_REFRESH_SECONDS = 30
DEFAULT_LTA_BUS_ARRIVAL_URL = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"
DEFAULT_WEATHER_FORECAST_URL = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
DEFAULT_WEATHER_AREA = "Singapore"
DEFAULT_GREETING_TEXT = "Good morning"
DEFAULT_REMINDER_TEXT = "Remember to bring everything you need."
MACOS_CERTIFICATE_HELPER = "/Applications/Python 3.14/Install Certificates.command"


def fetch_bus_arrivals(stop: str, service: str | None = None) -> dict[str, Any]:
    account_key = os.environ.get("LTA_ACCOUNT_KEY")
    if not account_key:
        raise RuntimeError("Missing LTA_ACCOUNT_KEY environment variable.")

    params = {"BusStopCode": stop}
    if service:
        params["ServiceNo"] = service

    endpoint = os.environ.get("LTA_BUS_ARRIVAL_URL", DEFAULT_LTA_BUS_ARRIVAL_URL)
    url = f"{endpoint}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "AccountKey": account_key,
            "accept": "application/json",
            "User-Agent": "kindle-bus-display/1.0",
        },
    )

    with urllib.request.urlopen(request, timeout=12, context=ssl_context()) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_weather_condition(area: str | None = None) -> str:
    area = (area or os.environ.get("WEATHER_AREA") or DEFAULT_WEATHER_AREA).strip()
    endpoint = os.environ.get("WEATHER_FORECAST_URL", DEFAULT_WEATHER_FORECAST_URL)
    request = urllib.request.Request(
        endpoint,
        headers={
            "accept": "application/json",
            "User-Agent": "kindle-bus-display/1.0",
        },
    )

    with urllib.request.urlopen(request, timeout=12, context=ssl_context()) as response:
        payload = json.loads(response.read().decode("utf-8"))

    forecasts = []
    if isinstance(payload.get("items"), list) and payload["items"]:
        forecasts = payload["items"][0].get("forecasts", [])
    elif isinstance(payload.get("data"), dict):
        items = payload["data"].get("items", [])
        if items:
            forecasts = items[0].get("forecasts", [])

    for forecast in forecasts:
        if forecast.get("area") == area:
            return forecast.get("forecast", "--")

    return forecasts[0].get("forecast", "--") if forecasts else "--"


def weather_icon_for(condition: str | None) -> str:
    text = (condition or "").lower()
    if "thunder" in text or "lightning" in text:
        return "⚡"
    if "rain" in text or "shower" in text:
        return "☂"
    if "cloud" in text or "overcast" in text:
        return "☁"
    if "fair" in text or "sun" in text:
        return "☀"
    if "haze" in text or "mist" in text or "fog" in text or "wind" in text:
        return "≋"
    return "○"


def ssl_context() -> ssl.SSLContext:
    if os.environ.get("LTA_ALLOW_INSECURE_SSL") == "1":
        return ssl._create_unverified_context()

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 401:
            return (
                "LTA DataMall rejected the AccountKey with HTTP 401 Unauthorized. "
                "Check that LTA_ACCOUNT_KEY in .env is the active DataMall AccountKey, "
                "then restart this script."
            )
        return f"LTA DataMall returned HTTP {exc.code}: {exc.reason}"

    message = str(exc)
    if "CERTIFICATE_VERIFY_FAILED" in message:
        return (
            "Python cannot verify LTA's HTTPS certificate. Run "
            f"`{MACOS_CERTIFICATE_HELPER}` once, then restart this script. "
            "For a temporary local-only workaround, add LTA_ALLOW_INSECURE_SSL=1 to .env."
        )
    return message


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key == "LTA_ACCOUNT_KEY" and value.startswith("LTA_ACCOUNT_KEY="):
                value = value.split("=", 1)[1].strip()
            if key and key not in os.environ:
                os.environ[key] = value


def local_ip_address() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def minutes_until(estimated_arrival: str) -> str:
    if not estimated_arrival:
        return "-"

    try:
        arrival = datetime.fromisoformat(estimated_arrival)
    except ValueError:
        return "?"

    now = datetime.now(arrival.tzinfo or timezone.utc)
    minutes = round((arrival - now).total_seconds() / 60)

    if minutes <= 0:
        return "Arr"
    return f"{minutes}m"


def bus_load_label(load: str) -> str:
    return {
        "SEA": "Seats",
        "SDA": "Standing",
        "LSD": "Limited",
    }.get(load, load or "")


def normalise_services(payload: dict[str, Any]) -> list[dict[str, Any]]:
    services = []
    for service in payload.get("Services", []):
        next_buses = [service.get("NextBus"), service.get("NextBus2"), service.get("NextBus3")]
        services.append(
            {
                "service": service.get("ServiceNo", ""),
                "operator": service.get("Operator", ""),
                "arrivals": [
                    {
                        "minutes": minutes_until(bus.get("EstimatedArrival", "")),
                        "load": bus_load_label(bus.get("Load", "")),
                        "type": bus.get("Type", ""),
                    }
                    for bus in next_buses
                    if bus
                ],
            }
        )

    return sorted(services, key=lambda item: item["service"])


def render_bus_content(payload: dict[str, Any] | None, error: str | None) -> str:
    services = normalise_services(payload or {})
    if error:
        return f"""
        <div class="message">
          <h2>Cannot load bus times</h2>
          <p>{html.escape(error)}</p>
        </div>
        """
    if not services:
        return """
        <div class="message">
          <h2>No arrivals found</h2>
          <p>Try again in a minute.</p>
        </div>
        """

    rows = []
    for item in services:
        arrivals = item["arrivals"] or [{"minutes": "-", "load": "", "type": ""}]
        cells = "".join(
            f"""
            <div class="arrival">
              <strong>{html.escape(arrival["minutes"])}</strong>
              <span>{html.escape(arrival["load"])}</span>
            </div>
            """
            for arrival in arrivals[:3]
        )
        rows.append(
            f"""
            <section class="service-row">
              <div class="service-no">{html.escape(item["service"])}</div>
              <div class="arrivals">{cells}</div>
            </section>
            """
        )
    return "".join(rows)


def render_bus_panel(
    stop: str,
    address: str,
    service: str | None,
    refresh_seconds: int,
    payload: dict[str, Any] | None,
    error: str | None,
    updated: str,
    layout: str,
    debug: bool,
    show_stop_heading: bool = False,
) -> str:
    service_note = f" · {html.escape(service)}路" if service else ""
    refresh_fields = [
        ("address", address),
        ("refresh", str(refresh_seconds)),
        ("layout", layout),
    ]
    if service:
        refresh_fields.append(("service", service))
    if debug:
        refresh_fields.append(("debug", "1"))
    refresh_fields.append(("_", str(int(time.time()))))
    refresh_href = f"/?{urllib.parse.urlencode(refresh_fields)}"
    heading = ""
    if show_stop_heading:
        heading = f"""
        <h2>{html.escape(address)}</h2>
        """

    return f"""
    <main class="services bus-panel">
      <div class="section-label">
        <!--  <h2>巴士到达时间{service_note}</h2> -->
        {heading}
        <div class="update-row">
          <h2>最后更新：{updated}</h2>
          <a class="refresh-link" href="{html.escape(refresh_href, quote=True)}">refresh</a>
        </div>
      </div>
      {render_bus_content(payload, error)}
    </main>
    """


def render_page(
    stop: str,
    address: str,
    service: str | None,
    refresh_seconds: int,
    payload: dict[str, Any] | None,
    error: str | None,
    layout: str = "portrait",
    debug: bool = False,
    weather_condition: str | None = None,
) -> bytes:
    now = datetime.now()
    display_date = now.strftime("%a, %d %b %Y")
    display_time = now.strftime("%H:%M")
    updated = now.strftime("%H:%M:%S")
    layout = normalise_layout(layout)
    body_class = f' class="{layout}"' if layout == "landscape" else ""
    weather_text = html.escape(weather_condition or "--")
    weather_icon = html.escape(weather_icon_for(weather_condition))
    greeting = html.escape(greeting_text())
    reminder = html.escape(reminder_text())
    debug_panel = ""
    if debug:
        debug_panel = """
    <section class="debug-panel">
      viewport: <span id="viewport-size">unknown</span>
    </section>
    <script>
      (function () {
        var target = document.getElementById("viewport-size");
        if (target) {
          target.innerHTML = window.innerWidth + " x " + window.innerHeight;
        }
      }());
    </script>
        """

    stop_payloads = (payload or {}).get("Stops", [])
    if stop_payloads:
        body = "\n".join(
            render_bus_panel(
                item["stop"],
                item["address"],
                service,
                refresh_seconds,
                item.get("payload"),
                item.get("error"),
                updated,
                layout,
                debug,
                True,
            )
            for item in stop_payloads
        )
    else:
        body = render_bus_panel(stop, address, service, refresh_seconds, payload, error, updated, layout, debug)

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="{refresh_seconds}">
  <title>Bus {html.escape(stop)}</title>
  <style>
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      padding: 18px;
      background: #fff;
      color: #000;
      font-family: Georgia, "Times New Roman", serif;
    }}
    header {{
      border: 3px solid #000;
      margin-bottom: 12px;
      padding: 12px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 34px;
      line-height: 1.05;
      letter-spacing: 0;
    }}
    .greeting-row {{
      display: table;
      width: 100%;
    }}
    .weather-icon,
    .greeting-copy {{
      display: table-cell;
      vertical-align: middle;
    }}
    .greeting-text {{
      display: block;
    }}
    .greeting-time {{
      margin-bottom: 0;
    }}
    .weather-icon {{
      width: 62px;
      padding-left: 12px;
      font-size: 58px;
      line-height: 1;
      text-align: center;
    }}
    .meta {{
      margin: 0;
      font-size: 17px;
      line-height: 1.35;
    }}
    .clock {{
      margin: 8px 0 0;
      font-size: 24px;
      line-height: 1.15;
      font-weight: bold;
    }}
    .section-label,
    .reminder {{
      border: 3px solid #000;
      margin-bottom: 12px;
      padding: 10px 12px;
      font-size: 30px;
      line-height: 1.25;
      font-weight: bold;
    }}
    .section-label h2 {{
      margin: 0 0 4px;
      font-size: 32px;
      line-height: 1.1;
    }}
    .section-label p {{
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
      font-weight: bold;
    }}
    .update-row {{
      display: table;
      width: 100%;
    }}
    .update-row p,
    .refresh-link {{
      display: table-cell;
      vertical-align: middle;
    }}
    .refresh-link {{
      width: 86px;
      text-align: right;
      border: 2px solid #000;
      background: #fff;
      color: #000;
      padding: 6px 12px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 18px;
      font-weight: bold;
      text-decoration: none;
    }}
    .date-panel {{
      margin-bottom: 12px;
    }}
    .top-row {{
      display: block;
    }}
    .services {{
      display: block;
    }}
    .bus-panel {{
      border: 3px solid #000;
      margin-bottom: 12px;
      padding: 0;
    }}
    .bus-panel .section-label {{
      border: 0;
      border-bottom: 3px solid #000;
      margin-bottom: 0;
    }}
    .service-row {{
      display: table;
      width: 100%;
      min-height: 86px;
      border-bottom: 3px solid #000;
    }}
    .service-row:last-child {{
      border-bottom: 0;
    }}
    .service-no {{
      display: table-cell;
      width: 24%;
      padding: 10px;
      border-right: 3px solid #000;
      font-size: 34px;
      font-weight: bold;
      text-align: center;
      vertical-align: middle;
    }}
    .arrivals {{
      display: table-cell;
      width: 76%;
      padding: 8px;
      vertical-align: middle;
    }}
    .arrival {{
      float: left;
      width: 33.333%;
      min-height: 62px;
      padding: 6px 3px;
      border-left: 2px solid #000;
      text-align: center;
    }}
    .arrival:first-child {{
      border-left: 0;
    }}
    .arrival strong {{
      display: block;
      font-size: 33px;
      line-height: 1;
    }}
    .arrival span {{
      display: block;
      min-height: 18px;
      margin-top: 5px;
      font-size: 14px;
    }}
    .message {{
      border: 3px solid #000;
      padding: 18px;
    }}
    .message h2 {{
      margin: 0 0 10px;
      font-size: 26px;
    }}
    .message p {{
      margin: 0;
      font-size: 18px;
      line-height: 1.35;
    }}
    footer {{
      margin-top: 14px;
      font-size: 15px;
    }}
    .debug-panel {{
      border: 3px solid #000;
      margin-top: 12px;
      padding: 10px 12px;
      font-size: 24px;
      font-weight: bold;
    }}
    body.landscape {{
      overflow: hidden;
      padding: 0;
    }}
    .page {{
      display: block;
    }}
    body.landscape .page {{
      width: 1072px;
      min-height: 585px;
      padding: 12px 12px 12px 60px;
      -webkit-transform: rotate(90deg) translateY(-100%) scale(1.1);
      transform: rotate(90deg) translateY(-100%) scale(1.1);
      -webkit-transform-origin: top left;
      transform-origin: top left;
    }}
    body.landscape .top-row {{
      width: 100%;
      margin-bottom: 12px;
      display: block;
    }}
    body.landscape h1 {{
      font-size: 42px;
    }}
    body.landscape .weather-icon {{
      width: 88px;
      padding-left: 18px;
      font-size: 86px;
    }}
    body.landscape .clock {{
      margin-top: 8px;
      font-size: 30px;
    }}
    body.landscape .section-label h2 {{
      font-size: 38px;
    }}
    body.landscape .section-label p {{
      font-size: 25px;
    }}
    body.landscape .refresh-link {{
      padding: 8px 16px;
      font-size: 24px;
    }}
    body.landscape .service-row {{
      display: table;
      width: 100%;
      min-height: 112px;
      vertical-align: top;
    }}
    body.landscape .service-no {{
      width: 24%;
      font-size: 48px;
    }}
    body.landscape .arrivals {{
      width: 76%;
      padding: 10px;
    }}
    body.landscape .arrival {{
      min-height: 84px;
    }}
    body.landscape .arrival strong {{
      font-size: 48px;
    }}
    body.landscape .arrival span {{
      font-size: 18px;
    }}
    body.landscape .reminder {{
      padding: 12px 14px;
      margin-bottom: 200px;
      font-size: 32px;
    }}
    body.landscape footer {{
      display: none;
    }}
    body.landscape .debug-panel {{
      font-size: 30px;
    }}
    @media (max-width: 420px) {{
      body {{
        padding: 12px;
      }}
      h1 {{
        font-size: 29px;
      }}
      .clock {{
        font-size: 21px;
      }}
      .section-label,
      .reminder {{
        padding: 9px 10px;
        font-size: 19px;
      }}
      .section-label h2 {{
        font-size: 24px;
      }}
      .section-label p {{
        font-size: 17px;
      }}
      .service-row {{
        min-height: 78px;
      }}
      .service-no {{
        width: 23%;
        padding: 8px 4px;
        font-size: 28px;
      }}
      .arrivals {{
        width: 77%;
        padding: 6px;
      }}
      .arrival {{
        min-height: 56px;
      }}
      .arrival strong {{
        font-size: 27px;
      }}
      .arrival span {{
        font-size: 12px;
      }}
      body.landscape {{
        padding: 0;
      }}
      body.landscape .page {{
        width: 1072px;
        min-height: 585px;
        padding: 12px 12px 12px 60px;
      }}
      body.landscape .top-row {{
        width: 100%;
        display: block;
      }}
      body.landscape h1 {{
        font-size: 42px;
      }}
      body.landscape .weather-icon {{
        width: 88px;
        padding-left: 18px;
        font-size: 86px;
      }}
      body.landscape .clock {{
        font-size: 30px;
      }}
      body.landscape .service-row {{
        display: table;
        width: 100%;
        min-height: 112px;
      }}
      body.landscape .service-no {{
        width: 24%;
        font-size: 48px;
      }}
      body.landscape .arrivals {{
        width: 76%;
      }}
      body.landscape .arrival strong {{
        font-size: 48px;
      }}
      body.landscape .section-label h2 {{
        font-size: 38px;
      }}
      body.landscape .section-label p {{
        font-size: 25px;
      }}
      body.landscape .reminder {{
        margin-bottom: 200px;
        font-size: 32px;
      }}
    }}
  </style>
</head>
<body{body_class}>
  <div class="page">
    <div class="top-row">
      <header>
        <div class="greeting-row">
          <div class="greeting-copy">
            <h1 class="greeting-text">{greeting}</h1>
            <h1 class="greeting-text greeting-time">{display_date} · {display_time}</h1>
          </div>
          <div class="weather-icon">{weather_icon}</div>
        </div>
      </header>
    </div>
    {body}
    <section class="reminder">{reminder}</section>
    {debug_panel}
    <footer>Auto-refreshes every {refresh_seconds}s. Add ?service=265 to show one bus. Add ?layout=landscape for horizontal mode.</footer>
  </div>
</body>
</html>
"""
    return document.encode("utf-8")


def normalise_layout(value: str) -> str:
    if value.lower() in {"landscape", "horizontal", "wide"}:
        return "landscape"
    return "portrait"


def default_stop() -> str:
    return os.environ.get("BUS_STOP", DEFAULT_STOP).strip() or DEFAULT_STOP


def default_address() -> str:
    return os.environ.get("BUS_ADDRESS", DEFAULT_ADDRESS).strip() or DEFAULT_ADDRESS


def greeting_text() -> str:
    return os.environ.get("GREETING_TEXT", DEFAULT_GREETING_TEXT).strip() or DEFAULT_GREETING_TEXT


def reminder_text() -> str:
    return os.environ.get("REMINDER_TEXT", DEFAULT_REMINDER_TEXT).strip() or DEFAULT_REMINDER_TEXT


def parse_display_stops(value: str) -> list[dict[str, str]]:
    stops = []
    for raw_item in value.split(";"):
        item = raw_item.strip()
        if not item:
            continue

        parts = [part.strip() for part in item.split("|")]
        if len(parts) == 2:
            stop, address = parts
            alias = stop
        elif len(parts) == 3:
            alias, stop, address = parts
        else:
            continue

        if stop and address:
            stops.append({"alias": alias or stop, "stop": stop, "address": address})
    return stops


def display_stops() -> list[dict[str, str]]:
    configured = parse_display_stops(os.environ.get("DISPLAY_STOPS", ""))
    if configured:
        return configured
    return [{"alias": default_stop(), "stop": default_stop(), "address": default_address()}]


def stop_from_path(path: str) -> tuple[str, str] | None:
    key = path.strip("/").lower()
    if not key:
        return None

    for item in display_stops():
        aliases = {item["alias"].lower(), item["stop"].lower()}
        if key in aliases:
            return item["stop"], item["address"]
    return None


class BusHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        configured_stop = default_stop()
        configured_address = default_address()
        path_stop = stop_from_path(parsed.path)
        if path_stop:
            configured_stop, configured_address = path_stop

        stop = query.get("stop", [configured_stop])[0].strip() or configured_stop
        address = query.get("address", [configured_address])[0].strip() or configured_address
        service = query.get("service", [None])[0]
        refresh_seconds = parse_refresh(query.get("refresh", [str(DEFAULT_REFRESH_SECONDS)])[0])
        layout = normalise_layout(query.get("layout", ["portrait"])[0].strip())
        debug = query.get("debug", ["0"])[0] == "1"
        show_all_stops = parsed.path in {"/", "/index.html"} and "stop" not in query

        if parsed.path == "/api/bus":
            self.send_json(stop, service)
            return

        if parsed.path not in {"/", "/index.html"} and not path_stop:
            self.send_error(404, "Not found")
            return

        payload = None
        error = None
        weather_condition = None
        if show_all_stops:
            stop_payloads = []
            for item in display_stops():
                display_stop = item["stop"]
                display_address = item["address"]
                stop_payload = None
                stop_error = None
                try:
                    stop_payload = fetch_bus_arrivals(display_stop, service)
                except (RuntimeError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                    stop_error = friendly_error(exc)
                stop_payloads.append(
                    {
                        "stop": display_stop,
                        "address": display_address,
                        "payload": stop_payload,
                        "error": stop_error,
                    }
                )
            payload = {"Stops": stop_payloads}
        else:
            try:
                payload = fetch_bus_arrivals(stop, service)
            except (RuntimeError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                error = friendly_error(exc)

        try:
            weather_condition = fetch_weather_condition()
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            weather_condition = "--"

        content = render_page(stop, address, service, refresh_seconds, payload, error, layout, debug, weather_condition)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, stop: str, service: str | None) -> None:
        try:
            payload = fetch_bus_arrivals(stop, service)
            content = json.dumps(
                {
                    "ok": True,
                    "stop": stop,
                    "services": normalise_services(payload),
                    "source": "LTA DataMall v3 BusArrival",
                    "serverTime": int(time.time()),
                }
            ).encode("utf-8")
            self.send_response(200)
        except Exception as exc:  # JSON endpoint should return structured failures.
            content = json.dumps({"ok": False, "stop": stop, "error": friendly_error(exc)}).encode("utf-8")
            self.send_response(502)

        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("request - %s\n" % (format % args))


def parse_refresh(value: str) -> int:
    try:
        return max(15, min(600, int(value)))
    except ValueError:
        return DEFAULT_REFRESH_SECONDS


def main() -> None:
    load_dotenv()
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), BusHandler)
    host = local_ip_address() or "YOUR_COMPUTER_IP"
    print(f"Kindle bus display running on port {port}.")
    print(f"Open configured stops: http://{host}:{port}/")
    for item in display_stops():
        print(f"{item['address']}: http://{host}:{port}/{item['alias']}")
    if host == "YOUR_COMPUTER_IP":
        print("Could not detect your IP automatically. On macOS, run: ipconfig getifaddr en0")
    print(f"Default stop: {default_stop()} ({default_address()})")
    server.serve_forever()


if __name__ == "__main__":
    main()
