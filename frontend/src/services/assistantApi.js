
const API_URL = "http://127.0.0.1:5000";

export async function interruptVoiceCommand() {
  try {
    await fetch(`${API_URL}/api/interrupt`, {
      method: "POST"
    });
  } catch (error) {
    console.error("Interrupt request failed:", error);
  }
}

export async function startVoiceCommand(signal, onStatusChange) {
  let polling = true;

  const pollStatus = async () => {
    while (polling && !signal.aborted) {
      try {
        const result = await fetch(`${API_URL}/api/status`, {
          signal
        });

        const data = await result.json();

        if (polling && !signal.aborted) {
          onStatusChange(data.status);
        }
      } catch (error) {
        if (error.name !== "AbortError") {
          console.error("Status check failed:", error);
        }
        break;
      }

      await new Promise(resolve => setTimeout(resolve, 300));
    }
  };

  const pollingPromise = pollStatus();

  try {
    const result = await fetch(`${API_URL}/api/voice-command`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      signal
    });

    const data = await result.json();

    if (!result.ok) {
      throw new Error(data.error || "Assistant request failed");
    }

    return data;

  } finally {
    polling = false;
    await pollingPromise;
  }
}
