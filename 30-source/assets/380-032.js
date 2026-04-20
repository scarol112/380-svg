const REFRESH_MS = 6000;

function loadSvg() {
  const path = document.getElementById("svg-path").value.trim();
  const img = document.getElementById("svg-img");
  // Cache-bust so the browser fetches the latest version
  img.src = path + "?t=" + Date.now();
  document.getElementById("status").textContent =
    "Last refreshed: " + new Date().toLocaleTimeString();
}

loadSvg();
setInterval(loadSvg, REFRESH_MS);
