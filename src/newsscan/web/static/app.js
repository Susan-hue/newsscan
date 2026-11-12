// Everything from the server is untrusted (the recognised text came from a stranger's paper).
// Only textContent is used to display it, never innerHTML.
(function () {
  "use strict";

  var BANDS = {
    insufficient_evidence: "Not enough evidence for a verdict",
    reliable_signals: "Reliable signals",
    related_fact_checks: "Related fact-checks found",
    mixed: "Mixed signals",
    weak_signals: "Weak signals"
  };

  var form = document.getElementById("scan-form");
  var fileInput = document.getElementById("file");
  var submitButton = document.getElementById("submit");
  var statusEl = document.getElementById("status");
  var resultEl = document.getElementById("result");

  var stepsEl = document.getElementById("steps");
  var fileNameEl = document.getElementById("file-name");
  var DEFAULT_FILE_LABEL = fileNameEl.textContent;

  // 1 = upload, 2 = reading the text, 3 = report ready. Only a visual hint for the progress row.
  function setStep(n) {
    stepsEl.setAttribute("data-step", String(n));
  }

  fileInput.addEventListener("change", function () {
    // textContent only: a file name is user input too.
    fileNameEl.textContent = fileInput.files.length ? fileInput.files[0].name : DEFAULT_FILE_LABEL;
  });

  function setStatus(message, isError) {
    statusEl.textContent = message;
    statusEl.className = isError ? "error" : "";
  }

  function cell(row, value) {
    var td = document.createElement("td");
    td.textContent = value;
    row.appendChild(td);
  }

  function line(parent, label, value) {
    var p = document.createElement("p");
    var strong = document.createElement("strong");
    strong.textContent = label + " ";
    p.appendChild(strong);
    p.appendChild(document.createTextNode(value));
    parent.appendChild(p);
  }

  // Fact-check matches come from outside, so: textContent only, and a link only for http(s) URLs.
  function renderFactChecks(report) {
    var box = document.getElementById("factchecks");
    var list = document.getElementById("factcheck-list");
    list.replaceChildren();
    var signal = report.signals.find(function (s) { return s.name === "claim_checks"; });
    var items = (signal && signal.items) || [];
    items.forEach(function (item) {
      var li = document.createElement("li");
      line(li, "Rated by " + (item.publisher || "a fact-checker") + ":", item.rating);
      line(li, "Claim on your page:", item.claim);
      if (item.matched_claim) line(li, "Claim the fact-checker recorded:", item.matched_claim);
      if (/^https?:\/\//i.test(item.url)) {
        var a = document.createElement("a");
        a.href = item.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = item.title || "Read the fact-check";
        li.appendChild(a);
      }
      list.appendChild(li);
    });
    box.hidden = items.length === 0;
  }

  function render(scan) {
    var report = scan.report;
    var doc = scan.document;
    document.getElementById("band").textContent = BANDS[report.band] || report.band;
    document.getElementById("summary").textContent = report.summary;

    var tbody = document.getElementById("signals");
    tbody.replaceChildren();
    report.signals.forEach(function (signal) {
      var row = document.createElement("tr");
      cell(row, signal.name);
      cell(row, signal.kind);
      cell(row, signal.status === "ok" && signal.value !== null ? String(signal.value) : "not run");
      cell(row, signal.detail);
      tbody.appendChild(row);
    });

    renderFactChecks(report);

    var list = document.getElementById("limitations");
    list.replaceChildren();
    report.limitations.forEach(function (item) {
      var li = document.createElement("li");
      li.textContent = item;
      list.appendChild(li);
    });

    document.getElementById("text").textContent = doc.text || "(no text recognised)";
    resultEl.hidden = false;
  }

  function wait(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  async function poll(id) {
    var deadline = Date.now() + 5 * 60 * 1000;
    while (Date.now() < deadline) {
      var response = await fetch("/v1/scans/" + encodeURIComponent(id));
      if (!response.ok) throw new Error("Could not read the scan status.");
      var scan = await response.json();
      if (scan.status === "done") return scan;
      if (scan.status === "failed") throw new Error(scan.error || "The scan failed.");
      setStep(2);
      setStatus("Reading the paper (" + scan.status + ")...");
      await wait(1500);
    }
    throw new Error("This is taking too long. Check back later.");
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (!fileInput.files.length) return;
    resultEl.hidden = true;
    submitButton.disabled = true;
    setStep(1);
    setStatus("Uploading...");
    try {
      var body = new FormData();
      body.append("file", fileInput.files[0]);
      var response = await fetch("/v1/scans", { method: "POST", body: body });
      var payload = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(payload.detail || "The upload was rejected.");
      var scan = await poll(payload.id);
      setStep(3);
      setStatus("Done.");
      render(scan);
      resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      submitButton.disabled = false;
    }
  });
})();
