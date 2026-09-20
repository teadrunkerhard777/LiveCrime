import type { CollectionEntry } from "astro:content";

export function isPublishableEvent(event: CollectionEntry<"events">) {
  const { data } = event;

  if (data.section !== "crime" || data.publication_status !== "ready") {
    return false;
  }

  if (!data.sources.length || !data.summary.trim()) {
    return false;
  }

  // Учебная карточка показывает шаблон, но всегда закрыта от индексации.
  if (data.demo) {
    return true;
  }

  return data.updates.length > 0;
}
