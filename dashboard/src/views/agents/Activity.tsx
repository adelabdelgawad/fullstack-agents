import type { Card } from "../../lib/types";
import { openCard, useStore } from "../../store";

interface ActivityItem { at: number; tone: string; key?: string; who: string; text: string }

function time(at: number): string {
  return new Date(at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
}

export function Activity() {
  const state = useStore((value) => value.state);
  const feed = useStore((value) => value.fleet.feed);
  if (!feed) return null;
  const items = (state?.activity || []) as ActivityItem[];
  const known = new Set((state?.cards || []).map((card) => card.key));
  return <section className="feed" aria-label="Activity"><h2>Activity <span>newest first</span></h2>{items.length ? <ol>{items.map((item, index) => <ActivityRow item={item} open={!!item.key && known.has(item.key)} key={`${item.at}-${index}`} />)}</ol> : <div className="fnone">No activity since the dashboard started.</div>}<div className="fcount" style={{ marginTop: 8 }}>Only the latest 150 events are kept in memory.</div></section>;
}

function ActivityRow({ item, open }: { item: ActivityItem; open: boolean }) {
  const activate = () => { if (item.key) openCard(item.key); };
  return <li className={item.tone} data-open={open ? item.key : undefined} tabIndex={open ? 0 : undefined} onClick={open ? activate : undefined} onKeyDown={open ? (event) => event.key === "Enter" && activate() : undefined}><time>{time(item.at)}</time><div className="fbody" title={item.text}><b>{item.who}</b> <span className="ftext">{item.text}</span></div></li>;
}

export function CardActivity({ card }: { card: Card }) {
  const items = ((useStore((value) => value.state?.activity) || []) as ActivityItem[]).filter((item) => item.key === card.key).slice(0, 20);
  return items.length ? <ol className="detail-feed">{items.map((item, index) => <li className={item.tone} key={`${item.at}-${index}`}><time>{time(item.at)}</time> {item.text}</li>)}</ol> : <div className="s">No activity recorded since the dashboard started.</div>;
}
