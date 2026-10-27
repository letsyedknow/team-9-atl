# Contract: Frontend ↔ Agent Service

There is one origin, behind IAP. Paths are the standard ADK FastAPI routes (research R1). The app
name is `readiness_agent`. The user ID is a random per-browser-tab UUID, because identity is
already enforced by IAP and the app keeps no user state.

## 1. Sessions

```
POST /apps/readiness_agent/users/{user_id}/sessions          → 200 { "id": "<session_id>", ... }
```

The frontend creates **two** sessions per tab: `mapSession` (used once for data) and `chatSession`.

## 2. Session-start map data (FR-008a)

```
POST /run
{
  "app_name": "readiness_agent",
  "user_id": "<user_id>",
  "session_id": "<mapSession>",
  "new_message": { "role": "user", "parts": [ { "text": "LOAD_MAP_DATA v1" } ] }
}
→ 200 [ Event, ... ]
```

- The agent's `before_agent_callback` matches the text exactly, `LOAD_MAP_DATA v1`, and replies
  with **one** event whose `content.parts[0].text` is a JSON document that validates against
  [map-data.schema.json](map-data.schema.json).
- **No LLM call is made** for this request.
- The frontend takes the last event with author `readiness_agent`, parses the text, and checks that
  `schema == "map-data/v1"`.
- **Failure**: a non-200 status, an unparseable payload, a schema mismatch, or a timeout over 20 s
  (SC-004a). The frontend shows the FR-008b error state with Retry and never shows partial counts.
- Hovering never triggers a request. The payload is held for the session.

## 3. Chat turn (FR-010–FR-015)

```
POST /run_sse
{
  "app_name": "readiness_agent",
  "user_id": "<user_id>",
  "session_id": "<chatSession>",
  "streaming": true,
  "new_message": {
    "role": "user",
    "parts": [
      { "text": "<the user's question>" },
      { "text": "CONTEXT v1 {\"county_fips\":\"13067\",\"shelter_id\":null,\"scenario\":{...}}" }
    ]
  }
}
→ text/event-stream of `data: <Event JSON>`
```

The `scenario` object, when present, holds `track` (GeoJSON), `category`, `cutoff_km`,
`affected_county_fips[]`, `affected_shelter_ids[]` and `receiving_top[]` (the first 20 shelter IDs
in rank order).

**What the frontend reads from each Event:**

| Event field | Used for |
|---|---|
| `content.parts[].text` (author = agent, `partial` true or false) | Answer text, assembled in order |
| `content.parts[].functionResponse.response` | Any `shelter_id` or `county_fips` values found, recursively, go into `referenced_*` and are highlighted (FR-014) |
| `groundingMetadata.groundingChunks[].maps` `{uri, title, placeId}` | Sources (FR-012). `placeId` is held in memory only |
| `groundingMetadata.groundingSupports[]` `{segment{startIndex?, endIndex, text}, groundingChunkIndices[]}` | Marks spans as live (FR-013). A null `startIndex` is treated as 0 |
| `errorCode` / `errorMessage` | Shows the failed state with Retry (FR-015) |

**What this feature requires of the readiness agent (dependencies D1 and D2):**

1. Tool results that concern shelters or counties include `shelter_id` or `county_fips`.
2. The agent treats the `CONTEXT v1` part as context, not as a question, and it may mention the
   scenario.
3. Accessibility statements keep the Yes / No / Not recorded distinction (Constitution I).
4. Grounded output changes or annotates a result (Constitution II). Rendering it correctly is this
   feature's job.

## 4. Access (FR-023, FR-024)

- IAP rejects unauthenticated or non-allow-listed requests before they reach the service. The
  browser gets IAP's sign-in or denial page. The app never loads.
- Allow-list changes are made by granting or revoking `roles/iap.httpsResourceAccessor`. They need
  no code change or redeploy.

## 5. Versioning

- `LOAD_MAP_DATA v1`, `CONTEXT v1` and `map-data/v1` are versioned strings.
- A breaking change to the payload bumps all three together.
- The frontend refuses any schema version it does not know.
