export const LIVE_UPLOAD_MAX_BYTES = 50 * 1024 * 1024;

export const uploadingText = (files: File[]): string =>
  files.length === 1 ? `uploading ${files[0].name}…` : `uploading ${files.length} files…`;

export async function uploadFiles(files: File[], prefix: string): Promise<string[]> {
  const paths: string[] = [];
  for (const file of files) {
    const response = await fetch(`${prefix}name=${encodeURIComponent(file.name || "file")}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    });
    if (!response.ok) throw new Error((await response.text()) || `upload failed (${response.status})`);
    const data = (await response.json()) as { ok?: boolean; path?: unknown };
    if (!data.ok || typeof data.path !== "string") throw new Error("invalid upload response");
    paths.push(data.path);
  }
  return paths;
}

export function filesFromPaste(event: ClipboardEvent): File[] {
  const files = [...(event.clipboardData?.items ?? [])]
    .filter((entry) => entry.kind === "file")
    .map((entry) => entry.getAsFile())
    .filter((file): file is File => Boolean(file));
  if (files.length) {
    event.preventDefault();
    event.stopPropagation();
  }
  return files;
}

export function wireFileDrop(box: HTMLElement, onFiles: (files: File[]) => void): void {
  const hasFiles = (event: DragEvent) => [...(event.dataTransfer?.types ?? [])].includes("Files");
  box.addEventListener("dragover", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
    box.classList.add("file-drag-over");
  });
  box.addEventListener("dragleave", (event) => {
    if (!event.relatedTarget || !box.contains(event.relatedTarget as Node)) box.classList.remove("file-drag-over");
  });
  box.addEventListener("drop", (event) => {
    box.classList.remove("file-drag-over");
    const files = [...(event.dataTransfer?.files ?? [])];
    if (!files.length) return;
    event.preventDefault();
    event.stopPropagation();
    onFiles(files);
  });
}
