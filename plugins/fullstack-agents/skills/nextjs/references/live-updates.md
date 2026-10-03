# Live updates — EventSource / WebSocket lifecycle in the browser

The canonical client rules for server-pushed updates (SSE through a Next.js route handler, or a
WebSocket). Server-side WebSocket code is the `websocket` skill; refresh decisions after an event
are [data-freshness.md](data-freshness.md). Read both before adding, sharing or changing a stream.

## 1. One owner per connection

- One module owns each connection's lifecycle: open, retry timers, close. Components subscribe to
  it; they never construct their own `EventSource`/`WebSocket` for a stream that already has an
  owner.
- Share a connection only between subscribers with the same authenticated identity, scope,
  audience and stream. The URL alone is not a compatibility key: two audiences can share a path
  and receive different events.
- Reference-count subscribers. The connection closes, and its timers are cancelled, when the last
  subscriber leaves — including when it leaves during a backoff wait.
- One subscriber's cleanup never closes a connection another subscriber still holds. Verify under
  React Strict Mode (mount → unmount → mount) and route transitions between two consumers.
- Every subscriber keeps its own event types and filters. Sharing must not drop an event type one
  consumer needs, nor deliver another audience's events.
- On logout or identity change, close every connection and discard pending retries, resyncs and
  queued work belonging to the old identity.

## 2. Reconnect

- `EventSource` retries by itself only after a dropped 200 stream. A non-200 response, or a wrong
  `Content-Type`, sets `readyState` to `CLOSED` and it never retries. The owner must detect
  `CLOSED` and reopen; otherwise one upstream outage silences the page until reload.
- Native retry and explicit reconnect must not both run: when the owner reopens, it closes the old
  instance first, and while native retry is in progress (`CONNECTING`) it does not start its own.
  At most one live connection and one pending timer per owner.
- Transient failures (network, 5xx, upstream down): bounded exponential backoff with jitter (cap
  the *delay*, e.g. 30 s). Keep trying for as long as anyone is subscribed; never give up after a
  fixed number of attempts. Pause or slow down while the tab is hidden if the freshness
  requirement allows, and reconnect promptly on return.
- Expired authentication (401 / an `auth_expired` frame): run the app's session refresh, then
  reconnect. Bound it — a small number of refresh attempts, then hand over to the app's login
  path. Never loop on a credential that keeps failing.
- Confirmed forbidden access (403 / a `forbidden` frame): stop. Do not reconnect a stream the user
  is not allowed to read; surface it.
- Callbacks from a superseded connection are ignored: tag each connection (generation counter or
  instance identity) and drop `onmessage`/`onerror`/`onopen` from any instance that is no longer
  current.

## 3. Proxy route (SSE through Next.js)

- Pass the upstream stream through with `Content-Type: text/event-stream`, `Cache-Control:
  no-cache, no-transform`, no compression and no buffering; propagate the client's abort to the
  upstream request and release it on close.
- Never turn an authentication or authorization failure, or an unrelated HTTP error, into a stream
  that looks successful. A 401/403 must reach the client as a distinguishable signal (a status, or
  an explicit `auth_expired`/`forbidden` frame the client handles) — not as an empty 200 stream.
- A temporary upstream outage may be reported as an SSE error frame only if the client treats that
  frame as a transient failure and reconnects (§2). If the proxy returns a non-200 instead, the
  client must handle `CLOSED` (§2). Test both: the payload-less transport error and the
  application error frame.

## 4. After reconnect: resync, not a storm

- A reconnect may have missed events. Request one resync through the dataset's refresh
  coordinator ([data-freshness.md](data-freshness.md) §2) — once per reconnect, not once per
  subscriber and not once per missed event.
- If the server sends a resync/snapshot marker on connect, use it instead of a client refetch.
  Skip the initial resync on first mount only when nothing can be missed between the server
  render and the subscription (the marker or snapshot covers that window); otherwise resync once
  after the first `open`.
- Keep a watchdog (no events for N seconds on a supposedly open stream → resync) when the
  transport can go half-open; it is the fallback for missed events, not a polling loop.

## 5. Mutation echoes

A local mutation usually comes back as a realtime event about the same row. Handling it:

- Row id plus a short time window is not enough to discard an event: another user may have
  updated the same row in that window.
- Use reliable correlation where it exists — a mutation id echoed in the event, or a row
  version/`updated_at` that is monotonic. Discard an event only when it is provably not newer
  than the state already applied.
- Otherwise do not discard: coalesce. The event triggers the coordinator's refetch, which merges
  with any refetch the mutation already started; the newest server state wins.
- Handle: an echo arriving **before** the mutation response, duplicate echoes, out-of-order
  events, and another user's update to the same row immediately after yours.
- Do not add a backend protocol (mutation ids, versions) only so a client template can skip a
  refetch. Propose it separately when the measured cost justifies it.

## 6. Verification

- [ ] Connections per page in a browser trace equal the number of distinct (identity, audience,
      stream) owners — no duplicates after navigation between two consumers or in Strict Mode.
- [ ] Stop the upstream, restart it, repeat several times: the page recovers each time and shows
      current data within the stated freshness bound, with one connection afterwards.
- [ ] Expired session: bounded refresh, then reconnect or the login path. Forbidden: no reconnect.
- [ ] Unmount during a backoff wait leaves no timer and no connection.
- [ ] Logout closes every stream; the next identity never receives the previous one's events.
- [ ] A local mutation followed immediately by another user's update to the same row shows the
      other user's value.
