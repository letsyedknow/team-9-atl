import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import mapData from "../mocks/mapData.fixture.json";
import ShelterDetails from "../../src/components/summary/ShelterDetails";
import { StoreProvider } from "../../src/state/store";
import type { LiveCheckStatus, MapData } from "../../src/lib/types";

const data = mapData as unknown as MapData;

const renderWith = (status: LiveCheckStatus) =>
  render(
    <StoreProvider
      initial={{
        mapData: { status: "ready", data },
        selectedShelterId: "M1",
        liveChecks: new Map([["M1", { status, placeIds: ["p1"], checked_at: "2026-10-27T16:00:00Z" }]]),
      }}
    >
      <ShelterDetails />
    </StoreProvider>,
  );

describe("ShelterDetails live-check discrepancy (T077, T078)", () => {
  it("shows a renamed shelter as a discrepancy, registry record unedited", () => {
    renderWith("renamed");
    const line = screen.getByTestId("live-check");
    expect(line).toHaveTextContent("Live check: renamed per Google Maps");
    expect(line).toHaveTextContent("registry record shown unedited");
    expect(screen.getByText("Google Maps")).toHaveAttribute("translate", "no");
    expect(screen.getByText("Macon Centreplex")).toBeInTheDocument();
  });

  it("shows a confirmed shelter without a discrepancy", () => {
    renderWith("exists");
    expect(screen.getByTestId("live-check")).toHaveTextContent("Still there per Google Maps");
    expect(screen.getByTestId("live-check")).not.toHaveTextContent("unedited");
  });
});
