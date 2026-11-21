import { useEffect, useState } from "react";
import { getJson } from "../../lib/api";

export interface SlashCommand {
  name: string;
  description: string;
}

const SHOWN = 8;
let cached: Promise<SlashCommand[]> | null = null;

/** The slash commands sessions offer (Claude Code built-ins, user, project and plugin commands and skills). */
export function useSlashCommands(): SlashCommand[] {
  const [commands, setCommands] = useState<SlashCommand[]>([]);
  useEffect(() => {
    let live = true;
    cached ||= getJson<{ commands: SlashCommand[] }>("/api/slash")
      .then((data) => data.commands || [])
      .catch(() => {
        cached = null;
        return [];
      });
    void cached.then((list) => live && setCommands(list));
    return () => {
      live = false;
    };
  }, []);
  return commands;
}

/** Suggestions while the box holds only "/word": names starting with it first (also after a "plugin:" prefix),
 * then names containing it. Nothing once the command is followed by a space. */
export function matchCommands(commands: SlashCommand[], text: string): SlashCommand[] {
  const typed = /^\/(\S*)$/.exec(text);
  if (!typed) return [];
  const word = typed[1].toLowerCase();
  const starts = (name: string) => name.startsWith(word) || name.split(":").pop()!.startsWith(word);
  const lower = commands.map((command) => ({ command, name: command.name.toLowerCase() }));
  const first = lower.filter((item) => starts(item.name));
  const rest = lower.filter((item) => !starts(item.name) && item.name.includes(word));
  return [...first, ...rest].slice(0, SHOWN).map((item) => item.command);
}

export function SlashMenu({
  items,
  active,
  pick,
}: {
  items: SlashCommand[];
  active: number;
  pick: (name: string) => void;
}) {
  return (
    <ul className="chat-slash" role="listbox" aria-label="Slash commands">
      {items.map((item, index) => (
        <li
          key={item.name}
          role="option"
          aria-selected={index === active}
          className={index === active ? "on" : ""}
          onMouseDown={(event) => {
            event.preventDefault();
            pick(item.name);
          }}
        >
          <span className="chat-slash-name">/{item.name}</span>
          <span className="chat-slash-text">{item.description}</span>
        </li>
      ))}
    </ul>
  );
}
