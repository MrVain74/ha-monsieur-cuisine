# Testing & helping with other models

🌐 **English** · [Deutsch](TESTEN.md)

Thanks for helping test this **alpha**! This page has two parts: general testing,
and a short guide for owners of **other Monsieur Cuisine models**.

> 🔒 **Never post credentials, tokens or device IDs publicly** (issues, forum,
> screenshots). How to clean a log before sharing is explained below.

## Everyone: report bugs & wishes
1. Install via HACS (see [Setup](SETUP.md)).
2. Use it and note anything that breaks or that you'd like to see.
3. Open a **GitHub issue**: https://github.com/MrVain74/ha-monsieur-cuisine/issues
   (one issue per topic is easiest). Include your integration version, your model,
   and your Home Assistant version.

## Owners of other models (MC Compact / Connect / Plus)
Only the **MC Smart (MC3.0)** is tested so far. To support your model **without
owning it**, we need a short sample of the raw live data your device sends over
the cloud. No packet sniffer needed — the integration can log it for you.

### 1. Enable debug logging
- **UI:** Settings → Devices & Services → **Monsieur Cuisine** → ⋮ → **Enable
  debug logging**.
- **or `configuration.yaml`:**
  ```yaml
  logger:
    logs:
      custom_components.monsieur_cuisine: debug
  ```
  then restart / reload Home Assistant.

### 2. Cook a short, defined sequence
With the device **on and connected**, do a few simple actions and **note what the
display shows** at each moment (temperature, speed, remaining time, mode). For
example:
- Heat water: e.g. 60 °C, speed 1, 3 min — note the displayed values.
- Change the speed (e.g. to 4).
- If possible, start a **guided recipe** and advance one step.

Keep it short (a couple of minutes). The clock time per action helps us match
log lines to what you saw.

### 3. Collect the log
- **UI:** ⋮ → **Disable debug logging** → Home Assistant offers the log file for
  download.
- **or** filter your log (Settings → System → Logs) for **`Rohframe`**. The lines
  look like:
  ```
  MC-Live Rohframe: model=… connected=True extraInfo={…} hexCommand={…}
  ```

### 4. Anonymize, then send
Before sharing, **mask anything that looks like an account/device identifier, a
token, or your e-mail** (replace with `xxx`). **Keep the cooking values**
(temperature, speed, time, mode) — those are exactly what we decode.

Send the cleaned lines plus your notes (what the display showed) via a
**GitHub issue** or the forum thread.

Thank you for helping! 🙌
