export function openAgent(_sid: string, _id: string, _view = "console"): void {}

export function isOutOpen(): boolean {
  return false;
}

export function OutDialog() {
  return (
    <dialog id="out" aria-labelledby="out-title">
      <div className="oh">
        <h3 id="out-title"></h3>
        <span className="s" id="out-meta"></span>
        <button className="action-button" id="out-copy" style={{ marginLeft: 0 }}>
          Copy
        </button>
        <button className="action-button" id="out-close" style={{ marginLeft: 0 }}>
          Close
        </button>
      </div>
      <div className="items" id="out-items" role="group" aria-label="Choose output"></div>
      <div id="out-info"></div>
      <div id="out-files"></div>
      <pre id="out-pre" tabIndex={0} aria-label="Console output"></pre>
    </dialog>
  );
}
