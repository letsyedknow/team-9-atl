// Folding one streamed ADK event into the answer being built (tasks T070, T076).
import type { AgentEvent } from "./agentClient";
import { collectLiveChecks, collectReferences } from "./grounding";
import type { GroundingMetadata, LiveCheckReport } from "./types";

export interface Fold {
  text: string;
  grounding?: GroundingMetadata;
  shelterIds: string[];
  countyFips: string[];
  liveChecks: LiveCheckReport[];
}

export const emptyFold: Fold = { text: "", shelterIds: [], countyFips: [], liveChecks: [] };

const union = (a: string[], b: string[]) => (b.length ? [...new Set([...a, ...b])] : a);

export function foldEvent(acc: Fold, e: AgentEvent): Fold {
  let { text, grounding, shelterIds, countyFips, liveChecks } = acc;
  for (const part of e.content?.parts ?? []) {
    if (part.functionResponse) {
      const refs = collectReferences(part.functionResponse.response);
      shelterIds = union(shelterIds, refs.shelterIds);
      countyFips = union(countyFips, refs.countyFips);
      const checks = collectLiveChecks(part.functionResponse.response);
      if (checks.length) liveChecks = [...liveChecks, ...checks];
    }
  }
  const chunk = (e.content?.parts ?? []).map((p) => p.text ?? "").join("");
  if (chunk && e.author !== "user") {
    // Partial events carry deltas; a non-partial event carries the whole text so far.
    text = e.partial ? text + chunk : chunk;
  }
  if (e.groundingMetadata) grounding = e.groundingMetadata;
  return { text, grounding, shelterIds, countyFips, liveChecks };
}
