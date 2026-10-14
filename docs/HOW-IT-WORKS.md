# How it works

🌐 **English** · [Deutsch](FUNKTIONSWEISE.md)

> **Unofficial.** Not affiliated with Lidl, SilverCrest or Tecpal. The integration
> uses the undocumented cloud interface of the Monsieur Cuisine app. It **reads**
> status and account data and **writes recipes only into your own account** – it
> sends **no** control commands to the device.

This page describes how the integration works. For setup see
[`SETUP.md`](SETUP.md), for version differences
[`../CHANGELOG.md`](../CHANGELOG.md).

## Model coverage

Of the four Monsieur Cuisine models, only two report a live status over the
cloud; only those are interpreted here.

| Model | Name | Live status | Status format |
|---|---|---|---|
| **MC3.0** | MC Smart | ✅ tested | structured JSON (`extraInfo`) |
| **MC0.5** | MC Compact | ✅ format decoded, untested | binary TLV frame + `extraInfo` |
| MC2.0 | MC Connect | – not networked | — |
| MC1.1 | MC Plus | – not networked | — |

The device is assigned to one of the two classes (Compact or Smart) by its
**device identifier**; the Smart is the default case. A shared parser covers both
classes with two branches.

## Live status while cooking

The live status does **not** come via ordinary HTTP polls, but over a **gRPC
stream** from the vendor cloud. The integration subscribes to this stream (push)
and keeps it open; every state change produces a message. There is no poll
interval. If the stream drops (at the latest when the device switches off after
cooking), it reconnects with growing back-off and fetches a fresh session token
beforehand.

Each message contains:

- **`extraInfo`** – a JSON object with the prepared status (cooking state,
  operating mode, target temperature, speed, remaining time, step, etc.). This is
  the authoritative source on the **MC3.0**.
- **`hexCommand`** – on the **MC0.5** additionally a binary frame (TLV) carrying,
  among other things, the actual temperature and lid state. On the **MC3.0** this
  frame is a pure **command echo** (setpoints: target temperature, speed,
  remaining time, operating mode, counter, checksum) – it carries **no measured
  values** and is not evaluated by the vendor app either. On the MC3.0 the
  authoritative source is `extraInfo`.

Values are merged from both sources and mapped onto the entities. If a single
value is missing, that entity shows "unknown"; if the whole live status is
missing (device off), it counts as "unavailable".

**Model differences worth knowing:**

- The field names in `extraInfo` differ per model (e.g. temperature and speed).
  The integration knows both name sets.
- **On the MC3.0 the cloud transmits no measured values** – no actual
  temperature, lid, weight or error-code value (checked on the real device: while
  heating up no byte moves, `extraInfo` carries no such fields). Those entities
  therefore do not exist for the MC3.0. Only **states derived from measurements**
  are transmitted (e.g. "pre-heating").
- Times can arrive as remaining time (countdown) or as elapsed time (stopwatch);
  the mode is an attribute on the remaining-time sensor.

**Entities on the MC3.0:** cooking state, operating mode, target temperature,
speed, remaining time, recipe (name/image/ID as attributes) and step number in
recipe mode, plus the binary sensors **Pre-heating** and **Scale active**. The
done message (`DONE`/`RECIPE_DONE`) works as a trigger for notifications – not
`STEP_DONE` (that reports every intermediate step).

### Recipe step text and total

When a recipe is active, the integration loads the step text and the total number
of steps once (via the recipe API, `GET api/v2/recipes/{id}`) and caches it. The
step sensor then shows "Step N of M" with the step text as an attribute. The
total depends on the selected serving size.

## Shopping list and weekly planner

Both are read from the account at a calm interval (every 30 minutes):

- **Shopping list → to-do list.** Two sources in one list: the ingredients of the
  planned recipes and freely added entries. Quantities are taken over as **text**
  (they may contain fraction glyphs like ½/¼). Read-only for now – checking items
  off and removing them from Home Assistant will follow (tracked in the issues).
- **Weekly planner → calendar.** Planned recipes appear as **all-day events** (the
  planner knows only days, no times), with the recipe name as the title and
  link/duration in the description.

## Sign-in

The user signs in with Lidl once (credentials and captcha stay between the user
and Lidl). From this login the integration obtains the vendor cloud's session
token and renews it on its own; a repeated Lidl login is not needed in normal
operation. The login runs through a small browser helper that captures the login
code and hands it to Home Assistant – see [`SETUP.md`](SETUP.md). The captcha is
never bypassed.

## Recipes

The integration converts a recipe (from a web page with schema.org data or as
JSON) into a Monsieur Cuisine recipe with **machine steps** and creates it in your
own account (as a draft at first). A recipe published as "private" appears on the
device but requires a recipe image; uploading the image currently has to be done
via the website.

## What the integration does NOT do

- It **sends no control commands** to the device (no start, stop, temperature
  setting). It only reads the status.
- It bypasses **no captcha** and stores no credentials in clear text in logs.
- It talks to **your own account only**, with gentle intervals.

## Limits / open

- Live values are tested on the **MC3.0**; the MC0.5 path is derived from the
  data format but not yet verified on a device.
- Actual temperature, lid, weight and error code on the MC3.0: **not available
  via the cloud** (checked on the real device, see above) – only locally on the
  device.
- Checking off the shopping list and creating planner entries: prepared, not yet
  active.
