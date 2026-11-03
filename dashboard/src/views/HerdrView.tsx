import { useEffect, useRef } from "react";
import { Layout } from "../components/Layout";
import { loadHerdr, useStore } from "../store";
import { closeHerdrClient, mountHerdrClient } from "../terminal/herdrClient";

function HerdrClient({ rootRef }: { rootRef: React.RefObject<HTMLDivElement> }) {
  return (
    <div className="herdr-client" ref={rootRef}>
      <div className="herdr-client-host">
        <div className="terminal-drop" aria-hidden="true">
          <span>+</span>
          <b>Drop to attach</b>
        </div>
      </div>
      <header className="herdr-client-head">
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

export function HerdrView() {
  const herdrData = useStore((state) => state.herdrData);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!herdrData) void loadHerdr();
  }, [herdrData]);

  useEffect(() => {
    if (herdrData?.running && rootRef.current) void mountHerdrClient(rootRef.current);
    return closeHerdrClient;
  }, [herdrData?.running]);

  if (!herdrData)
    return (
      <Layout>
        <div className="hint">Loading Herdr…</div>
      </Layout>
    );
  if (!herdrData.running)
    return (
      <Layout>
        <div className="empty" style={{ padding: "24px 32px" }}>
          herdr is not running on this server
        </div>
      </Layout>
    );
  return (
    <Layout>
      <HerdrClient rootRef={rootRef} />
    </Layout>
  );
}
