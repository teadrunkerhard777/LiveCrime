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
  image: string;
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
      {
        id: "mma",
        title: "MMA TODAY",
        subtitle: "UFC • MMA • бойцы",
        image: "/channel-logos/mma.jpg",
        url: "/mma/",
        theme: "mma",
      },
      {
        id: "cars",
        title: "АВТО",
        subtitle: "Автомобили • новости",
        image: "/channel-logos/auto.jpg",
        url: "/cars/",
        theme: "cars",
      },
      {
        id: "crime",
        title: "ПРЕСТУПЛЕНИЯ",
        subtitle: "Новости 24/7",
        image: "/channel-logos/crime.jpg",
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
        image: "/channel-logos/roblox.jpg",
        url: "/roblox/",
        theme: "roblox",
        size: "wide",
      },
      {
        id: "pets",
        title: "ХВОСТАТЫЕ НОВОСТИ",
        subtitle: "Кошки • собаки • животные",
        image: "/channel-logos/pets.jpg",
        theme: "pets",
      },
      {
        id: "gadgets",
        title: "НУ И ГАДЖЕТЫ",
        subtitle: "ИИ • техника • наука",
        image: "/channel-logos/gadgets.jpg",
        theme: "gadgets",
      },
      {
        id: "stars",
        title: "ЗВЁЗДНЫЕ БУДНИ",
        subtitle: "Шоу-бизнес • знаменитости",
        image: "/channel-logos/stars.jpg",
        url: "/stars/",
        theme: "stars",
        size: "wide",
      },
    ],
  },
];
