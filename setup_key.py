#!/usr/bin/env python3
"""Prompt for the LTA DataMall key and write a private .env file."""

from __future__ import annotations

import getpass
import os


def main() -> None:
    key = normalise_key(getpass.getpass("Paste LTA_ACCOUNT_KEY: "))
    if not key:
        raise SystemExit("No key entered. .env was not changed.")

    with open(".env", "w", encoding="utf-8") as env_file:
        env_file.write(f"LTA_ACCOUNT_KEY={key}\n")
        env_file.write("PORT=8080\n")
        env_file.write("LTA_BUS_ARRIVAL_URL=https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival\n")
        env_file.write("BUS_STOP=REMOVED_BUS_STOP\n")
        env_file.write("BUS_ADDRESS=Blk REMOVED_STOP_ALIAS AMK\n")

    os.chmod(".env", 0o600)
    print(".env saved. You can now run: python3 bus_kindle.py")


def normalise_key(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    if value.startswith("LTA_ACCOUNT_KEY="):
        value = value.split("=", 1)[1].strip().strip('"').strip("'")
    return value


if __name__ == "__main__":
    main()
