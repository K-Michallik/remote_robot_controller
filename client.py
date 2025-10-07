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
		if host:
			self.set_host(host)

	def set_host(self, host: str) -> None:
		# Base URL format: http://{host}/universal-robots/robot-api
		base = ensure_http_scheme(host).rstrip("/")
		self._base_url = f"{base}/universal-robots/robot-api"

	def _build_url(self, path: str) -> str:
		return f"{self._base_url}{path}"

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


