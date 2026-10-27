import { afterEach, describe, expect, it, vi } from "vitest";
import { parseSseChunk, streamChat, type AgentEvent } from "../../src/lib/agentClient";

const ERROR_EVENT = { error: "ValueError: boom", error_details: { error_type: "ValueError", error_message: "boom" } };

function sseResponse(events: unknown[]): Response {
  const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body));
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("parseSseChunk", () => {
  it("parses ADK's mid-stream error event", () => {
    const { events, rest } = parseSseChunk(`data: ${JSON.stringify(ERROR_EVENT)}\n\n`);
    expect(rest).toBe("");
    expect(events[0].error).toBe("ValueError: boom");
  });
});

describe("streamChat", () => {
  it("rejects when the stream ends with an error event (FR-015)", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes("/sessions")
        ? new Response(JSON.stringify({ id: "s1" }), { status: 200 })
        : sseResponse([{ author: "readiness_agent", partial: true, content: { parts: [{ text: "Partial" }] } }, ERROR_EVENT]),
    );
    vi.stubGlobal("fetch", fetchMock);
    const seen: AgentEvent[] = [];
    await expect(
      streamChat({
        question: "q",
        context: { county_fips: null, shelter_id: null, scenario: null },
        onEvent: (e) => seen.push(e),
      }),
    ).rejects.toThrow("ValueError: boom");
    expect(seen).toHaveLength(1);
  });
});
