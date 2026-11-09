
import { Mic, MicOff, LoaderCircle } from "lucide-react";

function VoiceAssistant({ status, onStart, onStop }) {
  const isListening = status === "listening";
  const isProcessing = status === "processing";

  const getMessage = () => {
    if (isListening) return "Listening... Speak now";
    if (isProcessing) return "Processing your command...";
    if (status === "response") return "Response received";
    if (status === "error") return "Something went wrong. Try again.";

    return "Click the microphone and speak your command";
  };

  return (
    <section className="voice-section">

      <h1>
        Voice-Based 
        <span> Personal Assistant</span>
      </h1>

      <div className={`mic-wrapper ${isListening ? "listening" : ""}`}>

        {isListening && (
          <>
            <div className="pulse pulse-one"></div>
            <div className="pulse pulse-two"></div>
          </>
        )}

        <button
          className={`mic-button ${isListening ? "mic-active" : ""}`}
          onClick={isListening ? onStop : onStart}
          disabled={isProcessing}
          aria-label={isListening ? "Stop listening" : "Start listening"}
        >
          {isListening ? (
            <MicOff size={42} />
          ) : (
            <Mic size={42} />
          )}
        </button>

      </div>

      <h2 className="mic-heading">
        {isListening
          ? "Listening..."
          : isProcessing
          ? "Processing..."
          : status === "response"
          ? "Assistant Responded"
          : "Click to Speak"}
      </h2>

      <p className="mic-description">
        {getMessage()}
      </p>

      {isListening && (
        <div className="wave-container">
          {Array.from({ length: 17 }).map((_, index) => (
            <span
              key={index}
              className="wave-bar"
              style={{ animationDelay: `${index * 0.08}s` }}
            />
          ))}
        </div>
      )}

      {isProcessing && (
        <div className="processing-indicator">
          <LoaderCircle size={25} className="processing-spinner" />
          <span>Please wait while I prepare your response...</span>
        </div>
      )}

    </section>
  );
}

export default VoiceAssistant;
