from __future__ import annotations

import base64
import csv
import json
import os
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
REPORTS_CSV_PATH = Path(os.environ.get("REPORTS_CSV_PATH", str(ROOT / "illegal_mining_reports.csv")))
CSV_FIELDS = [
	"id",
	"created_at",
	"site_name",
	"notes",
	"latitude",
	"longitude",
	"image_mime",
	"image_base64",
]


def utc_now() -> str:
		return datetime.now(timezone.utc).isoformat(timespec="seconds")


def initialize_storage() -> None:
		if REPORTS_CSV_PATH.exists() and REPORTS_CSV_PATH.stat().st_size > 0:
				return

		with REPORTS_CSV_PATH.open("w", newline="", encoding="utf-8") as file_handle:
				writer = csv.DictWriter(file_handle, fieldnames=CSV_FIELDS)
				writer.writeheader()


def load_report_rows() -> list[dict[str, str]]:
		if not REPORTS_CSV_PATH.exists() or REPORTS_CSV_PATH.stat().st_size == 0:
				return []

		with REPORTS_CSV_PATH.open("r", newline="", encoding="utf-8") as file_handle:
				reader = csv.DictReader(file_handle)
				return list(reader)


def save_report(site_name: str, notes: str, latitude: float, longitude: float, image_mime: str, image_blob: bytes) -> int:
		initialize_storage()
		report_id = len(load_report_rows()) + 1
		encoded_image = base64.b64encode(image_blob).decode("ascii")
		row = {
				"id": str(report_id),
				"created_at": utc_now(),
				"site_name": site_name,
				"notes": notes,
				"latitude": str(latitude),
				"longitude": str(longitude),
				"image_mime": image_mime,
				"image_base64": encoded_image,
		}

		with REPORTS_CSV_PATH.open("a", newline="", encoding="utf-8") as file_handle:
				writer = csv.DictWriter(file_handle, fieldnames=CSV_FIELDS)
				writer.writerow(row)

		return report_id


def list_reports(limit: int = 25) -> list[dict[str, object]]:
		rows = load_report_rows()
		selected_rows = rows[-limit:][::-1]

		return [
			{
				"id": int(row["id"]),
				"created_at": row["created_at"],
				"site_name": row["site_name"],
				"notes": row["notes"],
				"latitude": float(row["latitude"]),
				"longitude": float(row["longitude"]),
			}
			for row in selected_rows
		]


def get_report_image(report_id: int) -> tuple[str, bytes] | None:
		for row in load_report_rows():
				if int(row["id"]) == report_id:
					return str(row["image_mime"]), base64.b64decode(row["image_base64"])

		return None


