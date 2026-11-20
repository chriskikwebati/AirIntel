import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const RESULT = {
  lat: 38.9,
  lon: -77.0,
  aqi: 162,
  category_name: "Unhealthy",
  category_number: 4,
  dominant_pollutant: "PM2.5",
  risk_level: "high",
  message: "Air quality is unhealthy. People with asthma should avoid prolonged outdoor exertion.",
};

function mockLocation({ coords = { latitude: 38.9, longitude: -77.0 }, error } = {}) {
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: (onSuccess, onError) => (error ? onError(error) : onSuccess({ coords })),
    },
  });
}

function mockFetch(status, body) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => (body === undefined ? Promise.reject(new Error("no body")) : Promise.resolve(body)),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function clickCheck() {
  fireEvent.click(screen.getByRole("button", { name: "Check my location" }));
}

describe("App", () => {
  beforeEach(() => mockLocation());

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the check button before anything happens", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "AirIntel" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Check my location" })).toBeTruthy();
  });

  it("asks the backend about the user's location and shows the result", async () => {
    const fetchMock = mockFetch(200, RESULT);
    render(<App />);
    clickCheck();

    expect(await screen.findByText("High asthma risk")).toBeTruthy();
    expect(screen.getByText("AQI 162")).toBeTruthy();
    expect(screen.getByText("Unhealthy")).toBeTruthy();
    expect(screen.getByText("Main pollutant: PM2.5")).toBeTruthy();
    expect(screen.getByText(RESULT.message)).toBeTruthy();

    const url = fetchMock.mock.calls[0][0];
    expect(url).toContain("/api/aqi-risk?lat=38.9&lon=-77");
  });

  it("colours the result card by risk level", async () => {
    mockFetch(200, { ...RESULT, risk_level: "severe" });
    const { container } = render(<App />);
    clickCheck();
    await screen.findByText("Severe asthma risk");
    expect(container.querySelector(".result").className).toContain("risk-severe");
  });

  it("shows the backend's error message when the request fails", async () => {
    mockFetch(502, { detail: "Air quality data is temporarily unavailable" });
    render(<App />);
    clickCheck();
    expect(await screen.findByText("Air quality data is temporarily unavailable")).toBeTruthy();
  });

  it("falls back to the status code when the error has no body", async () => {
    mockFetch(500);
    render(<App />);
    clickCheck();
    expect(await screen.findByText("Request failed with status 500")).toBeTruthy();
  });

  it("shows a message when the user blocks location access", async () => {
    mockLocation({ error: { message: "User denied Geolocation" } });
    const fetchMock = mockFetch(200, RESULT);
    render(<App />);
    clickCheck();
    expect(await screen.findByText("User denied Geolocation")).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("explains when the browser has no location support", async () => {
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: undefined });
    render(<App />);
    clickCheck();
    expect(await screen.findByText("Geolocation is not supported by this browser.")).toBeTruthy();
  });
});
