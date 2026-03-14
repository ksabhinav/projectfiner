import { defineConfig } from 'astro/config';
import svelte from '@astrojs/svelte';

export default defineConfig({
  site: 'https://ksabhinav.github.io',
  base: '/projectfiner/',
  integrations: [svelte()],
  output: 'static',
});
