/**
 * AI Drone Emergency Response System — Shared JavaScript Module
 * ==============================================================
 * WebSocket connection, API helpers, and shared utilities.
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const API_BASE_URL = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" || window.location.protocol === "file:")
    ? "http://localhost:10000"
    : "https://your-render-backend.onrender.com";  // ← Update with your Render URL

const WS_BASE_URL = API_BASE_URL.replace("http", "ws");

// ---------------------------------------------------------------------------
// API Helpers
// ---------------------------------------------------------------------------

async function apiFetch(endpoint, options = {}) {
    try {
        const resp = await fetch(`${API_BASE_URL}${endpoint}`, options);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error(`API Error [${endpoint}]:`, err);
        throw err;
    }
}

async function getIncidents() {
    return apiFetch("/incidents");
}

async function getIncident(incidentId) {
    return apiFetch(`/incidents/${incidentId}`);
}

async function getDrones() {
    return apiFetch("/drones");
}

async function uploadDroneImage(incidentId, file) {
    const formData = new FormData();
    formData.append("image", file);
    return apiFetch(`/upload-image/${incidentId}`, {
        method: "POST",
        body: formData,
    });
}

// ---------------------------------------------------------------------------
// WebSocket Manager
// ---------------------------------------------------------------------------

class DroneWebSocket {
    constructor(onMessage) {
        this.url = `${WS_BASE_URL}/ws`;
        this.onMessage = onMessage;
        this.ws = null;
        this.reconnectDelay = 2000;
        this.maxReconnectDelay = 30000;
        this.connect();
    }

    connect() {
        console.log("🔌 Connecting WebSocket...", this.url);
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
            console.log("✅ WebSocket connected");
            this.reconnectDelay = 2000;
            // Start ping interval
            this.pingInterval = setInterval(() => {
                if (this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send("ping");
                }
            }, 15000);
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type !== "pong") {
                    this.onMessage(data);
                }
            } catch (err) {
                console.warn("WS parse error:", err);
            }
        };

        this.ws.onclose = () => {
            console.log("❌ WebSocket disconnected, reconnecting...");
            clearInterval(this.pingInterval);
            setTimeout(() => this.connect(), this.reconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay);
        };

        this.ws.onerror = (err) => {
            console.error("WebSocket error:", err);
        };
    }

    close() {
        clearInterval(this.pingInterval);
        if (this.ws) this.ws.close();
    }
}

// ---------------------------------------------------------------------------
// Utility Functions
// ---------------------------------------------------------------------------

function formatTimestamp(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString();
}

function getPriorityColor(priority) {
    switch (priority?.toUpperCase()) {
        case "CRITICAL": return "#ff4444";
        case "HIGH": return "#ff8800";
        case "MEDIUM": return "#ffcc00";
        case "LOW": return "#44cc44";
        default: return "#888888";
    }
}

function getPriorityBadge(priority) {
    const color = getPriorityColor(priority);
    return `<span style="
        background: ${color}22;
        color: ${color};
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8em;
        font-weight: 600;
        border: 1px solid ${color}44;
    ">${priority || "N/A"}</span>`;
}

function showToast(message, type = "info") {
    const toast = document.createElement("div");
    const colors = {
        info: "#3498db",
        success: "#27ae60",
        warning: "#f39c12",
        error: "#e74c3c",
    };
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: ${colors[type] || colors.info};
        color: white;
        padding: 14px 24px;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 500;
        z-index: 10000;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        animation: slideIn 0.3s ease;
        max-width: 380px;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = "fadeOut 0.3s ease";
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// Add animation styles
const style = document.createElement("style");
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes fadeOut {
        from { opacity: 1; }
        to { opacity: 0; }
    }
`;
document.head.appendChild(style);
