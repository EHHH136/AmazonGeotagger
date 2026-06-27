# Amazon Geotagger

A small Python web app for collecting field reports about illegal mining activity in Amazon regions.

## Features

- Capture a photo from the browser camera
- Attach GPS coordinates from the device
- Save reports to a CSV file
- View recent saved reports in the app

## Run locally

1. Open a terminal in this folder.
2. Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

3. Start the app:

```powershell
python main.py
```

4. Open `http://127.0.0.1:8000` in your browser.

## Notes

- The app stores reports in `illegal_mining_reports.csv`.
- The CSV file is ignored by Git so your collected data stays local by default.
- Camera and geolocation features usually require HTTPS when deployed publicly.
