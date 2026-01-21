import json
import urllib.parse
import urllib.request


def ensure_http_scheme(host: str) -> str:
	"""Ensure the host string includes an http scheme.

	If the user enters just an IP or hostname, prefix with http://.
	"""
	if not host:
		return host
	parsed = urllib.parse.urlparse(host)
	# Check if scheme is missing or not a valid HTTP scheme
	if not parsed.scheme or parsed.scheme not in ("http", "https"):
		return f"http://{host}"
	return host


class RobotApiClient:
	"""Minimal HTTP client for the robot REST API using urllib (stdlib only)."""

	def __init__(self, host: str | None = None, timeout_seconds: float = 10.0) -> None:
		self._timeout_seconds = timeout_seconds
		self._base_url = ""
		self._last_response_metadata: dict = {}  # Store metadata for debug purposes
		if host:
			self.set_host(host)

	def set_host(self, host: str) -> None:
		# Base URL format: http://{host}/universal-robots/robot-api
		base = ensure_http_scheme(host).rstrip("/")
		self._base_url = f"{base}/universal-robots/robot-api"

	def _build_url(self, path: str) -> str:
		return f"{self._base_url}{path}"

	def get_last_response_metadata(self) -> dict:
		"""Return metadata from the last successful HTTP response for debug purposes."""
		return self._last_response_metadata.copy()

	def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
		url = self._build_url(path)
		data_bytes = None
		headers = {"Accept": "application/json"}
		if payload is not None:
			data_bytes = json.dumps(payload).encode("utf-8")
			headers["Content-Type"] = "application/json"

		# Follow up to 3 redirects (e.g., 307 http -> https) for non-GET as well
		max_redirects = 3
		for _ in range(max_redirects + 1):
			req = urllib.request.Request(url=url, data=data_bytes, headers=headers, method=method)
			try:
				with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
					# Store metadata for debug purposes
					self._last_response_metadata = {
						"method": method,
						"url": url,
						"status": resp.status,
						"headers": dict(resp.headers),
						"request_body": payload,
					}
					content_type = resp.headers.get("Content-Type", "")
					raw = resp.read()
					if "application/json" in content_type:
						try:
							return json.loads(raw.decode("utf-8")) if raw else {}
						except json.JSONDecodeError:
							# Fall back to text when payload isn't valid JSON
							return {"_raw": raw.decode("utf-8", errors="replace")}
					return {"_raw": raw.decode("utf-8", errors="replace")}
			except urllib.error.HTTPError as err:
				# Handle explicit redirect for methods like PUT: 307/308
				if err.code in (307, 308):
					location = err.headers.get("Location") if err.headers else None
					if location:
						# Parse both URLs to preserve port from original if redirect strips it
						original_parsed = urllib.parse.urlparse(url)
						location_parsed = urllib.parse.urlparse(location)
						
						# If redirect is absolute but missing port, preserve original port
						if location_parsed.scheme and location_parsed.netloc:
							# Check if location has no port but original does
							if ':' in original_parsed.netloc and ':' not in location_parsed.netloc:
								# Extract port from original
								original_host, original_port = original_parsed.netloc.rsplit(':', 1)
								# Add port to redirect location
								new_netloc = f"{location_parsed.netloc}:{original_port}"
								location_parsed = location_parsed._replace(netloc=new_netloc)
								location = urllib.parse.urlunparse(location_parsed)
						
						url = urllib.parse.urljoin(url, location)
						continue
				# Propagate other HTTP errors to caller
				raise

	def get_program_state(self) -> dict:
		return self._request("GET", "/program/v1/state")

	def set_program_action(self, action: str) -> dict:
		return self._request("PUT", "/program/v1/state", {"action": action})

	def load_program(self, program_name: str) -> dict:
		return self._request("PUT", "/program/v1/load", {"programName": program_name})

	def set_robot_state(self, action: str) -> dict:
		return self._request("PUT", "/robotstate/v1/state", {"action": action})

	def get_safety_mode(self) -> dict:
		return self._request("GET", "/robotstate/v1/safetymode")

	def get_robot_mode(self) -> dict:
		return self._request("GET", "/robotstate/v1/robotmode")

	def get_control_mode(self) -> dict:
		return self._request("GET", "/system/v1/controlmode")

	def get_operational_mode(self) -> dict:
		return self._request("GET", "/system/v1/operationalmode")

	def get_programs_list(self) -> dict:
		return self._request("GET", "/programs/v1")

	def get_program_by_name(self, name: str) -> dict:
		return self._request("GET", f"/programs/v1/{name}")