def build_html() -> str:
	return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Amazon Mining GeoTag Reporter</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
		:root {
			color-scheme: light;
			--bg: #0d1b16;
			--panel: rgba(255, 255, 255, 0.08);
			--panel-border: rgba(255, 255, 255, 0.12);
			--text: #f5f7f2;
			--muted: #b9c7be;
			--accent: #f2b84b;
			--accent-2: #6dd3a0;
			--danger: #ff6b6b;
			--shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
		}

		* { box-sizing: border-box; }

		body {
			margin: 0;
			font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
			color: var(--text);
			min-height: 100vh;
			background:
				radial-gradient(circle at top left, rgba(109, 211, 160, 0.28), transparent 30%),
				radial-gradient(circle at bottom right, rgba(242, 184, 75, 0.18), transparent 25%),
				linear-gradient(160deg, #08120f 0%, #0d1b16 45%, #173224 100%);
		}

		.shell {
			width: min(1200px, calc(100% - 32px));
			margin: 0 auto;
			padding: 32px 0 48px;
		}

		.hero {
			display: grid;
			gap: 16px;
			margin-bottom: 24px;
		}

		.eyebrow {
			text-transform: uppercase;
			letter-spacing: 0.22em;
			font-size: 0.75rem;
			color: var(--accent-2);
			margin: 0;
		}

		h1 {
			margin: 0;
			font-size: clamp(2rem, 4vw, 4rem);
			line-height: 1.02;
			max-width: 11ch;
		}

		.subtitle {
			margin: 0;
			max-width: 70ch;
			color: var(--muted);
			font-size: 1rem;
			line-height: 1.6;
		}

		.grid {
			display: grid;
			grid-template-columns: 1.2fr 0.8fr;
			gap: 20px;
		}

		.card {
			background: var(--panel);
			border: 1px solid var(--panel-border);
			border-radius: 24px;
			box-shadow: var(--shadow);
			backdrop-filter: blur(18px);
			overflow: hidden;
		}

		.card .content {
			padding: 20px;
		}

		.panel-title {
			margin: 0 0 8px;
			font-size: 1.1rem;
		}

		.panel-copy {
			margin: 0 0 16px;
			color: var(--muted);
			line-height: 1.5;
		}

		/* collapsible control */
		.controls {
			display: block;
			margin-bottom: 12px;
		}

		.controls .toggle {
			display: flex;
			justify-content: space-between;
			align-items: center;
			cursor: pointer;
			padding: 10px 12px;
			border-radius: 12px;
			background: rgba(255,255,255,0.03);
			border: 1px solid rgba(255,255,255,0.04);
		}

		.controls .arrow {
			transition: transform 0.2s ease;
		}

		.controls .arrow.open { transform: rotate(180deg); }

		.controls .panel {
			display: none;
			margin-top: 8px;
			padding: 10px 12px;
			border-radius: 12px;
			background: rgba(255,255,255,0.02);
			border: 1px solid rgba(255,255,255,0.03);
		}

		.data-preview { display: flex; gap: 12px; align-items: center; }
		.data-preview .stats { color: var(--muted); }
		.data-preview .thumbs { display:flex; gap:8px; }
		.data-preview .thumbs img { width:56px; height:56px; object-fit:cover; border-radius:8px; border:1px solid rgba(255,255,255,0.06); }

		.camera-wrap {
			display: grid;
			gap: 12px;
		}

		video, canvas, .photo-preview {
			width: 100%;
			border-radius: 20px;
			background: rgba(255, 255, 255, 0.06);
			border: 1px solid rgba(255, 255, 255, 0.1);
		}

		video {
			min-height: 340px;
			object-fit: cover;
		}

		canvas, .photo-preview {
			display: none;
			min-height: 340px;
			object-fit: cover;
		}

		.button-row {
			display: flex;
			flex-wrap: wrap;
			gap: 10px;
		}

		button {
			border: 0;
			border-radius: 999px;
			padding: 0.95rem 1.2rem;
			font-weight: 700;
			cursor: pointer;
			transition: transform 0.15s ease, opacity 0.15s ease, background 0.15s ease;
		}

		button:hover { transform: translateY(-1px); }
		button:active { transform: translateY(0); }

		.primary { background: var(--accent); color: #1d1504; }
		.secondary { background: rgba(255, 255, 255, 0.1); color: var(--text); border: 1px solid rgba(255, 255, 255, 0.14); }
		.ghost { background: transparent; color: var(--text); border: 1px solid rgba(255, 255, 255, 0.14); }

		form {
			display: grid;
			gap: 14px;
		}

		label {
			display: grid;
			gap: 8px;
			color: var(--muted);
			font-size: 0.95rem;
		}

		input, textarea {
			width: 100%;
			border-radius: 16px;
			border: 1px solid rgba(255, 255, 255, 0.14);
			background: rgba(10, 18, 15, 0.6);
			color: var(--text);
			padding: 0.95rem 1rem;
			font: inherit;
			outline: none;
		}

		textarea { min-height: 120px; resize: vertical; }

		.status {
			padding: 12px 14px;
			border-radius: 16px;
			background: rgba(255, 255, 255, 0.08);
			color: var(--muted);
			line-height: 1.5;
		}

		.status strong { color: var(--text); }

		.status.error { color: #ffd7d7; background: rgba(255, 107, 107, 0.12); }
		.status.success { color: #dff7ea; background: rgba(109, 211, 160, 0.14); }

		.meta-grid {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 12px;
		}

		.meta {
			padding: 16px;
			border-radius: 18px;
			background: rgba(255, 255, 255, 0.06);
			border: 1px solid rgba(255, 255, 255, 0.08);
		}

		.meta span {
			display: block;
			color: var(--muted);
			font-size: 0.85rem;
			margin-bottom: 6px;
		}

		.meta strong {
			display: block;
			font-size: 1rem;
			word-break: break-word;
		}

		.reports {
			display: grid;
			gap: 14px;
		}

		#map {
			width: 100%;
			height: 320px;
			border-radius: 14px;
			border: 1px solid rgba(255, 255, 255, 0.08);
			background: rgba(255,255,255,0.03);
		}

		.report {
			display: grid;
			grid-template-columns: 110px 1fr;
			gap: 12px;
			align-items: start;
			padding: 12px;
			border-radius: 18px;
			background: rgba(255, 255, 255, 0.06);
			border: 1px solid rgba(255, 255, 255, 0.08);
		}

		.report img {
			width: 110px;
			height: 110px;
			object-fit: cover;
			border-radius: 14px;
			border: 1px solid rgba(255, 255, 255, 0.1);
		}

		.report h3 {
			margin: 0 0 4px;
			font-size: 1rem;
		}

		.report p {
			margin: 0;
			color: var(--muted);
			line-height: 1.5;
			font-size: 0.92rem;
		}

		@media (max-width: 900px) {
			.grid { grid-template-columns: 1fr; }
			.report { grid-template-columns: 1fr; }
			.report img { width: 100%; height: 220px; }
			.meta-grid { grid-template-columns: 1fr; }
		}
	</style>
</head>
<body>
	<div class="shell">
		<section class="hero">
			<p class="eyebrow">Amazon field reporting</p>
			<h1>Geotag illegal mining evidence in the field.</h1>
			<p class="subtitle">
				Capture a photo, record GPS coordinates from the device, and save the report to CSV.
				The app is built for evidence collection in remote Amazon locations and can be extended to
				a production database later.
			</p>
		</section>

		<main class="grid">
			<section class="card">
				<div class="content camera-wrap">
					<div>
						<h2 class="panel-title">Capture and upload evidence</h2>
						<p class="panel-copy">Open the camera, take a photo, and let the browser attach the location before saving.</p>
					</div>

					<video id="video" autoplay playsinline></video>
					<canvas id="canvas"></canvas>
					<img id="photoPreview" class="photo-preview" alt="Captured photo preview" />

					<div class="button-row">
						<button type="button" class="secondary" id="startCamera">Start camera</button>
						<button type="button" class="ghost" id="capturePhoto">Capture photo</button>
						<button type="button" class="ghost" id="retakePhoto">Retake</button>
					</div>

					<form id="reportForm">
						<label>
							Site / zone name
							<input id="siteName" name="siteName" placeholder="Example: Madre de Dios riverbank" required />
						</label>

						<label>
							Notes
							<textarea id="notes" name="notes" placeholder="Describe what was observed, nearby landmarks, and any safety details."></textarea>
						</label>

						<div class="meta-grid">
							<div class="meta">
								<span>Latitude</span>
								<strong id="latitudeValue">Waiting for GPS</strong>
							</div>
							<div class="meta">
								<span>Longitude</span>
								<strong id="longitudeValue">Waiting for GPS</strong>
							</div>
						</div>

						<input type="hidden" id="latitude" />
						<input type="hidden" id="longitude" />
						<input type="hidden" id="imageData" />

						<div class="button-row">
							<button type="button" class="secondary" id="locateMe">Get geotag</button>
							<button type="button" class="secondary" id="downloadCsv">Download CSV</button>
							<button type="submit" class="primary">Save to database</button>
						</div>
					</form>

					<div id="status" class="status">No report submitted yet.</div>
				</div>
			</section>

			<section class="card">
				<div class="content">
					<h2 class="panel-title">Latest reports</h2>
					<p class="panel-copy">Recent records stored in CSV. Images are base64-encoded in the file and exposed through the app.</p>
					<div class="controls">
						<div class="toggle" id="controlsToggle">
							<span>Map controls</span>
							<span class="arrow" id="controlsArrow">▾</span>
						</div>
						<div class="panel" id="controlsPanel">
							<div style="display:flex;justify-content:space-between;align-items:center;">
								<label><input type="checkbox" id="showHeat" checked /> Show heatmap</label>
								<label><input type="checkbox" id="showThumbs" checked /> Show sample thumbnails</label>
							</div>
							<div class="data-preview" id="dataPreview">
								<div class="stats" id="previewStats">0 reports</div>
								<div class="thumbs" id="previewThumbs"></div>
							</div>
						</div>
					</div>
					<div id="map"></div>
					<div style="height:12px"></div>
					<div id="reports" class="reports"></div>
				</div>
			</section>
		</main>
	</div>

	<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
	<script src="https://unpkg.com/leaflet.heat/dist/leaflet-heat.js"></script>

	<script>
		const video = document.getElementById('video');
		const canvas = document.getElementById('canvas');
		const photoPreview = document.getElementById('photoPreview');
		const startCameraButton = document.getElementById('startCamera');
		const capturePhotoButton = document.getElementById('capturePhoto');
		const retakePhotoButton = document.getElementById('retakePhoto');
		const downloadCsvButton = document.getElementById('downloadCsv');
		const locateMeButton = document.getElementById('locateMe');
		const reportForm = document.getElementById('reportForm');
		const statusBox = document.getElementById('status');
		const imageDataField = document.getElementById('imageData');
		const latitudeField = document.getElementById('latitude');
		const longitudeField = document.getElementById('longitude');
		const latitudeValue = document.getElementById('latitudeValue');
		const longitudeValue = document.getElementById('longitudeValue');
		const reportsContainer = document.getElementById('reports');

		const mapDiv = document.getElementById('map');
		let map = null;
		let heatLayer = null;

		const controlsToggle = document.getElementById('controlsToggle');
		const controlsPanel = document.getElementById('controlsPanel');
		const controlsArrow = document.getElementById('controlsArrow');
		const showHeatCheckbox = document.getElementById('showHeat');
		const showThumbsCheckbox = document.getElementById('showThumbs');
		const previewStats = document.getElementById('previewStats');
		const previewThumbs = document.getElementById('previewThumbs');

		controlsToggle?.addEventListener('click', () => {
			if (!controlsPanel) return;
			const open = controlsPanel.style.display !== 'block';
			controlsPanel.style.display = open ? 'block' : 'none';
			if (controlsArrow) controlsArrow.classList.toggle('open', open);
		});

		function initMap() {
			if (!mapDiv || map) return;
			map = L.map('map').setView([-9.19, -75.0152], 5);
			L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
				attribution: '&copy; OpenStreetMap contributors'
			}).addTo(map);
		}

		function updateHeatmap(reports) {
			if (!Array.isArray(reports)) return;
			initMap();
			const points = reports.map(r => [Number(r.latitude), Number(r.longitude), 0.75]).filter(p => Number.isFinite(p[0]) && Number.isFinite(p[1]));
			if (heatLayer && map) {
				map.removeLayer(heatLayer);
				heatLayer = null;
			}
			if (points.length && map && (showHeatCheckbox ? showHeatCheckbox.checked : true)) {
				heatLayer = L.heatLayer(points, { radius: 25, blur: 15, maxZoom: 17 }).addTo(map);
				try {
					const latlngs = points.map(p => [p[0], p[1]]);
					const bounds = L.latLngBounds(latlngs);
					map.fitBounds(bounds.pad(0.2));
				} catch (e) {
					// ignore fitBounds errors
				}
			} else if (map) {
				map.setView([-9.19, -75.0152], 5);
			}

			// update preview stats and thumbs
			if (previewStats) previewStats.textContent = `${reports.length} reports`;
			if (previewThumbs) {
				previewThumbs.innerHTML = '';
				if (showThumbsCheckbox && showThumbsCheckbox.checked) {
					const sample = reports.slice(0, 4);
					for (const r of sample) {
						const img = document.createElement('img');
						img.src = `/api/reports/${r.id}/image`;
						previewThumbs.appendChild(img);
					}
				}
			}
		}

		let stream = null;

		function setStatus(message, kind = '') {
			statusBox.className = kind ? `status ${kind}` : 'status';
			statusBox.textContent = message;
		}

		function stopCamera() {
			if (stream) {
				stream.getTracks().forEach(track => track.stop());
				stream = null;
			}
			video.srcObject = null;
		}

		async function startCamera() {
			try {
				stopCamera();
				stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
				video.srcObject = stream;
				setStatus('Camera ready. Capture a frame when you are positioned over the site.', '');
			} catch (error) {
				setStatus(`Camera error: ${error.message}`, 'error');
			}
		}

		function capturePhoto() {
			if (!video.videoWidth || !video.videoHeight) {
				setStatus('Start the camera before capturing a photo.', 'error');
				return;
			}

			canvas.width = video.videoWidth;
			canvas.height = video.videoHeight;
			const context = canvas.getContext('2d');
			context.drawImage(video, 0, 0, canvas.width, canvas.height);

			const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
			imageDataField.value = dataUrl;
			photoPreview.src = dataUrl;
			photoPreview.style.display = 'block';
			canvas.style.display = 'none';
			setStatus('Photo captured. You can add notes and save the report.', 'success');
		}

		function retakePhoto() {
			imageDataField.value = '';
			photoPreview.removeAttribute('src');
			photoPreview.style.display = 'none';
			setStatus('Ready for a new capture.', '');
		}

		function getLocation() {
			if (!navigator.geolocation) {
				setStatus('Geolocation is not available in this browser.', 'error');
				return;
			}

			navigator.geolocation.getCurrentPosition(
				position => {
					const { latitude, longitude } = position.coords;
					latitudeField.value = String(latitude);
					longitudeField.value = String(longitude);
					latitudeValue.textContent = latitude.toFixed(6);
					longitudeValue.textContent = longitude.toFixed(6);
					setStatus('Geolocation attached to the current report.', 'success');
				},
				error => {
					setStatus(`Location error: ${error.message}`, 'error');
				},
				{ enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
			);
		}

		async function loadReports() {
			const response = await fetch('/api/reports');
			const payload = await response.json();
			const reports = Array.isArray(payload) ? payload : payload.items || payload.reports || [];

			reportsContainer.innerHTML = '';

			if (!reports.length) {
				reportsContainer.innerHTML = '<div class="status">No saved reports yet.</div>';
				updateHeatmap([]);
				return;
			}

			for (const report of reports) {
				const item = document.createElement('article');
				item.className = 'report';
				item.innerHTML = `
					<img src="/api/reports/${report.id}/image" alt="Report image" />
					<div>
						<h3>${report.site_name}</h3>
						<p><strong>Time:</strong> ${report.created_at}</p>
						<p><strong>Coordinates:</strong> ${Number(report.latitude).toFixed(6)}, ${Number(report.longitude).toFixed(6)}</p>
						<p><strong>Notes:</strong> ${report.notes || 'No notes provided.'}</p>
					</div>
				`;
				reportsContainer.appendChild(item);
			}

			// update heatmap with latest coordinates
			updateHeatmap(reports);
		}

		reportForm.addEventListener('submit', async event => {
			event.preventDefault();

			const siteName = document.getElementById('siteName').value.trim();
			const notes = document.getElementById('notes').value.trim();
			const latitude = latitudeField.value;
			const longitude = longitudeField.value;
			const imageData = imageDataField.value;

			if (!siteName) {
				setStatus('Add a site name before saving.', 'error');
				return;
			}

			if (!latitude || !longitude) {
				setStatus('Attach GPS coordinates before saving.', 'error');
				return;
			}

			if (!imageData) {
				setStatus('Capture a photo before saving.', 'error');
				return;
			}

			const response = await fetch('/api/reports', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ site_name: siteName, notes, latitude: Number(latitude), longitude: Number(longitude), image_data_url: imageData }),
			});

			const payload = await response.json();

			if (!response.ok) {
				setStatus(payload.error || 'Could not save report.', 'error');
				return;
			}

			setStatus(`Report saved with ID ${payload.report_id}.`, 'success');
			reportForm.reset();
			retakePhoto();
			await loadReports();
		});

		startCameraButton.addEventListener('click', startCamera);
		capturePhotoButton.addEventListener('click', capturePhoto);
		retakePhotoButton.addEventListener('click', retakePhoto);
		downloadCsvButton.addEventListener('click', () => {
			window.location.href = '/download-csv';
		});
		locateMeButton.addEventListener('click', getLocation);

		window.addEventListener('beforeunload', stopCamera);

		getLocation();
		loadReports().catch(error => setStatus(`Could not load reports: ${error.message}`, 'error'));
	</script>
