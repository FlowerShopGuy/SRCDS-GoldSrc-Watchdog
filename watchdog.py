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

def restart_server(server, reason="CRASH"):
    """Always performs a hard KILL -> START sequence"""
    url = f"{server['ptero_url']}/api/client/servers/{server['server_id']}/power"
    headers = {
        "Authorization": f"Bearer {server['api_key']}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"[{server['name']}] Sending KILL signal ({reason})...")
        requests.post(url, json={"signal": "kill"}, headers=headers)
        
        # Wait 5 seconds to ensure the Wings daemon terminates the process
        time.sleep(5)
        
        print(f"[{server['name']}] Sending START signal...")
        resp = requests.post(url, json={"signal": "start"}, headers=headers)
        
        if resp.status_code == 204:
            print(f"[{server['name']}] Restart command successfully processed by panel.")
            return True
        else:
            print(f"[{server['name']}] API Error during start: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"[{server['name']}] Network error during API request: {e}")
        return False

def check_steam_update(app_id, current_version):
    """Checks Steam API to see if the current version is up to date"""
    try:
        url = f"https://api.steampowered.com/ISteamApps/UpToDateCheck/v1/?appid={app_id}&version={current_version}"
        response = requests.get(url, timeout=5).json()
        
        if response.get("response", {}).get("success"):
            is_updated = response["response"]["up_to_date"]
            return not is_updated 
    except Exception as e:
        print(f"[Steam API Error] Failed to check for updates: {e}")
    
    return False

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

        # Check for updates every 10 cycles
        check_updates_time = global_cfg.get('check_updates', False) and (update_check_counter % 10 == 0)

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
                    if check_steam_update(server['app_id'], info.version):
                        print(f"[{server['name']}] UPDATE AVAILABLE! Initiating hard restart for update...")
                        if restart_server(server, reason="UPDATE"):
                            last_restart[sid] = time.time()

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