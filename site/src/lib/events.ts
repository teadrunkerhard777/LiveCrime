export const EVENT_STATUS_LABELS = {
  reported: "Появилось первое сообщение",
  investigating: "Идёт проверка или расследование",
  suspect_detained: "Подозреваемый задержан",
  charged: "Предъявлено обвинение",
  trial: "Дело рассматривается в суде",
  verdict: "Вынесен приговор",
  closed: "Событие закрыто для обновлений",
} as const;

export function formatDate(date: Date) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

export function withBase(path: string) {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  return `${base}${path}` || "/";
}
