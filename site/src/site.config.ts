type LandingPoint = {
  title: string;
  description: string;
};

type SiteConfig = {
  name: string;
  kicker: string;
  sourceUrl: string;
  url: string;
  landing: {
    headline: readonly [string, string];
    description: string;
    points: readonly [LandingPoint, LandingPoint, LandingPoint];
  };
};

export const site = {
  /** Project name - sidebar label + topbar crumb. Lowercase per brand. */
  name: "mill",
  /** One-line descriptor under the name in the sidebar and landing eyebrow. */
  kicker: "Put it through the mill",
  /** Source links in the top bar and landing hero. */
  sourceUrl: "https://github.com/frostyard/mill",
  /** Canonical site URL (sitemap, astro `site`). */
  url: "https://mill-docs.bjk.workers.dev",
  /** Project-specific root-page copy. Keep each value concise. */
  landing: {
    headline: ["Spec goes in.", "Evidence comes out."],
    description: "The mill turns a complete specification into a reviewed, gated branch, with deterministic scripts deciding what passes.",
    points: [
      {
        title: "Scripts referee",
        description: "Deterministic code owns every loop, gate, and git operation."
      },
      {
        title: "A rival model grades",
        description: "A different model reviews the plan, each chunk, and the final evidence."
      },
      {
        title: "You decide what ships",
        description: "You approve the plan and decide whether anything leaves the machine."
      }
    ]
  }
} satisfies SiteConfig;
