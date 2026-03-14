# NMS Expeditions Online

Play any old No Man's Sky expedition **online with full multiplayer** — see other players, visit the Anomaly, and play with friends.

This tool acts as a local proxy that intercepts the game's expedition/season data and replaces it with the expedition of your choice, while leaving all other game traffic (multiplayer, discovery services, bases) completely untouched.

## How It Works

No Man's Sky checks Hello Games' servers on startup to determine which expedition is currently active. This tool:

1. Redirects NMS API traffic to a local proxy (via your system's hosts file)
2. Intercepts the season/expedition data and replaces it with your chosen expedition
3. Patches the authentication response so the game believes your expedition is the active one
4. Forwards all other traffic (discovery services, bases, multiplayer) to the real servers untouched

**Multiplayer uses Steam's peer-to-peer networking**, which is completely unaffected by this tool.

## Requirements

- **No Man's Sky** (Steam, PC)
- An expedition JSON file from [cwmonkey's NMS Expeditions tool](https://cwmonkey.github.io/nms-expeditions/)
- **Administrator/root privileges** (required to modify the hosts file and listen on port 443)

## Quick Start

### Step 1: Download Your Expedition

1. Visit [cwmonkey's NMS Expeditions](https://cwmonkey.github.io/nms-expeditions/)
2. Select the expedition you want to play
3. Apply recommended patches (optional but suggested)
4. Download the `SEASON_DATA_CACHE.JSON` file

### Step 2: Set Up the Tool

#### Windows

1. Download `NMSExpeditionsOnline.exe` from the [Releases](../../releases) page
2. Place `SEASON_DATA_CACHE.JSON` in the **same folder** as the `.exe`
3. Double-click `NMSExpeditionsOnline.exe` (it will request administrator privileges)

#### Linux

**Prerequisites:** Python 3.10+ (most distros ship with this)

**Option A — One command:**

1. [Download and extract the latest Linux release](https://github.com/BonzTM/nms-expeditions-online/releases/latest)
2. Place `SEASON_DATA_CACHE.JSON` in the project directory
3. Run:
   ```bash
   ./run.sh
   ```
   This handles sudo elevation, checks for Python, installs dependencies if needed, and starts the app.

**Option B — pip install:**

1. [Download and extract the latest Linux release](https://github.com/BonzTM/nms-expeditions-online/releases/latest)
2. Place `SEASON_DATA_CACHE.JSON` in the project directory
3. Install and run:
   ```bash
   pip install .
   sudo -E nms-expeditions-online
   ```

### Step 3: Install

1. Select **option 1 (Install)** from the menu
2. Confirm when prompted — this adds entries to your hosts file

### Step 4: Start the Proxy

1. Select **option 2 (Run)** from the menu
2. Wait for "Proxy is running!" to appear
3. **Launch No Man's Sky** through Steam as normal
4. You should see:
   - "Connected to Discovery Services" (not stuck on "Connecting")
   - Other players in the Anomaly
   - Your chosen expedition available to start

### Step 5: Play!

Play the expedition normally. Multiplayer, discovery services, and bases all work.

### When You're Done

1. Return to the tool window and press **Enter** to stop the proxy
2. Select **option 3 (Uninstall)** to restore your hosts file

## Important Warnings

### Do NOT uninstall mid-expedition

If you uninstall (remove the hosts file entries) while you have an active expedition save, **you will lose access to that expedition save**. The game will no longer recognize the expedition as active and you won't be able to continue it.

Only uninstall after you have:
- **Completed** the expedition and claimed your rewards, OR
- **Abandoned** the expedition save

### Switching expeditions

To switch to a different expedition:
1. Make sure you've completed or abandoned your current expedition
2. Stop the proxy
3. Replace the `SEASON_DATA_CACHE.JSON` file with the new expedition
4. Start the proxy again

## Troubleshooting

### "Port 443 is already in use"

Something else is using port 443. Common culprits:
- **IIS** (Internet Information Services) on Windows
- **Apache/Nginx** web servers
- **Skype** (older versions)
- **VPN software**

Close the conflicting application and try again.

### "No expedition JSON file found"

Make sure `SEASON_DATA_CACHE.JSON` is in the same directory as the executable (Windows) or the project directory (Linux).

### Game shows "No Active Expedition"

- Make sure the proxy is running (you should see "Proxy is running!" in the tool)
- Make sure you installed the hosts file entries (option 1)
- Restart NMS after starting the proxy — the game caches DNS from startup

### Game says "Connecting to Discovery Services" and never connects

- Check that the proxy window shows connection logs (like `POST https://merged-nms-auth...`)
- If the proxy is silent, restart both the proxy and NMS
- Make sure no firewall is blocking connections to localhost port 443

### Multiplayer not working

Multiplayer uses Steam's networking and should work regardless. If you don't see other players:
- Check your Steam online status
- Make sure NMS multiplayer is enabled in the game's network settings
- Try visiting the Anomaly

## How It Works (Technical Details)

The tool modifies your system's hosts file to redirect four NMS API hostnames to `127.0.0.1`:

```
127.0.0.1 merged-nms-auth.nomanssky.com
127.0.0.1 merged-nms-static.nomanssky.com
127.0.0.1 merged-nms-discovery.nomanssky.com
127.0.0.1 merged-nms-contentreport.nomanssky.com
```

A local HTTPS proxy listens on port 443 and:
- Reads the TLS SNI (Server Name Indication) to determine which server the game wants
- Generates per-hostname TLS certificates signed by a local CA
- Connects to the real NMS servers (resolved via direct DNS query to Google's `8.8.8.8`, bypassing the hosts file)
- Forwards requests and responses, modifying only:
  - `POST /season` on the static server — returns your custom expedition JSON
  - `POST /Steam` on the auth server — patches the `seasonData` to match your expedition
- All other traffic passes through unmodified

## Building from Source

### Requirements

- Python 3.10+
- `cryptography` package (`pip install cryptography`)

### Running directly

```bash
pip install cryptography
sudo python3 -m nms_expeditions_online
```

### Building the Windows .exe

On a Windows machine:

```bash
pip install cryptography pyinstaller
pyinstaller --onefile --console --uac-admin --name NMSExpeditionsOnline nms_expeditions_online/__main__.py
```

The executable will be in the `dist/` folder.

## Credits

- [cwmonkey's NMS Expeditions](https://cwmonkey.github.io/nms-expeditions/) — expedition data and patches
- Hello Games — No Man's Sky

## License

See [LICENSE](LICENSE) for details.
