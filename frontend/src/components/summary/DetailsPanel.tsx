import { useStore } from "../../state/store";
import { useScenario } from "../../state/scenario";
import CountySummary from "./CountySummary";
import ShelterDetails from "./ShelterDetails";
import CouldNotTell from "./CouldNotTell";
import AffectedSummary from "../scenario/AffectedSummary";
import ReceivingList from "../scenario/ReceivingList";

/**
 * County/shelter summaries, the hurricane lists and "What we could not tell you". Collapsed to a
 * rail by default; hovering, selecting or drawing never opens it (tasks T082–T083).
 */
export default function DetailsPanel() {
  const { state, dispatch } = useStore();
  const scenario = useScenario();
  const hasNews = Boolean(state.selectedShelterId || state.selectedFips || scenario);

  if (!state.detailsOpen) {
    return (
      <button
        type="button"
        className="details-rail"
        aria-expanded="false"
        aria-controls="details-panel"
        aria-label={hasNews ? "Show details (new details available)" : "Show details"}
        onClick={() => dispatch({ type: "setDetailsOpen", open: true })}
      >
        {hasNews && <span className="details-rail__dot" aria-hidden="true" />}
        Details ▸
      </button>
    );
  }

  return (
    <aside id="details-panel" className="side" aria-label="Details">
      <div className="side__header">
        <h2>Details</h2>
        <button
          type="button"
          className="btn"
          aria-expanded="true"
          aria-controls="details-panel"
          onClick={() => dispatch({ type: "setDetailsOpen", open: false })}
        >
          ◂ Hide
        </button>
      </div>
      {state.selectedShelterId ? <ShelterDetails /> : <CountySummary />}
      {scenario && (
        <>
          <AffectedSummary />
          <ReceivingList />
        </>
      )}
      <CouldNotTell />
    </aside>
  );
}
