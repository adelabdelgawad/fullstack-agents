import { useEffect, useRef } from "react";
import { loadHerdr, useStore } from "../store";
import { closeHerdrClient, showHerdrClient } from "../terminal/herdrClient";

function HerdrClient({ rootRef, hidden }: { rootRef: React.RefObject<HTMLDivElement>; hidden: boolean }) {
  return (
    <div className="herdr-client" ref={rootRef} hidden={hidden}>
      <div className="herdr-client-host">
        <div className="terminal-drop" aria-hidden="true">
          <span>+</span>
          <b>Drop to attach</b>
        </div>
      </div>
      <header className="herdr-client-head">
        <button
          type="button"
          data-herdr-client-sidebar=""
          aria-label="Expand or collapse Herdr sidebar"
          title="Expand or collapse sidebar (Ctrl+B, B)"
          disabled
        >
          <span aria-hidden="true">‹ ›</span>
        </button>
        <span className="herdr-client-status" data-herdr-client-status="">
          starting…
        </span>
        <button data-herdr-client-reconnect="" hidden>
          reconnect
        </button>
        <button
          data-herdr-client-fullscreen=""
          aria-pressed="false"
          title="Full screen; desktop Chromium also locks the keyboard (hold Esc to leave)"
        >
          full screen
        </button>
        <button
          data-herdr-client-attach=""
          className="herdr-client-attach"
          aria-label="Attach files"
          title="Attach files: their paths are typed into the focused pane"
        >
          +
        </button>
        <input type="file" multiple hidden data-herdr-client-attach-input="" />
      </header>
    </div>
  );
}

export function HerdrView({ active }: { active: boolean }) {
  const herdrData = useStore((state) => state.herdrData);
  const running = Boolean(herdrData?.running);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (active && !herdrData) void loadHerdr();
  }, [active, herdrData]);

  useEffect(() => {
    if (active && running && rootRef.current) showHerdrClient(rootRef.current);
  }, [active, running]);

  useEffect(() => (running ? closeHerdrClient : undefined), [running]);

  if (!herdrData) return active ? <div className="hint">Loading Herdr…</div> : null;
  if (!running)
    return active ? (
      <div className="empty" style={{ padding: "24px 32px" }}>
        herdr is not running on this server
      </div>
    ) : null;
  return <HerdrClient rootRef={rootRef} hidden={!active} />;
}
