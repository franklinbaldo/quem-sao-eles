// @ts-check

import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import { defineConfig } from 'astro/config';

import svelte from '@astrojs/svelte';

// https://astro.build/config
export default defineConfig({
    site: 'https://franklinbaldo.github.io',
    base: '/quem-sao-eles',
    integrations: [mdx(), sitemap(), svelte()],
});