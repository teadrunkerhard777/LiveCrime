import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { z } from "astro/zod";

const sourceSchema = z.object({
  name: z.string().min(1),
  url: z.url(),
  published_at: z.coerce.date().optional(),
});

const updateSchema = z.object({
  date: z.coerce.date(),
  title: z.string().min(1),
  summary: z.string().min(1),
  source_urls: z.array(z.url()).min(1),
});

const events = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/events" }),
  schema: z.object({
    event_id: z.string().regex(/^[a-z0-9-]+$/),
    title: z.string().min(10),
    summary: z.string().min(40),
    event_date: z.coerce.date(),
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
    created_at: z.coerce.date(),
    updated_at: z.coerce.date(),
    topics: z.array(z.string().min(1)).min(1),
    sources: z.array(sourceSchema).min(1),
    updates: z.array(updateSchema).default([]),
    related_events: z.array(z.string()).default([]),
    draft: z.boolean().default(true),
    demo: z.boolean().default(false),
  }),
});

export const collections = { events };
