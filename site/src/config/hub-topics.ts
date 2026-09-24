export type HubTopicTheme =
  | "mma"
  | "cars"
  | "crime"
  | "roblox"
  | "pets"
  | "gadgets"
  | "stars";

export interface HubTopic {
  id: string;
  title: string;
  subtitle: string;
  url?: string;
  theme: HubTopicTheme;
  size?: "wide";
}

export interface HubTopicGroup {
  id: "events" | "interests";
  title: string;
  topics: HubTopic[];
}

export const HUB_TOPIC_GROUPS: HubTopicGroup[] = [
  {
    id: "events",
    title: "События",
    topics: [
      { id: "mma", title: "MMA TODAY", subtitle: "UFC • MMA • бойцы", theme: "mma" },
      { id: "cars", title: "АВТО", subtitle: "Автомобили • новости", theme: "cars" },
      {
        id: "crime",
        title: "ПРЕСТУПЛЕНИЯ",
        subtitle: "Новости 24/7",
        url: "/crime/",
        theme: "crime",
      },
    ],
  },
  {
    id: "interests",
    title: "Интересы",
    topics: [
      {
        id: "roblox",
        title: "ROBLOX HUB",
        subtitle: "Игры • новости",
        url: "/roblox/",
        theme: "roblox",
        size: "wide",
      },
      {
        id: "pets",
        title: "ХВОСТАТЫЕ НОВОСТИ",
        subtitle: "Кошки • собаки • животные",
        theme: "pets",
      },
      {
        id: "gadgets",
        title: "НУ И ГАДЖЕТЫ",
        subtitle: "ИИ • техника • наука",
        theme: "gadgets",
      },
      {
        id: "stars",
        title: "ЗВЁЗДНЫЕ БУДНИ",
        subtitle: "Шоу-бизнес • знаменитости",
        theme: "stars",
        size: "wide",
      },
    ],
  },
];
