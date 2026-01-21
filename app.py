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
	from .client import RobotApiClient  # when run as a module
except ImportError:
	from client import RobotApiClient  # when run as a script


# Action constants
class RobotStateAction:
	UNLOCK_PROTECTIVE_STOP = "UNLOCK_PROTECTIVE_STOP"
	RESTART_SAFETY = "RESTART_SAFETY"
	POWER_OFF = "POWER_OFF"
	POWER_ON = "POWER_ON"
	BRAKE_RELEASE = "BRAKE_RELEASE"


class ProgramAction:
	PLAY = "play"
	PAUSE = "pause"
	STOP = "stop"
	RESUME = "resume"


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
		attach_tooltip(self.host_entry, "Enter robot IP or hostname.\nExamples:\n• Physical robot: 10.0.0.5\n• URSim default: localhost\n• URSim custom port: localhost:50020")
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

		# System Status frame
		system_frame = ttk.LabelFrame(self.root, text="System Status", padding=8)
		system_frame.grid(row=2, column=0, padx=8, sticky="ew")
		self.root.grid_rowconfigure(2, weight=0)

		self.control_mode_var = tk.StringVar(value="Control Mode: -")
		self.operational_mode_var = tk.StringVar(value="Operational Mode: -")
		
		control_mode_label = ttk.Label(system_frame, textvariable=self.control_mode_var)
		control_mode_label.grid(row=0, column=0, padx=(0, 16), sticky="w")
		
		operational_mode_label = ttk.Label(system_frame, textvariable=self.operational_mode_var)
		operational_mode_label.grid(row=0, column=1, padx=(0, 16), sticky="w")
		
		refresh_system_button = ttk.Button(system_frame, text="Refresh", command=self.on_refresh_system_status)
		refresh_system_button.grid(row=0, column=2, padx=(0, 8))

		# Separator
		separator2 = ttk.Separator(self.root, orient="horizontal")
		separator2.grid(row=3, column=0, sticky="ew", pady=(4, 4))

		# Robot State controls
		robot_frame = ttk.LabelFrame(self.root, text="Robot State", padding=8)
		robot_frame.grid(row=4, column=0, padx=8, sticky="ew")
		self.root.grid_rowconfigure(4, weight=0)

		# Robot state status displays
		status_row = ttk.Frame(robot_frame)
		status_row.grid(row=0, column=0, columnspan=5, pady=(0, 8), sticky="ew")
		
		self.safety_mode_var = tk.StringVar(value="Safety: -")
		self.robot_mode_var = tk.StringVar(value="Robot: -")
		
		safety_mode_label = ttk.Label(status_row, textvariable=self.safety_mode_var)
		safety_mode_label.grid(row=0, column=0, padx=(0, 16), sticky="w")
		
		robot_mode_label = ttk.Label(status_row, textvariable=self.robot_mode_var)
		robot_mode_label.grid(row=0, column=1, padx=(0, 16), sticky="w")
		
		refresh_robot_status_button = ttk.Button(status_row, text="Refresh", command=self.on_refresh_robot_status)
		refresh_robot_status_button.grid(row=0, column=2, padx=(0, 8))

		robot_actions = [
			RobotStateAction.UNLOCK_PROTECTIVE_STOP,
			RobotStateAction.RESTART_SAFETY,
			RobotStateAction.POWER_OFF,
			RobotStateAction.POWER_ON,
			RobotStateAction.BRAKE_RELEASE,
		]
		for idx, action in enumerate(robot_actions):
			btn = ttk.Button(
				robot_frame, 
				text=action, 
				command=lambda a=action: self._send_robot_state_action(a)
			)
			btn.grid(row=1, column=idx, padx=(0, 6), pady=(0, 2), sticky="w")

		# Separator
		separator3 = ttk.Separator(self.root, orient="horizontal")
		separator3.grid(row=5, column=0, sticky="ew", pady=(4, 4))

		# Program controls
		program_frame = ttk.LabelFrame(self.root, text="Program", padding=8)
		program_frame.grid(row=6, column=0, padx=8, sticky="ew")
		self.root.grid_rowconfigure(6, weight=0)

		# Load program
		self.program_name_var = tk.StringVar()
		ttk.Label(program_frame, text="Program Name:").grid(row=0, column=0, padx=(0, 8), sticky="w")
		self.program_entry = ttk.Entry(program_frame, textvariable=self.program_name_var, width=28)
		self.program_entry.grid(row=0, column=1, padx=(0, 8), sticky="we")
		attach_tooltip(self.program_entry, "Enter program name without extension.\nExample: For 'my_robot_program.urpx' enter 'my_robot_program'")
		program_frame.grid_columnconfigure(1, weight=1)
		self.load_button = ttk.Button(program_frame, text="Load", command=self.on_load_program)
		self.load_button.grid(row=0, column=2, padx=(0, 8))

		# Program actions
		actions_frame = ttk.Frame(program_frame)
		actions_frame.grid(row=1, column=0, columnspan=3, pady=(8, 0), sticky="w")
		program_actions = [
			ProgramAction.PLAY,
			ProgramAction.PAUSE,
			ProgramAction.STOP,
			ProgramAction.RESUME,
		]
		for idx, action in enumerate(program_actions):
			btn = ttk.Button(
				actions_frame, 
				text=action.capitalize(), 
				command=lambda a=action: self._send_program_action(a)
			)
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
		separator4 = ttk.Separator(self.root, orient="horizontal")
		separator4.grid(row=7, column=0, sticky="ew", pady=(4, 4))

		# Programs list frame
		programs_list_frame = ttk.LabelFrame(self.root, text="Programs List", padding=8)
		programs_list_frame.grid(row=8, column=0, padx=8, sticky="ew")
		self.root.grid_rowconfigure(8, weight=0)

		list_button = ttk.Button(programs_list_frame, text="Get Programs List", command=self.on_get_programs_list)
		list_button.grid(row=0, column=0, sticky="w")
		attach_tooltip(list_button, "Retrieve and display the list of programs available on the robot.")

		# Separator
		separator5 = ttk.Separator(self.root, orient="horizontal")
		separator5.grid(row=9, column=0, sticky="ew", pady=(4, 4))

		# Log area (errors and info)
		log_frame = ttk.LabelFrame(self.root, text="Log", padding=8)
		log_frame.grid(row=10, column=0, padx=8, pady=(0, 8), sticky="nsew")
		self.root.grid_rowconfigure(10, weight=1)

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

	def _format_http_success(self, response_body: dict) -> str:
		"""Format successful HTTP response for debug logging."""
		metadata = self.client.get_last_response_metadata()
		if not metadata:
			return ""
		
		method = metadata.get("method", "")
		url = metadata.get("url", "")
		status = metadata.get("status", "")
		headers = metadata.get("headers", {})
		request_body = metadata.get("request_body")
		
		parts = [f"HTTP {status} {method} {url}"]
		
		# Request details
		if request_body:
			parts.append(f"\nRequest Body:\n{json.dumps(request_body, indent=2)}")
		
		# Response headers
		headers_str = "\n".join([f"{k}: {v}" for k, v in headers.items()])
		parts.append(f"\nResponse Headers:\n{headers_str}")
		
		# Response body
		if response_body:
			body_str = json.dumps(response_body, indent=2) if isinstance(response_body, dict) else str(response_body)
			parts.append(f"\nResponse Body:\n{body_str}")
		
		return "".join(parts)

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

	def _run_async(self, worker, on_success=None, on_error=None, on_finally=None) -> None:
		"""Execute a worker function asynchronously with optional callbacks."""
		def target():
			try:
				result = worker()
				if on_success:
					self.root.after(0, on_success, result)
			except Exception as exc:  # noqa: BLE001
				if on_error:
					self.root.after(0, on_error, exc)
			finally:
				if on_finally:
					self.root.after(0, on_finally)
		threading.Thread(target=target, daemon=True).start()

	def _execute_api_call(
		self,
		api_call,
		initial_message: str | None = None,
		success_message: str | None = None,
		on_success_callback=None,
		on_error_callback=None,
		on_finally=None,
	) -> None:
		"""Execute an API call with standard logging and error handling.
		
		Args:
			api_call: Function that makes the API call and returns response
			initial_message: Optional message to log before making the call
			success_message: Message to log on success
			on_success_callback: Optional callback to execute on success (in addition to logging)
			on_error_callback: Optional callback to execute on error (in addition to logging)
			on_finally: Optional callback to execute in finally block
		"""
		if initial_message:
			self.append_log(initial_message)

		def success(resp):
			if success_message:
				self.append_log(success_message)
			if self.debug_var.get():
				debug_info = self._format_http_success(resp)
				if debug_info:
					self.append_log(debug_info)
			if on_success_callback:
				on_success_callback(resp)

		def error(err: Exception):
			self.append_log(self._format_http_error(err, debug=self.debug_var.get()))
			if on_error_callback:
				on_error_callback(err)

		self._run_async(api_call, on_success=success, on_error=error, on_finally=on_finally)

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

		def on_success_callback(_resp):
			self.set_indicator("green")
			self.connection_status_var.set("Connection Success")

		def on_error_callback(_err):
			self.set_indicator("red")
			self.connection_status_var.set("Connection Failed")

		self._execute_api_call(
			api_call=self.client.get_program_state,
			success_message="Connected successfully.",
			on_success_callback=on_success_callback,
			on_error_callback=on_error_callback,
			on_finally=lambda: self.connect_button.configure(state="normal"),
		)

	def _send_robot_state_action(self, action: str) -> None:
		"""Generic handler for robot state actions."""
		self._execute_api_call(
			api_call=lambda: self.client.set_robot_state(action),
			initial_message=f"Sending robot state action: {action}",
			success_message=f"Robot state action '{action}' succeeded.",
		)

	def on_load_program(self) -> None:
		name = self.program_name_var.get().strip()
		if not name:
			self.append_log("Please enter a program name to load.")
			return

		self._execute_api_call(
			api_call=lambda: self.client.load_program(name),
			initial_message=f"Loading program: {name}",
			success_message=f"Program '{name}' loaded successfully.",
		)

	def _send_program_action(self, action: str) -> None:
		"""Generic handler for program actions."""
		self._execute_api_call(
			api_call=lambda: self.client.set_program_action(action),
			initial_message=f"Sending program action: {action}",
			success_message=f"Program action '{action}' succeeded.",
		)

	def on_refresh_program_state(self) -> None:
		def on_success_callback(resp: dict):
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

		self._execute_api_call(
			api_call=self.client.get_program_state,
			initial_message="Refreshing program state...",
			success_message="Program state refreshed.",
			on_success_callback=on_success_callback,
		)

	def on_refresh_system_status(self) -> None:
		def update_control_mode():
			def on_success_callback(resp: dict):
				mode = resp.get("mode", "-") if isinstance(resp, dict) else "-"
				self.control_mode_var.set(f"Control Mode: {mode}")
			
			self._execute_api_call(
				api_call=self.client.get_control_mode,
				on_success_callback=on_success_callback,
			)

		def update_operational_mode():
			def on_success_callback(resp: dict):
				mode = resp.get("mode", "-") if isinstance(resp, dict) else "-"
				self.operational_mode_var.set(f"Operational Mode: {mode}")
			
			self._execute_api_call(
				api_call=self.client.get_operational_mode,
				on_success_callback=on_success_callback,
			)

		self.append_log("Refreshing system status...")
		update_control_mode()
		update_operational_mode()

	def on_refresh_robot_status(self) -> None:
		def update_safety_mode():
			def on_success_callback(resp: dict):
				mode = resp.get("mode", "-") if isinstance(resp, dict) else "-"
				self.safety_mode_var.set(f"Safety: {mode}")
			
			self._execute_api_call(
				api_call=self.client.get_safety_mode,
				on_success_callback=on_success_callback,
			)

		def update_robot_mode():
			def on_success_callback(resp: dict):
				mode = resp.get("mode", "-") if isinstance(resp, dict) else "-"
				self.robot_mode_var.set(f"Robot: {mode}")
			
			self._execute_api_call(
				api_call=self.client.get_robot_mode,
				on_success_callback=on_success_callback,
			)

		self.append_log("Refreshing robot status...")
		update_safety_mode()
		update_robot_mode()

	def on_get_programs_list(self) -> None:
		def on_success_callback(resp: dict):
			if isinstance(resp, dict) and "programs" in resp:
				programs = resp.get("programs", [])
				if programs:
					programs_text = "\n".join([
						f"  - {prog.get('name', 'Unknown')}" if isinstance(prog, dict) else f"  - {prog}"
						for prog in programs
					])
					self.append_log(f"Available programs ({len(programs)}):\n{programs_text}")
				else:
					self.append_log("No programs found on the robot.")
			else:
				self.append_log(f"Programs list response: {json.dumps(resp, indent=2)}")

		self._execute_api_call(
			api_call=self.client.get_programs_list,
			initial_message="Retrieving programs list...",
			success_message="Programs list retrieved.",
			on_success_callback=on_success_callback,
		)


def main() -> None:
	root = tk.Tk()
	app = RemoteRobotControllerApp(root)
	root.minsize(720, 420)
	root.mainloop()


if __name__ == "__main__":
	main()


