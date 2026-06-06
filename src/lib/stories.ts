import fs from "node:fs";
import path from "node:path";
import { CATEGORY_LABELS, type Article, type Category, formatDate, loadArticles } from "./articles";

export type StoryStatus = "active" | "complete" | "paused";

export interface StoryArticleRef {
  slug: string;
  label?: string;
  note?: string;
}

export interface StoryConfig {
  id: string;
  title: string;
  subtitle?: string;
  description: string;
  category: Category;
  status: StoryStatus;
  updatedAt: string;
  cadence?: string;
  articles: StoryArticleRef[];
}

export interface ResolvedStoryArticle extends StoryArticleRef {
  article: Article;
  part: number;
}

export interface Story extends StoryConfig {
  categoryLabel: { en: string; zh: string };
  resolvedArticles: ResolvedStoryArticle[];
}

const STORIES_DIR = path.join(process.cwd(), "data", "stories");

export function loadStories(): Story[] {
  if (!fs.existsSync(STORIES_DIR)) {
    return [];
  }

  const articlesBySlug = new Map(loadArticles().map((article) => [article.slug, article]));
  const stories: Story[] = [];

  for (const file of fs.readdirSync(STORIES_DIR).filter((name) => name.endsWith(".json"))) {
    const full = path.join(STORIES_DIR, file);
    try {
      const config = JSON.parse(fs.readFileSync(full, "utf-8")) as StoryConfig;
      const resolvedArticles = config.articles
        .map((ref, index) => {
          const article = articlesBySlug.get(ref.slug);
          if (!article) return undefined;
          return {
            ...ref,
            article,
            part: index + 1,
          };
        })
        .filter((item): item is ResolvedStoryArticle => Boolean(item));

      stories.push({
        ...config,
        categoryLabel: CATEGORY_LABELS[config.category],
        resolvedArticles,
      });
    } catch (err) {
      console.error(`Failed to parse story ${full}:`, err);
    }
  }

  stories.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  return stories;
}

export function getStoryById(id: string): Story | undefined {
  return loadStories().find((story) => story.id === id);
}

export function getStoriesForArticle(slug: string): Story[] {
  return loadStories().filter((story) =>
    story.resolvedArticles.some((item) => item.article.slug === slug)
  );
}

export function formatStoryUpdatedAt(iso: string): string {
  return formatDate(iso, "zh");
}
