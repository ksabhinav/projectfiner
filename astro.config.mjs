import { defineConfig } from 'astro/config';
import svelte from '@astrojs/svelte';

export default defineConfig({
  site: 'https://projectfiner.com',
  base: '/',
  integrations: [svelte()],
  output: 'static',
});
