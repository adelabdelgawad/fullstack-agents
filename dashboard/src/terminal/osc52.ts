export function createOsc52Scanner(onText: (text: string) => void): (chunk: Uint8Array) => void {
  const prefix = [0x1b, 0x5d, 0x35, 0x32, 0x3b];
  let matched = 0;
  let bytes: number[] | null = null;
  const finish = () => {
    const text = new TextDecoder("latin1").decode(Uint8Array.from(bytes ?? []));
    const payload = text.slice(text.indexOf(";") + 1);
    bytes = null;
    if (!payload || payload === "?") return;
    try {
      onText(new TextDecoder().decode(Uint8Array.from(atob(payload), (char) => char.charCodeAt(0))));
    } catch {
      return;
    }
  };
  return (chunk) => {
    for (const byte of chunk) {
      if (bytes) {
        if (byte === 0x07) finish();
        else if (byte === 0x5c && bytes.at(-1) === 0x1b) {
          bytes.pop();
          finish();
        } else if (bytes.length < 4 << 20) bytes.push(byte);
        else bytes = null;
        continue;
      }
      matched = byte === prefix[matched] ? matched + 1 : byte === 0x1b ? 1 : 0;
      if (matched === prefix.length) {
        bytes = [];
        matched = 0;
      }
    }
  };
}
