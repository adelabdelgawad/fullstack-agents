# Dark RetroUI dashboard

The final scope preserves the original Agents and History organization: summary strip, filters, collapsible Orchestrators navigation, card grid, activity feed, inline details, and History table.

Implemented presentation:
- Shared pixel-retroui Button, Input, and Card components with system typography and a dark palette.
- RetroUI frames inside Information sections, health metrics, task/run cards, and Git changes columns.
- Three-row (64px) usage tiles with segmented plan/context bars and green, amber, and teal accents inspired by the supplied reference.
- Static interactions, keyboard access, and persisted sidebar/disclosure state.
- Component-only library styles, excluding its global reset; retained BSD license attribution.
- Local preview proxies authenticated dashboard traffic to port 8799. Backend authentication remains required.

Verification: dashboard tests, TypeScript and production build; browser checks for search, keyboard selection, sidebar collapse/expand, Information disclosures, Git file selection/column toggles, and tablet/phone widths. Live access was verified with the user's approved dashboard token; no credentials are committed.

Unrelated Herdr and plugin edits remain outside this change. Release assets are built from the isolated commit scope.

Final refinements: cap summary cards at 150px with a 64px three-row height, show Codex credits on the first row, and shorten plan labels. Give Agents, Herdr, and History distinct /next/ page URLs with direct-link, refresh, and back/forward support. Wrap long attention flags inside agent cards while retaining space for Respond.
