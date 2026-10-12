// Monsieur Cuisine – HA Login-Helfer
//
// Fängt nach dem Lidl-Login die Weiterleitung auf die App-Adresse ab
// ("lidl-com.monsieur-cuisine.Companion://login/prod?code=…") und übergibt den
// Anmelde-Code an die Empfangs-Adresse von Home Assistant (steckt im "state").
//
// Zuverlässiger Weg: Wir lesen den `Location`-Header der 302-Antwort von
// accounts.lidl.com (onHeadersReceived). Das feuert immer – auch wenn der
// Browser die App-Adresse danach nicht öffnen kann. onBeforeRedirect bleibt
// als zusätzliche Absicherung.
//
// Nur Weiterleitungen von accounts.lidl.com werden gelesen. Keine Zugangsdaten.

const SCHEME_PREFIX = "lidl-com.monsieur-cuisine.Companion://login/prod";

function b64urlDecode(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  return atob(s);
}

function deliver(schemeUrl, tabId, via) {
  const qi = schemeUrl.indexOf("?");
  if (qi < 0) return false;
  const p = new URLSearchParams(schemeUrl.slice(qi + 1));
  const code = p.get("code");
  const state = p.get("state");
  if (!code || !state) {
    console.log("[MC] Weiterleitung ohne code/state:", schemeUrl.slice(0, 60));
    return false;
  }
  let cb;
  try {
    cb = JSON.parse(b64urlDecode(state)).cb;
  } catch (e) {
    console.log("[MC] state nicht lesbar:", e);
    return false;
  }
  if (!cb || !/^https?:\/\//i.test(cb)) {
    console.log("[MC] keine gültige HA-Adresse im state:", cb);
    return false;
  }
  const target =
    cb + (cb.includes("?") ? "&" : "?") +
    "code=" + encodeURIComponent(code) +
    "&state=" + encodeURIComponent(state);
  console.log("[MC] Code abgefangen (" + via + ") → sende an HA:", cb, "Tab", tabId);
  if (typeof tabId === "number" && tabId >= 0) {
    chrome.tabs.update(tabId, { url: target });
  } else {
    chrome.tabs.create({ url: target });
  }
  return true;
}

// Zuverlässig: Location-Header der 302-Antwort lesen.
chrome.webRequest.onHeadersReceived.addListener(
  (d) => {
    const loc = (d.responseHeaders || []).find(
      (h) => h.name.toLowerCase() === "location"
    );
    if (loc && loc.value && loc.value.indexOf(SCHEME_PREFIX) === 0) {
      deliver(loc.value, d.tabId, "headers");
    }
  },
  { urls: ["https://accounts.lidl.com/*"] },
  ["responseHeaders"]
);

// Absicherung: falls Chrome die Weiterleitung doch als Redirect meldet.
chrome.webRequest.onBeforeRedirect.addListener(
  (d) => {
    if (d.redirectUrl && d.redirectUrl.indexOf(SCHEME_PREFIX) === 0) {
      deliver(d.redirectUrl, d.tabId, "redirect");
    }
  },
  { urls: ["https://accounts.lidl.com/*"] }
);

console.log("[MC] Login-Helfer bereit (v0.2.0)");
