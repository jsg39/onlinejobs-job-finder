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
  match: "Match is the average of Fit and Appeal, from 0 to 4. Jobs are sorted by it.",
  fit: "Fit: how well your resume meets this job's requirements. Would they hire you? 4 = meets the core requirements with your strongest experience; 0 = wrong field.",
  appeal:
    "Appeal: how well the job matches what you want: backend or AI work, fully remote, at or above your pay floor. Would you want it? 4 = exactly the work you do best on good terms; 0 = conflicts with your preferences.",
  pay: "Approximate USD per month, converted from the posted pay so jobs can be compared and filtered. Hourly pay uses the posted hours per week.",
};
