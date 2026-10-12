# Monsieur Cuisine for Home Assistant (unofficial)

> ⚠️ **Unofficial.** Not affiliated with Lidl, SilverCrest or Tecpal. Uses the undocumented
> cloud interface of the Monsieur Cuisine app. May break at any time if the vendor changes things.
> For your own account only, gentle polling (max. 1 request/second, every 15 minutes).

**Status: Alpha (v0.3)** – tested with the *Monsieur Cuisine Smart* (MC3.0).

👉 **Deutsche Einrichtungsanleitung:** [`docs/EINRICHTUNG.md`](docs/EINRICHTUNG.md)

## What it does

| Feature | State |
|---|---|
| **Send recipe** (`monsieur_cuisine.send_recipe`): a recipe page (schema.org/Recipe, e.g. Chefkoch, Mealie) or JSON → your own recipe with **machine steps** | ✅ format verified |
| **Step translator**: “30 sec/speed 5”, “10 min/100 °C/reverse/speed 1”, “weigh 250 g” → device values | ✅ |
| Sensor *Own recipes* | ✅ |
| Diagnostic *Cloud connection* (device currently connected to the cloud) | ✅ |
| Sign-in (Lidl login directly in Home Assistant) | ✅ setup dialog |
| **Live cooking status** (state, target temperature, speed, remaining time) | ✅ via the cloud (gRPC), decoded – for the MC Smart; sensors in progress |
| Save recipe as “private” (shows up on the device) | ⏳ needs image upload – draft for now, add the picture on the website |
| Shopping list as a to-do list, weekly planner as a calendar | ⏳ planned |

## Example

```yaml
action: monsieur_cuisine.send_recipe
data:
  url: https://example.org/recipe/tomato-soup
  dry_run: true   # preview first
```

Response (shortened):

```yaml
title: Tomato soup
steps:
  - title: Chop
    setting: 5 sec / speed 5
  - title: Cook
    setting: 20 min / 100 °C / speed 1 / reverse
  - title: Stir in cream
    setting: null
warnings: []
```

Without `dry_run` the recipe is created as a **draft** in your account (`recipe_id` in the response).
With `recipe_id` an existing recipe of yours is overwritten.

## Translator limitations

- Turbo is not applied yet (kept as text, with a warning).
- “Varoma” is applied as 120 °C – for steaming, pick the “Steam” program instead.
- Half speeds (e.g. 4.5) are rounded up.
- Units the Monsieur Cuisine editor doesn’t know (ml, packet, can …) are appended in brackets to the ingredient name.
- Everything detected is a **suggestion** – check it in the recipe before cooking.

## Installation (HACS, custom repository)

1. HACS → top right ⋮ → **Custom repositories** → this repo, category *Integration*.
2. Install “Monsieur Cuisine (unofficial)”, restart Home Assistant.
3. Settings → Devices & Services → Add integration → *Monsieur Cuisine*.

Sign-in offers **three ways**, no DevTools and no copy-paste of anything from
developer tools:

- **Without any add-on (recommended):** HA serves a small helper page with a
  **bookmark**. You drag it to your bookmarks bar once, sign in to Lidl, and click
  it – the dialog finishes on its own. Works because HA requests the Lidl login with
  `response_mode=form_post`, so the one-time code arrives on a normal page the
  bookmark can read. No extension, no permissions.
- **With the browser helper:** a tiny add-on from [`browser-helper/`](browser-helper/)
  completes the login fully automatically (not even a click).
- **Manual:** paste the redirect address, the page source, or just the code.

Step-by-step (German): [`docs/EINRICHTUNG.md`](docs/EINRICHTUNG.md).

## Development

```bash
python3 -m pytest tests            # translator and payload
python3 tools/mc_cli.py parse "10 min/100 °C/speed 1"
python3 tools/mc_cli.py preview --schema recipe.json
```

The `mcbridge` library has no dependency on Home Assistant.

## Author

Built by **MrVain74** ([@MrVain74](https://github.com/MrVain74)). Unofficial, not affiliated with Lidl, SilverCrest or Tecpal. Thanks to everyone helping to test.

License: MIT
