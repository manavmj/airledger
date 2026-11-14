# Connect your Gemini key locally

AirLedger currently needs one provider key: **Google Gemini**. It does not require an OpenAI key. Create a key in [Google AI Studio](https://aistudio.google.com/apikey). Use a model available to your key; the application default is `gemini-2.5-flash`.

## Windows PowerShell — recommended for the existing local installation

1. Stop the currently running server with **Ctrl+C** in its terminal. Do not leave the old server running on port 8765.
2. Open PowerShell **inside the extracted project folder**, where `start_windows.bat` is located.
3. Run these commands, replacing the placeholder with your own key **on your computer**:

```powershell
$env:GEMINI_API_KEY = "PASTE_YOUR_GEMINI_KEY_HERE"
$env:GEMINI_MODEL = "gemini-2.5-flash"
.\start_windows.bat
```

The launcher inherits the key from that PowerShell process. The key stays in that terminal's environment; closing it does not save the setting for future launches. If you later double-click the batch file from Explorer, it will not inherit this terminal-only setting. Repeat the commands above when starting a new session.

For an installation that already has its `.venv`, you can skip the launcher's dependency check:

```powershell
.\.venv\Scripts\python.exe scripts\run_local.py
```

Use this only in the **same PowerShell window** after setting the environment variables.

## Windows Command Prompt alternative

```bat
set "GEMINI_API_KEY=PASTE_YOUR_GEMINI_KEY_HERE"
set "GEMINI_MODEL=gemini-2.5-flash"
start_windows.bat
```

These are Command Prompt commands, not PowerShell commands.

## Verify the connection

Refresh the app after restarting the server. The header should show **Gemini configured**, and AI mapping / AI briefing controls should become available. You can also open `http://127.0.0.1:8765/api/status`; `ai_configured` should be `true`.

This status means a key exists in the server environment; it does not validate it with Google. To test the actual provider call, upload `manual-tests/01_clean_baseline.csv`, review and confirm the mapping, analyse it, and compose a brief with **Use GenAI to select and prioritize evidence** checked. A successful brief is labelled **Gemini-selected evidence**. Do not confuse a rules-based brief with a successful AI call.

If the header still says **AI not connected**, the server was probably started outside the terminal where the key was set, or the old server is still running. Stop the server, set the variable, restart, and refresh.

If AI generation returns an error, check your key, model access and quota in Google AI Studio. The application deliberately does not expose provider error bodies, and it does not silently save a rules-based brief after an AI failure.

## Optional persistent setting on Windows

If you prefer to launch by double-clicking the batch file, add a **user environment variable** through Windows **Edit environment variables for your account**:

| Name | Value |
| --- | --- |
| `GEMINI_API_KEY` | Your own Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash`, or your compatible available model |

Restart the terminal/launcher so it receives the new environment. Environment variables are not an encrypted secret vault; keep access to your Windows account secure. For temporary testing, the terminal method above avoids saving the key as a persistent user setting.

## Where the key is used

`app/briefing.py` reads `GEMINI_API_KEY` and sends it to Google's Gemini endpoint in a server-side request header. The browser never needs the key. `.env.example` is documentation only; **this version does not auto-load `.env` files**.

Do not paste a real key into `app/static/`, test tables, README files, GitHub, or a chat message. There is no reason to edit the Python source to insert it. If a real key is ever published, revoke it in Google AI Studio and generate a replacement.
