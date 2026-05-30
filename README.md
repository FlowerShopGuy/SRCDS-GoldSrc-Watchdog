# SRCDS & GoldSrc Multi-Server Watchdog + Auto-Updater

A lightweight, centralized Python automation tool running as a standalone server inside **Pterodactyl Panel**. It constantly monitors your Valve game servers (Garry's Mod, Team Fortress 2, Counter-Strike 1.6, Synergy, etc.) across multiple local or remote nodes to recover them from crashes and handle automatic Steam updates cleanly.

## How It Works

1. **Crash Recovery (A2S Protocol):** Game servers running heavy Lua scripts or custom plugins can freeze completely without killing the OS process. Pterodactyl natively only tracks the PID, meaning frozen servers look "Online" in the panel. This script uses the **Source Engine Query Protocol (A2S)** to poll the game port. If a server stops responding, it issues a hard `KILL` and then a `START` command via the Pterodactyl Client API.
2. **Update Automation (Version Checking):** The script extracts the active version string from your running server and checks it directly against Valve's master servers via the Steam Web API. If a patch is pushed and your server falls behind, the script simply **restarts the server container**. If your game server container is configured to update on startup (e.g., via SteamCMD on boot), it will automatically pull the latest patch and launch fully updated.
---

## Configuration (`config.json`)

The script dynamically reloads this file every cycle. You can add, remove, or tune servers on the fly without restarting the Watchdog container itself.

```json
{
  "global": {
    "max_failures": 3,
    "timeout": 3.0,
    "check_interval_seconds": 60,
    "startup_grace_period_seconds": 300,
    "check_updates": true
  },
  "servers": [
    {
      "name": "Garry's Mod TTT Server",
      "ip": "93.84.96.73",
      "port": 27017,
      "ptero_url": "https://pterodactyl.yourdomain.net",
      "server_id": "e4f1627d",
      "api_key": "ptlc_YourClientApiKeyHere...",
      "app_id": 4000,
      "check_updates": false
    },
    {
      "name": "Synergy Co-op EU",
      "ip": "93.84.96.73",
      "port": 27015,
      "ptero_url": "https://pterodactyl.yourdomain.net",
      "server_id": "aa3a2661",
      "api_key": "ptlc_YourClientApiKeyHere...",
      "app_id": 17525
    }
  ]
}
```

### Parameter Reference

#### Global Settings (`global`)
* **`max_failures`** *(integer)*: Number of consecutive failed network connection attempts allowed before marking a server as frozen. Prevents false-positives caused by minor UDP packet drops.
* **`timeout`** *(float)*: The duration in seconds the script waits for a server response per request.
* **`check_interval_seconds`** *(integer)*: Interval between health-checks (e.g., checks all listed servers every 60 seconds).
* **`startup_grace_period_seconds`** *(integer)*: A "hands-off" countdown applied right after sending a boot command. Gives games room to pull Workshop content, mount maps, or parse heavy files without being killed during startup.
* **`check_updates`** *(boolean)*: Toggle to universally enable (`true`) or disable (`false`) Steam master version validation.

#### Per-Server Settings (`servers`)
* **`name`** *(string)*: Identifier used solely for log output readability.
* **`ip`** & **`port`** *(string/integer)*: Network coordinates of the target game instance.
* **`ptero_url`** *(string)*: The root web address of your Pterodactyl panel installation.
* **`server_id`** *(string)*: **Crucial:** The shorthand 8-character hash identifier assigned by Pterodactyl (found inside your browser's address bar when managing that server). Or in your server panel (**Settings -> Debug Information ->  Server ID**).
* **`api_key`** *(string)*: Client API key generated inside the profile dashboard (*Account -> API Credentials*) of the user account managing the targets.
* **`app_id`** *(integer)*: The exact Steam application ID (e.g., `4000` for Garry's Mod, `17525` for Synergy, `90` for CS 1.6). Required for update tracking.
* **`check_updates`** *(boolean, optional)*: Overrides the global setting. Set to `false` if you want a specific instance to skip version validations while others continue updating.

---

## Installation

### 1. Panel Setup
1. **Create Instance:** Add a new server in Pterodactyl using the **Python-Universal** EGG.
2. **Allocation:** Assign **absolutely any random network port** to the container. The script does not bind to an incoming port, but Pterodactyl strictly requires an allocation to create the Docker container.
3. **API Credentials:** Go to your account settings (**Account -> API Credentials**) and create an API key. This allows the script to manage panel power actions inside Docker. Paste the generated `ptlc_` string into your `config.json`.
4. **Startup Command:** Set the startup parameters inside the panel configuration to install requirements and run the script exactly like this:
   ```bash
   Startup Command 1: pip install -r requirements.txt
   Startup Command 2: python watchdog.py
   ```

### 2. Files Deployment
Upload the following files and place them **directly into the root folder** of your newly created container:

#### `requirements.txt`
```text
python-a2s
requests
```

#### `watchdog.py`
#### `config.json`

Click **START**. The panel container will handle dependency checks and begin active tracking routines immediately.
