# Setup – Monsieur Cuisine for Home Assistant (Alpha)

🌐 **English** · [Deutsch](EINRICHTUNG.md)

> **Unofficial.** Not affiliated with Lidl, SilverCrest or Tecpal. Uses the
> undocumented cloud interface of the Monsieur Cuisine app – for your **own account**
> only. May break at any time if the vendor changes things. Alpha test – feedback welcome.

## What you need
- Home Assistant (current), with [HACS](https://hacs.xyz).
- A **Monsieur Cuisine account** and a paired **Monsieur Cuisine Smart**.
- A **browser on a computer** for the one-time sign-in.
- The small **browser helper** from `browser-helper/`. It is **required** for the
  one-time sign-in – without it the login code never reaches Home Assistant
  (reason below).

## 1. Install via HACS (custom repository)
1. HACS → top right **⋮** → **Custom repositories**.
2. Repository: `https://github.com/MrVain74/ha-monsieur-cuisine`, category **Integration**, add.
3. In HACS, search for **"Monsieur Cuisine (inoffiziell)"** and **download** it.
4. **Restart Home Assistant**.

## 2. Add the integration
1. Settings → **Devices & Services** → **Add Integration**.
2. Search for **"Monsieur Cuisine"** and select it.

## 3. Sign in with Lidl
There is exactly **one** way, and after the one-time helper install it runs
through without a click.

> **Why a helper program is needed:** Lidl sends the login code only to an
> address hard-compiled into the vendor app (`lidl-com…://login/prod`). A browser
> cannot hand this address on to Home Assistant – measured in Chrome: the
> redirect is **silently discarded**, the address appears nowhere, not even in the
> address bar. So only something that can read *alongside* the page can capture it
> – hence the small browser helper.

1. Install the **browser helper** once – guide in
   [`../browser-helper/README.md`](../browser-helper/README.md), about a minute.
2. In Home Assistant, **Add Integration → Monsieur Cuisine**. First a short notice
   appears ("Browser helper ready?") – if the helper is running, click **Submit**.
3. Now click **Open website** at the bottom and sign in with Lidl: you enter
   **email, password and captcha** yourself.
4. The helper passes the login code to Home Assistant automatically. The dialog
   **closes on its own** and the device is set up.

The helper may only read redirects from `accounts.lidl.com` and nothing else.
Your password and captcha stay entirely between you and Lidl.

## 4. What you get
- **Device "Monsieur Cuisine Smart"** with:
  - **Live cooking status** (MC Smart): cooking state, operating mode, target
    temperature, speed, remaining time, recipe (name/image/ID) and step number,
    plus the binary sensors **Pre-heating** and **Scale active**. While the device
    is off, the live sensors read "unavailable".
    *(Actual temperature, lid and error code are **not** available via the cloud on
    the MC3.0 – see [How it works](HOW-IT-WORKS.md).)*
  - Diagnostic **Cloud connection** (connected/disconnected).
  - Sensor **Own recipes** (count).
- **Shopping list** as a to-do list and **Weekly planner** as a calendar from your
  account (read-only for now).
- **Action "Send recipe to Monsieur Cuisine"** (`monsieur_cuisine.send_recipe`):
  converts a recipe web page (schema.org, e.g. Chefkoch/Mealie) into a device
  recipe with machine steps.

## Troubleshooting
- **"Login failed":** The `code` is valid only briefly. Cancel the dialog and
  restart the sign-in.
- **Dialog stays on "Open website":** The browser helper is not installed or not
  active – without it the code doesn't arrive.
- **"Connection failed":** Network/cloud not reachable right now – try again later.
- **Device shows "disconnected":** The Monsieur logs itself off the cloud after a
  short while (power saving). It is connected while cooking.

## Privacy
- **No credentials** are stored – only the cloud session tokens (in the HA entry).
  Each user uses their **own account**. The captcha is never bypassed.
