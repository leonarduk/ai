# Putting it on LinkedIn

The checklist for turning the deployed app into an actual link on
[linkedin.com/in/leonarduk](https://www.linkedin.com/in/leonarduk) — the "just tell me what to
click" version, same style as [`deployment.md`](./deployment.md).

Landing page URL (what LinkedIn should link to, never the raw Render URL):
`https://leonarduk.github.io/ai-systems-lab/projects/08-linkedin-avatar/site/`

---

## 1. Featured section

1. On your profile, click **Add profile section** (or the **+** on an existing Featured section) →
   **Recommended** → **Featured** → **Add a link**.
2. Paste the landing page URL above and give it a moment — LinkedIn fetches the preview from the
   page's Open Graph tags automatically, so the title ("Steve Leonard — AI Twin"), description and
   image should populate on their own. `site/og-image.png` was already built for exactly this; there's
   nothing extra to design or upload.
3. If the preview comes back blank or shows something stale, LinkedIn caches URL scrapes. Run the
   URL through the [LinkedIn Post Inspector](https://www.linkedin.com/post-inspector/) first to force
   a fresh fetch, then try adding it to Featured again.
4. Save.

## 2. Website field (contact info)

1. On your profile, open **Contact info** (below your name/headline) → the edit (pencil) icon.
2. Under **Website**, click **Add website** → type **Portfolio** (or **Other** if Portfolio isn't
   offered) → paste the landing page URL above → **Save**.

## 3. Update the existing "Projects" entry

There's already a **Projects** section entry for this ("AI Systems Lab" → sub-project "Steve Leonard
— AI Twin"), added before the app was deployed — it currently links to the GitHub repo instead of
the live app or landing page.

1. On your profile, find that project entry → the edit (pencil) icon.
2. Update its link to the landing page URL above (or the live app URL directly, if you'd rather send
   people straight into the chat).
3. Save.

## 4. Launch post (draft)

Edit freely — this is a starting point, not a script.

> I built an AI version of myself that can talk about my career and my GitHub projects. Try it: [landing page link]
>
> A few things I wanted to get right:
>
> - It only answers from what's actually true — a redacted copy of my CV and a live snapshot of my public repos, refreshed nightly. If it doesn't know something, it says so instead of making it up.
> - It's cheap to run. I picked DeepSeek over a bigger-name API specifically so a demo page doesn't cost real money to leave running — and then designed around that constraint on purpose.
> - It has real guardrails: rate limits, an input cap, and a hard daily spend kill-switch. A public endpoint with an API key behind it needs those from day one, not as an afterthought.
> - Want to get in touch after chatting with it? Tell it, and your details come straight to me.
>
> It's part of a bigger repo where I'm building production-quality AI tooling and writing up what I learn, mistakes included: [repo link — https://github.com/leonarduk/ai-systems-lab]
>
> Happy to talk through how any of it works.

## 5. Verify

Once both are live, reload your public profile (or use an incognito window — Featured content can
render differently to you than to a visitor) and confirm:

- The Featured card shows the image/title/description, not a bare link
- Clicking it lands on the landing page, and "Start chatting" reaches a warm app
- The Website field under Contact info opens the same URL
