import { Mic, BrainCircuit, Volume2 } from "lucide-react";

const steps = [
  {
    id: "listening",
    label: "Listening",
    Icon: Mic
  },
  {
    id: "processing",
    label: "Processing",
    Icon: BrainCircuit
  },
  {
    id: "response",
    label: "Response",
    Icon: Volume2
  }
];

function StatusIndicator({ status }) {
  return (
    <div className="status-container">
      {steps.map(({ id, label, Icon }) => {
        const active = status === id;

        return (
          <div
            key={id}
            className={`status-card ${active ? "active" : ""}`}
          >
            <Icon size={25} />

            <span>{label}</span>

            {active && <div className="active-line"></div>}
          </div>
        );
      })}
    </div>
  );
}

export default StatusIndicator;