import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext

try:
	from remote_robot_controller.client import RobotApiClient  # when run as a script
except Exception:
	try:
		from .client import RobotApiClient  # when run as a module
	except Exception: 
		from client import RobotApiClient


class _Tooltip:
	def __init__(self, widget: tk.Widget, text: str) -> None:
		self.widget = widget
		self.text = text
		self.tipwindow: tk.Toplevel | None = None
		self.widget.bind("<Enter>", self._show)
		self.widget.bind("<Leave>", self._hide)
		self.widget.bind("<ButtonPress>", self._hide)

	def _show(self, _event=None) -> None:
		if self.tipwindow or not self.text:
			return
		x = self.widget.winfo_rootx() + 20
		y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
		self.tipwindow = tw = tk.Toplevel(self.widget)
		tw.wm_overrideredirect(True)
		tw.wm_geometry(f"+{x}+{y}")
		label = tk.Label(
			tw,
			text=self.text,
			justify=tk.LEFT,
			background="#ffffe0",
			relief=tk.SOLID,
			borderwidth=1,
			padx=6,
			pady=4,
			wraplength=320,
		)
		label.pack(ipadx=1)

	def _hide(self, _event=None) -> None:
		if self.tipwindow:
			self.tipwindow.destroy()
			self.tipwindow = None


def attach_tooltip(widget: tk.Widget, text: str) -> None:
	_Tooltip(widget, text)


