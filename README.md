# Kindle Singapore Bus Display

Small Kindle-friendly page for live bus arrivals at your chosen Singapore bus stop.

The Kindle opens a simple page from your computer. Your computer fetches the latest data from LTA DataMall, so the LTA API key is not exposed in the Kindle page.

It uses LTA DataMall `v3/BusArrival`, matching the sample files in `/Users/meilin/Downloads/BusArrival`.

## 1. Get an LTA DataMall API key

Create an account and get an `AccountKey` from LTA DataMall:

<https://datamall.lta.gov.sg/>

## 2. Run the display server

Create a private `.env` file:

```sh
python3 setup_key.py
```

Paste your LTA DataMall key when prompted. The key will not be shown on screen.

Then start the server:

```sh
python3 bus_kindle.py
```

The server listens on port `8080` and prints the URL to open on your Kindle.

## 3. Choose the URL

By default, the app prints your computer's IP address:

```text
Open this on your Kindle: http://YOUR_COMPUTER_IP:8080/
```

If the app cannot detect the IP automatically, find it on macOS:

```sh
ipconfig getifaddr en0
```

If that prints nothing, try:

```sh
ipconfig getifaddr en1
```

Then open `http://YOUR_COMPUTER_IP:8080/`.

## 4. Open it on the Kindle

Make sure the Kindle is on the same Wi-Fi network, then open the Kindle browser and go to:

```text
http://YOUR_COMPUTER_IP:8080/
```

Example:

```text
http://REMOVED_LOCAL_IP:8080/
```

The page auto-refreshes every 30 seconds.

Keep the Terminal window open while the Kindle display is running.

## Useful URLs

Show both nearby bus stops:

```text
http://YOUR_COMPUTER_IP:8080/
```

Show Blk REMOVED_STOP_ALIAS AMK, stop `REMOVED_BUS_STOP`:

```text
http://YOUR_COMPUTER_IP:8080/REMOVED_STOP_ALIAS
```

Show REMOVED_WEATHER_AREA Avenue 4 Blk REMOVED_STOP_ALIAS, stop `REMOVED_BUS_STOP`:

```text
http://YOUR_COMPUTER_IP:8080/REMOVED_STOP_ALIAS
```

Show only one bus service:

```text
http://YOUR_COMPUTER_IP:8080/?service=265
```

Change refresh rate:

```text
http://YOUR_COMPUTER_IP:8080/?refresh=30
```

Use the landscape Kindle layout:

```text
http://YOUR_COMPUTER_IP:8080/?layout=landscape&refresh=30
```

Get JSON data:

```text
http://YOUR_COMPUTER_IP:8080/api/bus
```

## Change Bus Stop

The fallback single bus stop is configured in your private `.env` file:

```env
BUS_STOP=REMOVED_BUS_STOP
BUS_ADDRESS=Blk REMOVED_STOP_ALIAS AMK
```

To permanently use another fallback stop, edit those two values in `.env`, save the file, then restart:

```sh
python3 bus_kindle.py
```

You can also change the bus stop from the URL without editing code:

```text
http://YOUR_COMPUTER_IP:8080/?stop=REMOVED_BUS_STOP&address=Ang%20Mo%20Kio%20Ave%204%20Blk%20REMOVED_STOP_ALIAS
```

For Kindle landscape mode:

```text
http://YOUR_COMPUTER_IP:8080/REMOVED_STOP_ALIAS?layout=landscape&refresh=30
```

Use LTA's bus stop code for `stop`. The `address` value is just a display label; replace spaces with `%20`.

## Notes

- If you see `Missing LTA_ACCOUNT_KEY environment variable`, set the API key in `.env` and restart the server.
- If the Kindle cannot load the page, check that your computer and Kindle are on the same Wi-Fi and that macOS firewall allows incoming connections for Python.
- If the bus stop has no current arrivals, the page will show `No arrivals found`.

## SSL certificate error

If the Kindle page says `CERTIFICATE_VERIFY_FAILED`, Python can reach LTA but does not have its certificate store set up.

Run this once on your Mac:

```sh
/Applications/Python\ 3.14/Install\ Certificates.command
```

Then restart the bus display:

```sh
python3 bus_kindle.py
```

Temporary local-only workaround:

```sh
echo 'LTA_ALLOW_INSECURE_SSL=1' >> .env
python3 bus_kindle.py
```

Use the workaround only for this private Kindle display on your home network.
