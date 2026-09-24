import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { z } from "astro/zod";

const sourceSchema = z.object({
  name: z.string().min(1),
  url: z.url(),
  published_at: z.coerce.date().optional(),
});

const displayDateSchema = z.string().refine(
  (value) =>
    /^\d{4}$/.test(value) ||
    /^\d{4}-(0[1-9]|1[0-2])$/.test(value) ||
    !Number.isNaN(Date.parse(value)),
  "Укажите год, год и месяц либо полную дату.",
);

const updateSchema = z.object({
  date: displayDateSchema,
  title: z.string().min(1),
  summary: z.string().min(1),
  source_urls: z.array(z.url()).min(1),
});

const imageSchema = z.object({
  url: z.url(),
  alt: z.string().min(1),
  credit: z.string().min(1),
  source_url: z.url(),
});

const events = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/events" }),
  schema: z.object({
    event_id: z.string().regex(/^[a-z0-9-]+$/),
    section: z.literal("crime"),
    publication_status: z.enum(["draft", "review", "ready"]),
    title: z.string().min(10),
    summary: z.string().min(40),
    event_date: displayDateSchema,
    date_basis: z.enum(["event", "source_publication"]).default("event"),
    location: z.object({
      country: z.string().min(1),
      region: z.string().min(1),
      locality: z.string().min(1),
    }),
    status: z.enum([
      "reported",
      "investigating",
      "suspect_detained",
      "charged",
      "trial",
      "verdict",
      "closed",
    ]),
    legal_status: z.enum([
      "no_person_named",
      "suspect",
      "accused",
      "defendant",
      "convicted",
      "acquitted",
      "case_closed",
      "not_assessed",
    ]),
    created_at: z.coerce.date(),
    updated_at: z.coerce.date(),
    topics: z.array(z.string().min(1)).min(1),
    image: imageSchema.optional(),
    sources: z.array(sourceSchema).min(1),
    updates: z.array(updateSchema).default([]),
    related_events: z.array(z.string()).default([]),
    demo: z.boolean().default(false),
  }),
});

const roblox = defineCollection({
  loader: glob({ pattern: "**/*.json", base: "./src/content/roblox" }),
  schema: z.object({
    message_id: z.string().regex(/^\d+$/),
    text: z.string().min(1),
    published_at: z.coerce.date(),
    image_url: z.url(),
    telegram_url: z.url(),
  }),
});

const crimeFeed = defineCollection({
  loader: glob({ pattern: "**/*.json", base: "./src/content/crime-feed" }),
  schema: z.object({
    message_id: z.string().regex(/^\d+$/),
    text: z.string().min(1),
    published_at: z.coerce.date(),
    image_url: z.url(),
    telegram_url: z.url(),
  }),
});

export const collections = { events, roblox, crimeFeed };
