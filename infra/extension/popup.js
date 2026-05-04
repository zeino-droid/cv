document.getElementById('clipBtn').addEventListener('click', async () => {
  const status = document.getElementById('status');
  const loader = document.getElementById('loader');
  const btn = document.getElementById('clipBtn');

  status.innerText = "";
  loader.style.display = "block";
  btn.disabled = true;

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    // Inject and execute extraction script
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractJobData,
    });

    if (results && results[0] && results[0].result) {
      const jobData = results[0].result;
      
      // Send to backend
      const response = await fetch("http://localhost:8000/clip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(jobData),
      });

      const data = await response.json();
      if (data.status === "success") {
        status.innerText = "✅ " + (data.is_new ? "Clipped!" : "Updated!");
        status.style.color = "#10b981";
      } else {
        status.innerText = "❌ Error: " + (data.detail || "Server error");
        status.style.color = "#ef4444";
      }
    } else {
      status.innerText = "❌ Could not find job data.";
      status.style.color = "#ef4444";
    }
  } catch (error) {
    status.innerText = "❌ Backend unreachable (is it running?)";
    status.style.color = "#ef4444";
    console.error(error);
  } finally {
    loader.style.display = "none";
    btn.disabled = false;
  }
});

function extractJobData() {
  function getLinkedIn() {
    return {
      title: document.querySelector(".job-details-jobs-unified-top-card__job-title, .jobs-details-top-card__job-title")?.innerText.trim(),
      company: document.querySelector(".job-details-jobs-unified-top-card__company-name, .jobs-details-top-card__company-url")?.innerText.trim(),
      location: document.querySelector(".job-details-jobs-unified-top-card__bullet, .jobs-details-top-card__bullet")?.innerText.trim(),
      description: document.querySelector(".jobs-description-content__text, .jobs-box__html-content")?.innerText.trim(),
      url: window.location.href,
      source: "LinkedIn"
    };
  }

  function getFranceTravail() {
    return {
      title: document.querySelector("h1[itemprop='title']")?.innerText.trim(),
      company: document.querySelector("h2[itemprop='name']")?.innerText.trim(),
      location: document.querySelector("span[itemprop='addressLocality']")?.innerText.trim(),
      description: document.querySelector(".description")?.innerText.trim(),
      url: window.location.href,
      source: "France Travail"
    };
  }

  if (window.location.host.includes("linkedin.com")) return getLinkedIn();
  if (window.location.host.includes("francetravail.fr") || window.location.host.includes("pole-emploi.fr")) return getFranceTravail();
  
  return {
    title: document.title,
    company: "Generic",
    description: document.body.innerText.substring(0, 3000),
    url: window.location.href,
    source: "Generic"
  };
}
