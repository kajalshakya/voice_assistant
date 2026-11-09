import { MessageSquare, Volume2 } from "lucide-react";

function ResponseBox({ transcript, response }) {
  return (
    <section className="response-box">
      <div className="response-title">
        <MessageSquare size={20} />
        <h3>Assistant Response</h3>
      </div>

      <div className="response-content">
        <p className="content-label">YOUR COMMAND</p>

        <p className="content-text">
          {transcript || "Your voice command will appear here..."}
        </p>
      </div>

      <div className="response-divider"></div>

      <div className="response-content">
        <div className="voice-response-label">
          <Volume2 size={18} />
          <p className="content-label">VOICE RESPONSE</p>
        </div>

        <p className="content-text">
          {response || "Your assistant's response will appear here..."}
        </p>
      </div>
    </section>
  );
}

export default ResponseBox;