import type { APIRoute } from 'astro';
import { getBuildStatus } from '../lib/build-status';

export const prerender = true;

export const GET: APIRoute = () => new Response(JSON.stringify(getBuildStatus(), null, 2), {
  headers: {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'public, max-age=300',
  },
});
