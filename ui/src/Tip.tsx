import type { ReactNode } from "react";

/** Hover or focus to read `tip`. Keyboard-reachable, so it works without a mouse too. */
export default function Tip({ tip, children }: { tip: string; children: ReactNode }) {
  return (
    <span className="tip" tabIndex={0} aria-label={tip}>
      {children}
      <span className="tip-bubble" role="tooltip">
        {tip}
      </span>
    </span>
  );
}

export const TIPS = {
  match: "Average of fit and appeal (0–4).",
  fit: "Would they hire you? Your resume vs. their requirements.",
  appeal: "Would you want it? Role, pay and remote vs. your preferences.",
  pay: "Approx. USD per month, for comparing.",
};
