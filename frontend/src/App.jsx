import { useState } from "react";
import "./App.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const RISK_LABELS = {
  low: "Low asthma risk",
  moderate: "Moderate asthma risk",
  high: "High asthma risk",
  very_high: "Very high asthma risk",
  severe: "Severe asthma risk",
};

function App() {
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const checkRisk = () => {
    if (!navigator.geolocation) {
      setStatus("error");
      setError("Geolocation is not supported by this browser.");
      return;
    }

    setStatus("loading");
    setError(null);

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;
        try {
          const response = await fetch(
            `${API_BASE_URL}/api/aqi-risk?lat=${latitude}&lon=${longitude}`
          );
          if (!response.ok) {
            const body = await response.json().catch(() => null);
            throw new Error(body?.detail || `Request failed with status ${response.status}`);
          }
          const data = await response.json();
          setResult(data);
          setStatus("done");
        } catch (err) {
          setError(err.message);
          setStatus("error");
        }
      },
      (geoError) => {
        setError(geoError.message);
        setStatus("error");
      }
    );
  };

  return (
    <div className="app">
      <h1>AirIntel</h1>
      <p className="subtitle">Check your asthma risk based on local air quality</p>

      <button onClick={checkRisk} disabled={status === "loading"}>
        {status === "loading" ? "Checking..." : "Check my location"}
      </button>

      {status === "error" && <p className="error">{error}</p>}

      {status === "done" && result && (
        <div className={`result risk-${result.risk_level}`}>
          <div className="risk-badge">{RISK_LABELS[result.risk_level] ?? result.risk_level}</div>
          <div className="aqi-value">AQI {result.aqi}</div>
          <div className="category">{result.category_name}</div>
          <p className="message">{result.message}</p>
          {result.dominant_pollutant && (
            <p className="pollutant">Main pollutant: {result.dominant_pollutant}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
