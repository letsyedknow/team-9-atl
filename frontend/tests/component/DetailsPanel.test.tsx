import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import mapData from "../mocks/mapData.fixture.json";
import DetailsPanel from "../../src/components/summary/DetailsPanel";
import { StoreProvider, type State } from "../../src/state/store";
import { ScenarioProvider } from "../../src/state/scenario";
import type { MapData } from "../../src/lib/types";

const data = mapData as unknown as MapData;

const renderPanel = (initial: Partial<State> = {}) =>
  render(
    <StoreProvider initial={{ mapData: { status: "ready", data }, ...initial }}>
      <ScenarioProvider>
        <DetailsPanel />
      </ScenarioProvider>
    </StoreProvider>,
  );

describe("DetailsPanel (T082–T085)", () => {
  it("is collapsed by default", () => {
    renderPanel();
    expect(screen.getByRole("button", { name: "Show details" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByTestId("county-summary")).toBeNull();
    expect(screen.queryByTestId("could-not-tell")).toBeNull();
  });

  it("opens with one click and collapses again", async () => {
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole("button", { name: "Show details" }));
    expect(screen.getByTestId("could-not-tell")).toBeInTheDocument();
    expect(screen.getByText("Hover over or select a county to see what is on file.")).toBeInTheDocument();
    const hide = screen.getByRole("button", { name: "◂ Hide" });
    expect(hide).toHaveAttribute("aria-expanded", "true");
    await user.click(hide);
    expect(screen.queryByTestId("could-not-tell")).toBeNull();
    expect(screen.getByRole("button", { name: "Show details" })).toBeInTheDocument();
  });

  it("signals new details without opening when a county is selected", () => {
    renderPanel({ selectedFips: "13157" });
    const rail = screen.getByRole("button", { name: /Show details/ });
    expect(rail).toHaveAccessibleName("Show details (new details available)");
    expect(rail.querySelector(".details-rail__dot")).not.toBeNull();
    expect(screen.queryByTestId("county-summary")).toBeNull();
  });

  it("shows the selected county's summary once opened", async () => {
    const user = userEvent.setup();
    renderPanel({ selectedFips: "13157" });
    await user.click(screen.getByRole("button", { name: /Show details/ }));
    expect(screen.getByTestId("county-summary")).toHaveTextContent("Jackson County");
  });
});
