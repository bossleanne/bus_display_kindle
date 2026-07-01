#!/usr/bin/env python3
"""Prompt for the LTA DataMall key and write a private .env file."""

from __future__ import annotations

import getpass
import os


def main() -> None:
    key = normalise_key(getpass.getpass("Paste LTA_ACCOUNT_KEY: "))
    if not key:
        raise SystemExit("No key entered. .env was not changed.")

    bus_stop = input("Default bus stop code: ").strip() or "00000"
    bus_address = input("Default bus stop label: ").strip() or "My Bus Stop"
    display_stops = input("Stops to display (alias|code|label;alias|code|label): ").strip()
    weather_area = input("Weather area: ").strip() or "Singapore"
    greeting = input("Greeting text: ").strip() or "Good morning"
    reminder = input("Reminder text: ").strip() or "Remember to bring everything you need."

    with open(".env", "w", encoding="utf-8") as env_file:
        env_file.write(f"LTA_ACCOUNT_KEY={key}\n")
        env_file.write("PORT=8080\n")
        env_file.write("LTA_BUS_ARRIVAL_URL=https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival\n")
        env_file.write(f"BUS_STOP={bus_stop}\n")
        env_file.write(f"BUS_ADDRESS={bus_address}\n")
        if display_stops:
            env_file.write(f"DISPLAY_STOPS={display_stops}\n")
        env_file.write(f"WEATHER_AREA={weather_area}\n")
        env_file.write(f"GREETING_TEXT={greeting}\n")
        env_file.write(f"REMINDER_TEXT={reminder}\n")

    os.chmod(".env", 0o600)
    print(".env saved. You can now run: python3 bus_kindle.py")


def normalise_key(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    if value.startswith("LTA_ACCOUNT_KEY="):
        value = value.split("=", 1)[1].strip().strip('"').strip("'")
    return value


if __name__ == "__main__":
    main()
