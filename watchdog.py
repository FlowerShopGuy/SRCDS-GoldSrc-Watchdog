import sys
import os
# Add the current directory to path so Python can find locally installed packages
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import a2s
import requests
import time
import json

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def restart_server(server, reason="CRASH", first_signal="kill"):
    """Performs power action on the server via Pterodactyl API"""
    url = f"{server['ptero_url']}/api/client/servers/{server['server_id']}/power"
    headers = {
        "Authorization": f"Bearer {server['api_key']}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        if first_signal == "restart":
            # Pterodactyl handles STOP -> START internally when sending 'restart'
            print(f"[{server['name']}] Sending RESTART signal ({reason})...")
            resp = requests.post(url, json={"signal": "restart"}, headers=headers)
        else:
            print(f"[{server['name']}] Sending {first_signal.upper()} signal ({reason})...")
            requests.post(url, json={"signal": first_signal}, headers=headers)
            
            # Wait 10 seconds to ensure the Wings daemon processes the signal
            time.sleep(10)
            
            print(f"[{server['name']}] Sending START signal...")
            resp = requests.post(url, json={"signal": "start"}, headers=headers)
        
        if resp.status_code == 204:
            print(f"[{server['name']}] Power command successfully processed by panel.")
            return True
        else:
            print(f"[{server['name']}] API Error during start: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"[{server['name']}] Network error during API request: {e}")
        return False

def check_steam_update(app_id, current_version):
    """Checks Steam API to see if the current version is up to date"""
    # Try the original app_id first
    try:
        url = f"https://api.steampowered.com/ISteamApps/UpToDateCheck/v1/?appid={app_id}&version={current_version}"
        resp = requests.get(url, timeout=5).json()
        if resp.get("response", {}).get("success"):
            r = resp["response"]
            return not r.get("up_to_date", True), r.get("required_version", current_version)
    except Exception as e:
        pass

    # If it failed (e.g., dedicated server app_id), try getting the parent app_id
    try:
        steamcmd_url = f"https://api.steamcmd.net/v1/info/{app_id}"
        info = requests.get(steamcmd_url, timeout=5).json()
        parent_app_id = info.get("data", {}).get(str(app_id), {}).get("common", {}).get("parent")
        
        if parent_app_id:
            url = f"https://api.steampowered.com/ISteamApps/UpToDateCheck/v1/?appid={parent_app_id}&version={current_version}"
            resp = requests.get(url, timeout=5).json()
            if resp.get("response", {}).get("success"):
                r = resp["response"]
                return not r.get("up_to_date", True), r.get("required_version", current_version)
    except Exception as e:
        print(f"[Steam API Error] Failed to check for updates: {e}")
    
    return False, current_version

def main():
    config = load_config()
    global_cfg = config['global']
    
    failures = {s['server_id']: 0 for s in config.get('servers', [])}
    last_restart = {s['server_id']: 0 for s in config.get('servers', [])}
    
    update_check_counter = 0 

    print("[SYSTEM] SRCDS Watchdog + AutoUpdater started.")

    while True:
        try:
            config = load_config()
        except Exception as e:
            pass

        # Check for updates based on configured cycle count (default 10)
        cycles = global_cfg.get('update_check_cycles', 10)
        check_updates_time = global_cfg.get('check_updates', False) and (update_check_counter % cycles == 0)

        for server in config['servers']:
            sid = server['server_id']
            if sid not in failures:
                failures[sid] = 0
                last_restart[sid] = 0

            # Grace period check: prevents killing the server while it's still booting
            time_since_restart = time.time() - last_restart[sid]
            if time_since_restart < global_cfg['startup_grace_period_seconds']:
                timeLeft = int(global_cfg['startup_grace_period_seconds'] - time_since_restart)
                print(f"[{server['name']}] Server is booting. Skipping check (remaining: {timeLeft}s).")
                continue

            try:
                info = a2s.info((server['ip'], server['port']), timeout=global_cfg['timeout'])
                failures[sid] = 0
                
                print(f"[{server['name']}] OK | Map: {info.map_name} | Players: {info.player_count}/{info.max_players} | Version: {info.version}")

                # Check individual server update settings
                server_wants_updates = server.get('check_updates', True)
                
                if check_updates_time and server_wants_updates and 'app_id' in server:
                    print(f"[{server['name']}] Checking for Steam updates...")
                    needs_update, valve_version = check_steam_update(server['app_id'], info.version)
                    if needs_update:
                        print(f"[{server['name']}] UPDATE AVAILABLE! Server version: {info.version} | Valve version: {valve_version}")
                        if restart_server(server, reason="UPDATE", first_signal="kill"):
                            last_restart[sid] = time.time()
                    else:
                        print(f"[{server['name']}] Up to date. Server version: {info.version} | Valve version: {valve_version}")

            except Exception as e:
                failures[sid] += 1
                print(f"[{server['name']}] NO RESPONSE! Attempt {failures[sid]}/{global_cfg['max_failures']}")
                
                if failures[sid] >= global_cfg['max_failures']:
                    print(f"[{server['name']}] CRITICAL FAILURE! Server hung. Initiating hard restart...")
                    if restart_server(server, reason="CRASH"):
                        failures[sid] = 0
                        last_restart[sid] = time.time()

        update_check_counter += 1
        time.sleep(global_cfg['check_interval_seconds'])

if __name__ == "__main__":
    main()