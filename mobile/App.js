import { useState } from "react";
import { StatusBar } from "expo-status-bar";
import Constants from "expo-constants";
import * as Location from "expo-location";
import * as Notifications from "expo-notifications";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000";

const RISK_COLORS = {
  low: { background: "#ecfdf5", border: "#34d399" },
  moderate: { background: "#fefce8", border: "#facc15" },
  high: { background: "#fff7ed", border: "#fb923c" },
  very_high: { background: "#fff7ed", border: "#fb923c" },
  severe: { background: "#fef2f2", border: "#f87171" },
};

export default function App() {
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [pushToken, setPushToken] = useState(null);
  const [alertsBusy, setAlertsBusy] = useState(false);
  const [alertsError, setAlertsError] = useState(null);

  const checkRisk = async () => {
    setStatus("loading");
    setError(null);

    const { status: permissionStatus } = await Location.requestForegroundPermissionsAsync();
    if (permissionStatus !== "granted") {
      setError("Permission to access location was denied.");
      setStatus("error");
      return;
    }

    try {
      const position = await Location.getCurrentPositionAsync({});
      const { latitude, longitude } = position.coords;

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
  };

  const toggleAlerts = async (enabled) => {
    setAlertsError(null);
    setAlertsBusy(true);
    try {
      if (enabled) {
        const { status: permissionStatus } = await Notifications.requestPermissionsAsync();
        if (permissionStatus !== "granted") {
          throw new Error("Permission to send notifications was denied.");
        }

        if (Platform.OS === "android") {
          await Notifications.setNotificationChannelAsync("default", {
            name: "Default",
            importance: Notifications.AndroidImportance.MAX,
          });
        }

        const projectId = Constants.expoConfig?.extra?.eas?.projectId;
        const { data: token } = await Notifications.getExpoPushTokenAsync(
          projectId ? { projectId } : undefined
        );

        const response = await fetch(`${API_BASE_URL}/api/alerts/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ push_token: token, lat: result.lat, lon: result.lon }),
        });
        if (!response.ok) throw new Error("Could not enable alerts");

        setPushToken(token);
      } else if (pushToken) {
        await fetch(`${API_BASE_URL}/api/alerts/unregister`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ push_token: pushToken }),
        });
        setPushToken(null);
      }
    } catch (err) {
      setAlertsError(err.message);
    } finally {
      setAlertsBusy(false);
    }
  };

  const riskColors = result ? RISK_COLORS[result.risk_level] : null;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>AirIntel</Text>
      <Text style={styles.subtitle}>Check your asthma risk based on local air quality</Text>

      <Pressable
        style={[styles.button, status === "loading" && styles.buttonDisabled]}
        onPress={checkRisk}
        disabled={status === "loading"}
      >
        {status === "loading" ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Check my location</Text>
        )}
      </Pressable>

      {status === "error" && <Text style={styles.error}>{error}</Text>}

      {status === "done" && result && (
        <View
          style={[
            styles.result,
            { backgroundColor: riskColors.background, borderColor: riskColors.border },
          ]}
        >
          <Text style={styles.aqiValue}>AQI {result.aqi}</Text>
          <Text style={styles.category}>{result.category_name}</Text>
          <Text style={styles.message}>{result.message}</Text>
        </View>
      )}

      {status === "done" && result && (
        <View style={styles.alertsRow}>
          <Text style={styles.alertsLabel}>Alert me about this location</Text>
          {alertsBusy ? (
            <ActivityIndicator />
          ) : (
            <Switch value={!!pushToken} onValueChange={toggleAlerts} />
          )}
        </View>
      )}

      {alertsError && <Text style={styles.error}>{alertsError}</Text>}

      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
  },
  subtitle: {
    color: "#666",
    marginTop: 8,
    marginBottom: 24,
    textAlign: "center",
  },
  button: {
    backgroundColor: "#2563eb",
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
  },
  buttonDisabled: {
    backgroundColor: "#94a3b8",
  },
  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  error: {
    color: "#b91c1c",
    marginTop: 24,
    textAlign: "center",
  },
  result: {
    marginTop: 32,
    padding: 20,
    borderRadius: 12,
    borderWidth: 1,
    width: "100%",
    alignItems: "center",
  },
  aqiValue: {
    fontSize: 36,
    fontWeight: "700",
  },
  category: {
    fontWeight: "600",
    marginTop: 4,
    marginBottom: 10,
  },
  message: {
    color: "#444",
    textAlign: "center",
  },
  alertsRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    width: "100%",
    marginTop: 20,
  },
  alertsLabel: {
    fontSize: 15,
    color: "#333",
  },
});
