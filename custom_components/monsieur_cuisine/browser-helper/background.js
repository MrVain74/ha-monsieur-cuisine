// Monsieur Cuisine – HA Login-Helfer
//
// Fängt die eine Weiterleitung nach dem Lidl-Login ab, die der Browser nicht
// öffnen kann (die App-Adresse "lidl-com.monsieur-cuisine.Companion://login/prod?code=…"),
// liest daraus den Anmelde-Code und schickt ihn an die Empfangs-Adresse von
// Home Assistant. Die HA-Adresse steckt im "state" der Weiterleitung – das
// Add-on braucht daher KEINE eigene Konfiguration.
//
// Es wird ausschließlich auf Weiterleitungen von accounts.lidl.com reagiert.
// Es werden keine Zugangsdaten gelesen oder gespeichert – nur der kurzlebige
// Einmal-Code weitergereicht.

const REDIRECT_PREFIX = "lidl-com.monsieur-cuisine.Companion://login/prod";

function b64urlDecode(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  return atob(s);
}

function onRedirect(details) {
  const url = details.redirectUrl || "";
  if (!url.startsWith(REDIRECT_PREFIX)) return;

  const qi = url.indexOf("?");
  if (qi < 0) return;
  const params = new URLSearchParams(url.slice(qi + 1));
  const code = params.get("code");
  const state = params.get("state");
  if (!code || !state) return;

  let cb;
  try {
    cb = JSON.parse(b64urlDecode(state)).cb;
  } catch (e) {
    return;
  }
  // Sicherheit: nur an eine normale http(s)-Adresse weiterleiten.
  if (!cb || !/^https?:\/\//i.test(cb)) return;

  const target =
    cb +
    (cb.includes("?") ? "&" : "?") +
    "code=" + encodeURIComponent(code) +
    "&state=" + encodeURIComponent(state);

  if (typeof details.tabId === "number" && details.tabId >= 0) {
    chrome.tabs.update(details.tabId, { url: target });
  } else {
    chrome.tabs.create({ url: target });
  }
}

chrome.webRequest.onBeforeRedirect.addListener(onRedirect, {
  urls: ["https://accounts.lidl.com/*"],
});
