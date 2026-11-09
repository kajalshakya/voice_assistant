
import { useRef, useState } from "react";

import Header from "./components/Header";
import VoiceAssistant from "./components/VoiceAssistant";
import StatusIndicator from "./components/StatusIndicator";
import ResponseBox from "./components/ResponseBox";

import "./App.css";
import "./index.css";

import {
  startVoiceCommand,
  interruptVoiceCommand
} from "./services/assistantApi";

function App() {
  const [status, setStatus] = useState("ready");
  const [transcript, setTranscript] = useState("");
  const [response, setResponse] = useState("");

  const controllerRef = useRef(null);

  const handleStart = async () => {

    // If already listening, stop current listening.
    if (status === "listening") {
      handleStop();
      return;
    }

    // Cancel previous frontend request.
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }

    // Interrupt previous backend task and speech.
    if (
      status === "processing" ||
      status === "response" ||
      status === "error"
    ) {
      await interruptVoiceCommand();
    }

    const controller = new AbortController();

    controllerRef.current = controller;

    setTranscript("");
    setResponse("");
    setStatus("listening");

    try {
      const result = await startVoiceCommand(
        controller.signal,
        (newStatus) => {
          if (controllerRef.current === controller) {
            setStatus(newStatus);
          }
        }
      );

      if (
        controller.signal.aborted ||
        controllerRef.current !== controller
      ) {
        return;
      }

      setTranscript(result.transcript || "");
      setResponse(result.response || "");
      setStatus("response");

    } catch (error) {

      if (error.name === "AbortError") {
        return;
      }

      if (controllerRef.current === controller) {
        console.error(error);
        setStatus("error");
      }

    } finally {

      // An old request must not clear a newer controller.
      if (controllerRef.current === controller) {
        controllerRef.current = null;
      }
    }
  };

  const handleStop = () => {

    controllerRef.current?.abort();
    controllerRef.current = null;

    interruptVoiceCommand();

    setStatus("ready");
  };

  return (
    <div className="app">

      <Header status={status} />

      <main className="main-container">

        <VoiceAssistant
          status={status}
          onStart={handleStart}
          onStop={handleStop}
        />

        <section className="assistant-status-section">

          <h3 className="section-heading">
            ASSISTANT STATUS
          </h3>

          <StatusIndicator status={status} />

        </section>

        <ResponseBox
          transcript={transcript}
          response={response}
        />

        <footer className="footer">
          Personal Voice Assistant · Powered by Python
        </footer>

      </main>

    </div>
  );
}

export default App;
