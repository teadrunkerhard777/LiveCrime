import type { APIRoute } from "astro";
import { withBase } from "../lib/events";

export const GET: APIRoute = ({ site }) => {
  const sitemapUrl = new URL(withBase("/sitemap.xml"), site).toString();

  return new Response(`User-agent: *\nAllow: /\n\nSitemap: ${sitemapUrl}\n`, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