class RemoteRobotControllerApp:
	def __init__(self, root: tk.Tk) -> None:
		self.root = root
		self.root.title("Remote Robot Controller")

		self.client = RobotApiClient()

		# Top connection frame
		conn_frame = ttk.Frame(self.root, padding=8)
		conn_frame.grid(row=0, column=0, sticky="nsew")
		self.root.grid_rowconfigure(0, weight=0)
		self.root.grid_columnconfigure(0, weight=1)

		self.host_var = tk.StringVar()
		self.connection_status_var = tk.StringVar(value="Not Connected")

		ttk.Label(conn_frame, text="Robot Host/IP:").grid(row=0, column=0, padx=(0, 8), sticky="w")
		self.host_entry = ttk.Entry(conn_frame, textvariable=self.host_var, width=28)
		self.host_entry.grid(row=0, column=1, padx=(0, 8), sticky="we")
		conn_frame.grid_columnconfigure(1, weight=1)

		self.connect_button = ttk.Button(conn_frame, text="Connect", command=self.on_connect)
		self.connect_button.grid(row=0, column=2, padx=(0, 8))

		# Connection indicator (canvas circle)
		self.indicator_canvas = tk.Canvas(conn_frame, width=16, height=16, highlightthickness=0)
		self.indicator_canvas.grid(row=0, column=3, padx=(0, 8))
		self.indicator_oval = self.indicator_canvas.create_oval(2, 2, 14, 14, fill="gray", outline="black")

		self.connection_status_label = ttk.Label(conn_frame, textvariable=self.connection_status_var)
		self.connection_status_label.grid(row=0, column=4, sticky="w")

		# Separator
		separator1 = ttk.Separator(self.root, orient="horizontal")
		separator1.grid(row=1, column=0, sticky="ew", pady=(4, 4))

		# Robot State controls
		robot_frame = ttk.LabelFrame(self.root, text="Robot State", padding=8)
		robot_frame.grid(row=2, column=0, padx=8, sticky="ew")
		self.root.grid_rowconfigure(2, weight=0)

		robot_actions = [
			("UNLOCK_PROTECTIVE_STOP", self.on_unlock_protective_stop),
			("RESTART_SAFETY", self.on_restart_safety),
			("POWER_OFF", self.on_power_off),
			("POWER_ON", self.on_power_on),
			("BRAKE_RELEASE", self.on_brake_release),
		]
		for idx, (label, handler) in enumerate(robot_actions):
			btn = ttk.Button(robot_frame, text=label, command=handler)
			btn.grid(row=0, column=idx, padx=(0, 6), pady=(0, 2), sticky="w")

		# Program controls
		program_frame = ttk.LabelFrame(self.root, text="Program", padding=8)
		program_frame.grid(row=3, column=0, padx=8, sticky="ew")
		self.root.grid_rowconfigure(3, weight=0)

		# Load program
		self.program_name_var = tk.StringVar()
		ttk.Label(program_frame, text="Program Name:").grid(row=0, column=0, padx=(0, 8), sticky="w")
		self.program_entry = ttk.Entry(program_frame, textvariable=self.program_name_var, width=28)
		self.program_entry.grid(row=0, column=1, padx=(0, 8), sticky="we")
		program_frame.grid_columnconfigure(1, weight=1)
		self.load_button = ttk.Button(program_frame, text="Load", command=self.on_load_program)
		self.load_button.grid(row=0, column=2, padx=(0, 8))

		# Program actions
		actions_frame = ttk.Frame(program_frame)
		actions_frame.grid(row=1, column=0, columnspan=3, pady=(8, 0), sticky="w")
		for idx, (label, handler) in enumerate([
			("play", self.on_program_play),
			("pause", self.on_program_pause),
			("stop", self.on_program_stop),
			("resume", self.on_program_resume),
		]):
			btn = ttk.Button(actions_frame, text=label.capitalize(), command=handler)
			btn.grid(row=0, column=idx, padx=(0, 6))

		# Program state display and refresh
		state_frame = ttk.Frame(program_frame)
		state_frame.grid(row=2, column=0, columnspan=3, pady=(8, 0), sticky="w")
		self.program_state_var = tk.StringVar(value="Program state: -")
		self.program_state_label = ttk.Label(state_frame, textvariable=self.program_state_var)
		self.program_state_label.grid(row=0, column=0, padx=(0, 8))
		self.refresh_state_button = ttk.Button(state_frame, text="Refresh", command=self.on_refresh_program_state)
		self.refresh_state_button.grid(row=0, column=1)

		# Separator
		separator2 = ttk.Separator(self.root, orient="horizontal")
		separator2.grid(row=4, column=0, sticky="ew", pady=(4, 4))

		# Log area (errors and info)
		log_frame = ttk.LabelFrame(self.root, text="Log", padding=8)
		log_frame.grid(row=5, column=0, padx=8, pady=(0, 8), sticky="nsew")
		self.root.grid_rowconfigure(5, weight=1)

		# Debug toggle
		debug_row = ttk.Frame(log_frame)
		debug_row.grid(row=0, column=0, sticky="ew")
		self.debug_var = tk.BooleanVar(value=False)
		self.debug_check = ttk.Checkbutton(debug_row, text="Debug", variable=self.debug_var)
		self.debug_check.grid(row=0, column=0, sticky="w")
		attach_tooltip(self.debug_check, "When enabled, logs will include full HTTP details (status, URL, headers, and body) for troubleshooting. Disable for concise user-friendly messages.")

		self.log_widget = scrolledtext.ScrolledText(log_frame, height=8, wrap="word", state="disabled")
		self.log_widget.grid(row=1, column=0, sticky="nsew")
		log_frame.grid_rowconfigure(1, weight=1)
		log_frame.grid_columnconfigure(0, weight=1)

		# Clear log button
		self.clear_log_button = ttk.Button(log_frame, text="Clear Log", command=self.clear_log)
		self.clear_log_button.grid(row=2, column=0, sticky="e", pady=(6, 0))

		# Keyboard shortcuts
		self.root.bind("<Return>", lambda _e: self.on_connect())

	def set_indicator(self, color: str) -> None:
		self.indicator_canvas.itemconfig(self.indicator_oval, fill=color)

	def append_log(self, message: str) -> None:
		self.log_widget.configure(state="normal")
		timestamp = time.strftime("%H:%M:%S")
		self.log_widget.insert("end", f"[{timestamp}] {message}\n")
		self.log_widget.see("end")
		self.log_widget.configure(state="disabled")

	def clear_log(self) -> None:
		self.log_widget.configure(state="normal")
		self.log_widget.delete("1.0", "end")
		self.log_widget.configure(state="disabled")

	@staticmethod
	def _format_http_error(err: Exception, debug: bool = False) -> str:
		if isinstance(err, urllib.error.HTTPError):
			try:
				body = err.read().decode("utf-8", errors="replace")
			except Exception:
				body = "<no body>"
			if debug:
				# Include more context: status, url, headers, body
				status = f"HTTP {err.code}"
				url = getattr(err, 'url', '') or ''
				headers = "\n".join([f"{k}: {v}" for k, v in (err.headers.items() if err.headers else [])])
				return f"{status} {url}\n{headers}\n\n{body}"
			# Non-debug: try to parse JSON message/details
			msg = f"HTTP {err.code}"
			try:
				data = json.loads(body) if body else {}
				message = data.get("message")
				details = data.get("details")
				parts = [msg]
				if message:
					parts.append(str(message))
				if details:
					parts.append(str(details))
				return " - ".join(parts)
			except Exception:
				return f"{msg} - {body}"
		if isinstance(err, urllib.error.URLError):
			reason = getattr(err, 'reason', err)
			return f"Network error: {reason}"
		return f"Error: {err}"

	def _run_async(self, worker, on_success=None, on_error=None) -> None:
		def target():
			try:
				result = worker()
				if on_success:
					self.root.after(0, on_success, result)
			except Exception as exc:  # noqa: BLE001
				if on_error:
					self.root.after(0, on_error, exc)
		threading.Thread(target=target, daemon=True).start()

	# Handlers
	def on_connect(self) -> None:
		host = self.host_var.get().strip()
		if not host:
			self.append_log("Please enter a robot host/IP.")
			return

		self.connect_button.configure(state="disabled")
		self.connection_status_var.set("Connecting...")
		self.set_indicator("orange")
		self.client.set_host(host)

		def success(_):
			self.set_indicator("green")
			self.connection_status_var.set("Connection Success")
			self.append_log("Connected successfully.")

		def error(err: Exception):
			self.set_indicator("red")
			self.connection_status_var.set("Connection Failed")
			self.append_log(self._format_http_error(err, debug=self.debug_var.get()))

		def worker():
			# Connectivity check by calling GET /program/v1/state
			return self.client.get_program_state()

		def finally_enable():
			self.connect_button.configure(state="normal")

		def wrapped_success(result):
			try:
				success(result)
			finally:
				finally_enable()

		def wrapped_error(err):
			try:
				error(err)
			finally:
				finally_enable()

		self._run_async(worker, on_success=wrapped_success, on_error=wrapped_error)

	def on_unlock_protective_stop(self) -> None:
		self._send_robot_state_action("UNLOCK_PROTECTIVE_STOP")

	def on_restart_safety(self) -> None:
		self._send_robot_state_action("RESTART_SAFETY")

	def on_power_off(self) -> None:
		self._send_robot_state_action("POWER_OFF")

	def on_power_on(self) -> None:
		self._send_robot_state_action("POWER_ON")

	def on_brake_release(self) -> None:
		self._send_robot_state_action("BRAKE_RELEASE")

	def _send_robot_state_action(self, action: str) -> None:
		self.append_log(f"Sending robot state action: {action}")

		def worker():
			return self.client.set_robot_state(action)

		def success(_):
			self.append_log(f"Robot state action '{action}' succeeded.")

		def error(err: Exception):
			self.append_log(self._format_http_error(err, debug=self.debug_var.get()))

		self._run_async(worker, on_success=success, on_error=error)

	def on_load_program(self) -> None:
		name = self.program_name_var.get().strip()
		if not name:
			self.append_log("Please enter a program name to load.")
			return
		self.append_log(f"Loading program: {name}")

		def worker():
			return self.client.load_program(name)

		def success(_):
			self.append_log(f"Program '{name}' loaded successfully.")

		def error(err: Exception):
			self.append_log(self._format_http_error(err, debug=self.debug_var.get()))

		self._run_async(worker, on_success=success, on_error=error)

	def on_program_play(self) -> None:
		self._send_program_action("play")

	def on_program_pause(self) -> None:
		self._send_program_action("pause")

	def on_program_stop(self) -> None:
		self._send_program_action("stop")

	def on_program_resume(self) -> None:
		self._send_program_action("resume")

	def _send_program_action(self, action: str) -> None:
		self.append_log(f"Sending program action: {action}")

		def worker():
			return self.client.set_program_action(action)

		def success(_):
			self.append_log(f"Program action '{action}' succeeded.")

		def error(err: Exception):
			self.append_log(self._format_http_error(err, debug=self.debug_var.get()))

		self._run_async(worker, on_success=success, on_error=error)

	def on_refresh_program_state(self) -> None:
		self.append_log("Refreshing program state...")

		def worker():
			return self.client.get_program_state()

		def success(resp: dict):
			# Try to find a 'state' key; otherwise show raw
			state_text = None
			if isinstance(resp, dict):
				if "state" in resp:
					state_text = str(resp.get("state"))
				elif "programState" in resp:
					state_text = str(resp.get("programState"))
				elif "_raw" in resp:
					state_text = resp.get("_raw")
			if not state_text:
				state_text = json.dumps(resp)
			self.program_state_var.set(f"Program state: {state_text}")
			self.append_log("Program state refreshed.")

		def error(err: Exception):
			self.append_log(self._format_http_error(err))

		self._run_async(worker, on_success=success, on_error=error)


def main() -> None:
	root = tk.Tk()
	app = RemoteRobotControllerApp(root)
	root.minsize(720, 420)
	root.mainloop()


if __name__ == "__main__":
	main()


