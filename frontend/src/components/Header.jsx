import { AudioLines } from "lucide-react";

function Header({ status }) {
  const isError = status === "error";

  return (
    <header className="header">
      <div className="brand">
        <div className="brand-icon">
          <AudioLines size={25} />
        </div>

        <div className="brand-text">
          <h2>PERSONAL AI ASSISTANT</h2>
        </div>
      </div>

      <div className="system-status">
        <span className={`status-dot ${isError ? "error-dot" : ""}`}></span>
        <span>{isError ? "Connection Error" : "System Ready"}</span>
      </div>
    </header>
  );
}

export default Header;