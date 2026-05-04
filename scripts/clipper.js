/**
 * 🔌 Job Copilot Clipper
 * Bookmarklet script to send job data to the backend.
 * 
 * Usage: Create a new bookmark and paste the following into the URL field:
 * javascript:(function(){const s=document.createElement('script');s.src='http://localhost:8000/static/clipper.js';document.body.appendChild(s);})();
 * (Note: The above requires the API to serve this file, but we'll provide a self-contained version).
 */

(function() {
    console.log("🚀 Job Copilot Clipper activated!");

    function extractLinkedIn() {
        const title = document.querySelector(".job-details-jobs-unified-top-card__job-title, .jobs-details-top-card__job-title")?.innerText.trim();
        const company = document.querySelector(".job-details-jobs-unified-top-card__company-name, .jobs-details-top-card__company-url")?.innerText.trim();
        const location = document.querySelector(".job-details-jobs-unified-top-card__bullet, .jobs-details-top-card__bullet")?.innerText.trim();
        const description = document.querySelector(".jobs-description-content__text, .jobs-box__html-content")?.innerText.trim();
        const url = window.location.href;

        return { title, company, location, description, url, source: "LinkedIn" };
    }

    function extractFranceTravail() {
        const title = document.querySelector("h1[itemprop='title']")?.innerText.trim();
        const company = document.querySelector("h2[itemprop='name']")?.innerText.trim();
        const location = document.querySelector("span[itemprop='addressLocality']")?.innerText.trim();
        const description = document.querySelector(".description")?.innerText.trim();
        const url = window.location.href;

        return { title, company, location, description, url, source: "France Travail" };
    }

    let jobData = null;
    if (window.location.host.includes("linkedin.com")) {
        jobData = extractLinkedIn();
    } else if (window.location.host.includes("francetravail.fr") || window.location.host.includes("pole-emploi.fr")) {
        jobData = extractFranceTravail();
    } else {
        // Fallback for other sites - try generic selectors
        jobData = {
            title: document.title,
            company: "Manual Extract",
            location: "Unknown",
            description: document.body.innerText.substring(0, 5000),
            url: window.location.href,
            source: "Generic Clipper"
        };
    }

    if (!jobData || !jobData.title) {
        alert("❌ Could not extract job data. Make sure you are on a job details page.");
        return;
    }

    console.log("📦 Data extracted:", jobData);

    // Send to backend
    fetch("http://localhost:8000/clip", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(jobData),
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            const statusEmoji = data.is_new ? "✅" : "♻️";
            alert(`${statusEmoji} Job Copilot: "${jobData.title}" ${data.is_new ? "clipped!" : "already exists (updated)."}`);
        } else {
            alert("❌ Error clipping job: " + (data.detail || "Unknown error"));
        }
    })
    .catch(error => {
        console.error("Error:", error);
        alert("❌ Could not connect to Job Copilot Backend. Is 'infra/api.py' running on port 8000?");
    });
})();
