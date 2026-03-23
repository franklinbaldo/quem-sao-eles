import { defineCollection, reference, z } from 'astro:content';
import { glob } from 'astro/loaders';

const politicos = defineCollection({
	loader: glob({ base: './src/content/politicos', pattern: '**/*.{md,mdx}' }),
	schema: ({ image }) =>
		z.object({
			name: z.string(),
			cpf: z.string().optional(),
			party: z.string(),
			role: z.string(),
			chamber: z.string(),
			since: z.coerce.date(),
			photo: z.optional(image()),
			tags: z.array(z.string()).optional(),
		}),
});

const noticias = defineCollection({
	loader: glob({ base: './src/content/noticias', pattern: '**/*.{md,mdx}' }),
	schema: () =>
		z.object({
			title: z.string(),
			politician: reference('politicos'),
			date: z.coerce.date(),
			source_url: z.string().url(),
			archive_url: z.string().url(),
			summary: z.string(),
		}),
});

export const collections = { politicos, noticias };
