export const EVENT_STATUS_LABELS = {
  reported: "Появилось первое сообщение",
  investigating: "Идёт проверка или расследование",
  suspect_detained: "Подозреваемый задержан",
  charged: "Предъявлено обвинение",
  trial: "Дело рассматривается в суде",
  verdict: "Вынесен приговор",
  closed: "Событие закрыто для обновлений",
} as const;

export const LEGAL_STATUS_LABELS = {
  no_person_named: "Конкретное лицо не названо",
  suspect: "Лицо упоминается как подозреваемое",
  accused: "Лицу предъявлено обвинение",
  defendant: "Дело в отношении подсудимого рассматривает суд",
  convicted: "Лицо признано виновным судом",
  acquitted: "Лицо оправдано судом",
  case_closed: "Дело прекращено",
} as const;

export function formatDate(date: Date) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

export function formatEventDate(value: string) {
  if (/^\d{4}$/.test(value)) {
    return `${value} год`;
  }

  if (/^\d{4}-\d{2}$/.test(value)) {
    const [year, month] = value.split("-").map(Number);
    return new Intl.DateTimeFormat("ru-RU", {
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    }).format(new Date(Date.UTC(year, month - 1, 1)));
  }

  return formatDate(new Date(value));
}

export function withBase(path: string) {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  return `${base}${path}` || "/";
}
