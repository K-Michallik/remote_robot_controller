## Remote Robot Controller

Desktop GUI to control a Polyscope X Universal Robots robot via the Robot API. The app provides quick access to robot state actions, program loading and execution, and live status feedback over HTTP.

![Remote Robot Controller GUI](resources/remote_controller_gui.png)

### Features
- **Robot State controls**: `UNLOCK_PROTECTIVE_STOP`, `RESTART_SAFETY`, `POWER_OFF`, `POWER_ON`, `BRAKE_RELEASE`
- **Robot Status monitoring**: View safety mode (NORMAL, REDUCED, FAULT, PROTECTIVE_STOP, EMERGENCY_STOP) and robot mode (POWER_OFF, IDLE, RUNNING, etc.)
- **System Status monitoring**: View control mode (LOCAL/REMOTE) and operational mode (MANUAL/AUTOMATIC)
- **Program management**: Load by name, control program state (`play`, `pause`, `stop`, `resume`), and list available programs. Note: provide the program name only (do not include the `.urpx` extension) or the command will fail.
- **Programs List**: Retrieve and display all programs available on the robot
- **Connection status**: Visual indicator and log panel with optional debug details
- **No external deps**: Pure Python stdlib (Tkinter + urllib)

### Requirements
- Python 3.10+
- A Universal Robots controller running Polyscope X
- Robot in **Remote Control** mode for most commands
- Network connectivity to the controller

#### Enabling Remote Control Mode
To use this application, you must first enable **Remote Control** mode on your UR robot. In Polyscope X, navigate to the Safety Overview and select **Remote** as the Control mode (you must already be in Automatic mode to enable it):

![Remote Control Selection](resources/remote_control_selection.png)

**Note:** Most robot state and program control commands will only work when the robot is in Remote Control mode.


### Running the App
You can run as a script or as a module. After cloning the repo you can run the following in a terminal:

```bash
# From repo root (inside remote_robot_controller/)
python app.py
```

Module form must be run from the directory that contains the `remote_robot_controller/` folder (i.e., the parent of the repo folder):

```bash
# From the parent directory that contains remote_robot_controller/
python -m remote_robot_controller.app
```

Enter the robot controller host/IP and click **Connect**. Use the provided buttons to send actions and manage programs. The log panel shows concise messages; enable **Debug** for full HTTP details (status, URL, headers, body) when troubleshooting.

**Connection Examples:**
- Physical robot: `10.0.0.5` or `192.168.1.100`
- URSim on default port: `localhost` or `127.0.0.1`
- URSim on custom port: `localhost:50020` or `127.0.0.1:50020`

> **Note:** The app automatically adds `http://` if no scheme is provided. You can also use `https://` if needed.

### REST Endpoints
All endpoints are served under the base URL:

```
http://{host}/universal-robots/robot-api
```

#### Robot State Domain
Provides control over the robot's operational state and status information.

```
PUT /robotstate/v1/state
Request: { "action": "UNLOCK_PROTECTIVE_STOP" }
Supported actions:
  UNLOCK_PROTECTIVE_STOP | RESTART_SAFETY | POWER_OFF | POWER_ON | BRAKE_RELEASE

Responses:
  200 OK – State changed successfully
  409 Conflict – Invalid state transition (e.g., not in PROTECTIVE_STOP)
  500 Internal Server Error
  504 Gateway Timeout
  422 Validation Error

GET /robotstate/v1/safetymode
Response: { "mode": "NORMAL" | "REDUCED" | "FAULT" | "PROTECTIVE_STOP" | "EMERGENCY_STOP" }
Responses:
  200 OK | 408 Request Timeout | 500 Internal Server Error

GET /robotstate/v1/robotmode
Response: { "mode": "NO_CONTROLLER" | "DISCONNECTED" | "CONFIRM_SAFETY" | "BOOTING" | 
           "POWER_OFF" | "POWER_ON" | "IDLE" | "BACKDRIVE" | "RUNNING" | "UPDATING" }
Responses:
  200 OK | 500 Internal Server Error
```

#### System Domain
Provides system-level information about the robot.

```
GET /system/v1/controlmode
Response: { "mode": "LOCAL" | "REMOTE" }
Responses:
  200 OK | 408 Request Timeout | 500 Internal Server Error

GET /system/v1/operationalmode
Response: { "mode": "MANUAL" | "AUTOMATIC" }
Responses:
  200 OK | 500 Internal Server Error
```

#### Program Domain
Provides control over individual robot programs.

```
PUT /program/v1/load
Request: { "programName": "example" }
Responses:
  200 OK | 500 Internal Server Error | 422 Validation Error

PUT /program/v1/state
Request: { "action": "play" }
Supported actions: play | pause | stop | resume
Responses:
  200 OK | 500 Internal Server Error | 422 Validation Error

GET /program/v1/state
Responses:
  200 OK | 500 Internal Server Error
```

#### Programs Domain
Provides control over the robot's program library.

```
GET /programs/v1
Response: { "programs": [ProgramInformation], "message": "string" }
Responses:
  200 OK | 500 Internal Server Error

GET /programs/v1/{name}
Function: Download program by name (.urpx file)
Responses:
  200 OK – program streamed | 404 Program not found | 422 Validation Error | 500 Internal Server Error

POST /programs/v1
Function: Import program from .urpx file
Request format: multipart/form-data
Responses:
  200 OK | 400 Program with this name already exists | 403 Forbidden | 
  422 Invalid .urpx file format | 500 Internal Server Error

PUT /programs/v1
Function: Update existing program from .urpx file
Request format: multipart/form-data
Responses:
  200 OK | 403 Forbidden | 404 Program not found | 409 Program is loaded and active | 
  422 Validation Error | 500 Internal Server Error
```

#### Developer Notes
- Error handling uses standardized schemas: `APIError`, `APIResponse`, `HTTPValidationError`.
- Use `RobotStateResponse` and `LoadProgramRequest` schemas for structured communication.


### Troubleshooting
- Verify the controller is reachable (ping the host/IP) and in Remote Control mode.
- If HTTPS redirection is used (307/308), the client will follow up to 3 redirects.
- Use the **Debug** checkbox to see detailed HTTP errors and response bodies.
- Ensure program names match exactly when loading via `PUT /program/v1/load`.