</body>
</html>
"""


class MiningReportHandler(BaseHTTPRequestHandler):
		def _send_json(self, payload: dict[str, object], status: int = HTTPStatus.OK) -> None:
				body = json.dumps(payload).encode("utf-8")
				self.send_response(status)
				self.send_header("Content-Type", "application/json; charset=utf-8")
				self.send_header("Content-Length", str(len(body)))
				self.send_header("Cache-Control", "no-store")
				self.end_headers()
				self.wfile.write(body)

		def _send_text(self, body: str, status: int = HTTPStatus.OK, content_type: str = "text/html; charset=utf-8") -> None:
				data = body.encode("utf-8")
				self.send_response(status)
				self.send_header("Content-Type", content_type)
				self.send_header("Content-Length", str(len(data)))
				self.send_header("Cache-Control", "no-store")
				self.end_headers()
				self.wfile.write(data)

		def do_GET(self) -> None:  # noqa: N802
				parsed = urlparse(self.path)

				if parsed.path == "/":
						self._send_text(build_html())
						return

				if parsed.path == "/api/reports":
						self._send_json({"items": list_reports()})
						return

				if parsed.path == "/download-csv":
					initialize_storage()
					csv_bytes = REPORTS_CSV_PATH.read_bytes()
					self.send_response(HTTPStatus.OK)
					self.send_header("Content-Type", "text/csv; charset=utf-8")
					self.send_header("Content-Length", str(len(csv_bytes)))
					self.send_header("Content-Disposition", 'attachment; filename="illegal_mining_reports.csv"')
					self.send_header("Cache-Control", "no-store")
					self.end_headers()
					self.wfile.write(csv_bytes)
					return

				if parsed.path.startswith("/api/reports/") and parsed.path.endswith("/image"):
						report_id_text = parsed.path.removeprefix("/api/reports/").removesuffix("/image").strip("/")

						if not report_id_text.isdigit():
								self._send_json({"error": "Invalid report id."}, HTTPStatus.BAD_REQUEST)
								return

						image_data = get_report_image(int(report_id_text))
						if image_data is None:
								self._send_json({"error": "Report not found."}, HTTPStatus.NOT_FOUND)
								return

						image_mime, image_blob = image_data
						self.send_response(HTTPStatus.OK)
						self.send_header("Content-Type", image_mime)
						self.send_header("Content-Length", str(len(image_blob)))
						self.send_header("Cache-Control", "no-store")
						self.end_headers()
						self.wfile.write(image_blob)
						return

				self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

		def do_POST(self) -> None:  # noqa: N802
				parsed = urlparse(self.path)

				if parsed.path != "/api/reports":
						self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
						return

				content_length = int(self.headers.get("Content-Length", "0"))
				raw_body = self.rfile.read(content_length)

				try:
						payload = json.loads(raw_body.decode("utf-8"))
				except json.JSONDecodeError:
						self._send_json({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
						return

				site_name = str(payload.get("site_name", "")).strip()
				notes = str(payload.get("notes", "")).strip()
				latitude = payload.get("latitude")
				longitude = payload.get("longitude")
				image_data_url = str(payload.get("image_data_url", ""))

				if not site_name:
						self._send_json({"error": "site_name is required."}, HTTPStatus.BAD_REQUEST)
						return

				if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
						self._send_json({"error": "latitude and longitude are required."}, HTTPStatus.BAD_REQUEST)
						return

				if not image_data_url.startswith("data:") or "," not in image_data_url:
						self._send_json({"error": "image_data_url must be a data URL."}, HTTPStatus.BAD_REQUEST)
						return

				header, encoded_image = image_data_url.split(",", 1)
				image_mime = header[5:header.index(";")] if ";" in header else "image/jpeg"

				try:
						image_blob = base64.b64decode(encoded_image, validate=True)
				except (ValueError, base64.binascii.Error):
						self._send_json({"error": "Image data could not be decoded."}, HTTPStatus.BAD_REQUEST)
						return

				report_id = save_report(site_name, notes, float(latitude), float(longitude), image_mime, image_blob)
				self._send_json({"report_id": report_id, "message": "Report saved."}, HTTPStatus.CREATED)

		def log_message(self, format: str, *args: object) -> None:
				return


def main() -> None:
		initialize_storage()
		host = "0.0.0.0"
		port = int(os.environ.get("PORT", "8000"))
		server = ThreadingHTTPServer((host, port), MiningReportHandler)
		print(f"Amazon mining geo-tag reporter running on {host}:{port}")
		try:
				server.serve_forever()
		except KeyboardInterrupt:
				print("Shutting down...")
		finally:
				server.server_close()


if __name__ == "__main__":
		main()
