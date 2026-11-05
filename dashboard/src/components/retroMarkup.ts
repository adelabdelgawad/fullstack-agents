import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { RetroCard } from "./RetroControls";

// Existing detail renderers produce escaped HTML and use delegated events.
// Render the same RetroUI Card used by React views without changing those events.
const slot = "__FSA_RETRO_CARD_CONTENT__";
export function retroCardHtml(content: string, className = ""): string {
  return renderToStaticMarkup(createElement(RetroCard, { className, children: slot })).replace(slot, () => content);
}
