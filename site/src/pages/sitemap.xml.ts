import { getCollection } from "astro:content";
import type { APIRoute } from "astro";
import { isPublishableEvent } from "../lib/content-quality";
import { withBase } from "../lib/events";

function escapeXml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

export const GET: APIRoute = async ({ site }) => {
  const events = (await getCollection("events"))
    .filter(isPublishableEvent)
    .filter(({ data }) => !data.demo);
  const pages = [
    { path: "/", changefreq: "weekly", priority: "1.0" },
    { path: "/crime/", changefreq: "daily", priority: "0.9" },
    { path: "/roblox/", changefreq: "daily", priority: "0.9" },
    { path: "/cars/", changefreq: "daily", priority: "0.9" },
    { path: "/mma/", changefreq: "daily", priority: "0.9" },
    { path: "/stars/", changefreq: "daily", priority: "0.9" },
    { path: "/pets/", changefreq: "daily", priority: "0.9" },
    { path: "/gadgets/", changefreq: "daily", priority: "0.9" },
    { path: "/about/", changefreq: "monthly", priority: "0.5" },
    ...events.map((event) => ({
      path: `/crime/${event.id}/`,
      changefreq: "weekly",
      priority: "0.8",
      lastmod: event.data.updated_at.toISOString(),
    })),
  ];

  const urls = pages
    .map((page) => {
      const location = new URL(withBase(page.path), site).toString();
      const lastmod = "lastmod" in page ? `\n    <lastmod>${page.lastmod}</lastmod>` : "";
      return `  <url>\n    <loc>${escapeXml(location)}</loc>${lastmod}\n    <changefreq>${page.changefreq}</changefreq>\n    <priority>${page.priority}</priority>\n  </url>`;
    })
    .join("\n");

  const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;

  return new Response(body, {
    headers: { "Content-Type": "application/xml; charset=utf-8" },
  });
};
