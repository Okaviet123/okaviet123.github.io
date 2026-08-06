import { Hono } from "hono";
import type { Context } from "hono";
import { contentTypeFor, type PageEntry, type Storage } from "./storage.js";
import { generateSlug, isValidSlug } from "./slug.js";

const IAP_EMAIL_HEADER = "x-goog-authenticated-user-email";

/** IAP ヘッダー("accounts.google.com:user@example.com")からメールアドレスを取り出す */
export function uploaderFromRequest(c: Context): string {
  const raw = c.req.header(IAP_EMAIL_HEADER);
  if (!raw) return "anonymous";
  const idx = raw.lastIndexOf(":");
  const email = idx >= 0 ? raw.slice(idx + 1) : raw;
  return email.trim() || "anonymous";
}

/** リクエストの Host からページ URL を組み立てる */
function pageUrl(c: Context, slug: string): string {
  const host =
    c.req.header("x-forwarded-host") ?? c.req.header("host") ?? "localhost";
  const proto =
    c.req.header("x-forwarded-proto") ??
    (/^(localhost|127\.0\.0\.1)(:\d+)?$/.test(host) ? "http" : "https");
  return `${proto}://${host}/p/${slug}/`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function notFoundHtml(): string {
  return `<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>404 - ページが見つかりません | pon 🫳</title>
<style>
  body { font-family: "Hiragino Sans", "Noto Sans JP", sans-serif; background: #f7f7f8;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; color: #333; }
  .box { text-align: center; padding: 2rem; }
  h1 { font-size: 3rem; margin: 0 0 .5rem; }
  p { color: #666; }
  a { color: #4666e5; text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="box">
  <h1>404 🫳</h1>
  <p>お探しのページは見つかりませんでした。</p>
  <p><a href="/">← ページ一覧へ戻る</a></p>
</div>
</body>
</html>`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function listHtml(pages: PageEntry[], retentionDays: number): string {
  const rows = pages
    .map(
      (p) => `      <li class="item">
        <a class="title" href="/p/${escapeHtml(p.slug)}/">${escapeHtml(p.title)}</a>
        <div class="meta">
          <span class="uploader">${escapeHtml(p.uploader)}</span>
          <span class="sep">·</span>
          <time datetime="${escapeHtml(p.updatedAt)}">${escapeHtml(formatDate(p.updatedAt))}</time>
        </div>
      </li>`,
    )
    .join("\n");

  const empty = `      <li class="empty">まだページがありません。<code>POST /api/pages</code> で最初のページを「ぽん」と置いてみましょう。</li>`;

  return `<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>pon 🫳 - 社内HTMLホスティング</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: "Hiragino Sans", "Noto Sans JP", sans-serif; background: #f7f7f8;
         margin: 0; color: #24292f; line-height: 1.6; }
  .container { max-width: 720px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
  header h1 { font-size: 2rem; margin: 0 0 .25rem; }
  header p.desc { color: #57606a; margin: 0 0 .5rem; font-size: .95rem; }
  p.note { color: #9a6700; background: #fff8c5; border: 1px solid #eed888;
           border-radius: 8px; padding: .5rem .85rem; font-size: .85rem; margin: 0 0 2rem; }
  ul.pages { list-style: none; margin: 0; padding: 0; background: #fff;
             border: 1px solid #e1e4e8; border-radius: 10px; overflow: hidden; }
  li.item { padding: 1rem 1.25rem; border-bottom: 1px solid #eef0f2; }
  li.item:last-child { border-bottom: none; }
  li.item:hover { background: #fafbfc; }
  a.title { font-size: 1.05rem; font-weight: 600; color: #1d4ed8; text-decoration: none; word-break: break-all; }
  a.title:hover { text-decoration: underline; }
  .meta { font-size: .82rem; color: #6e7781; margin-top: .15rem; }
  .sep { margin: 0 .35rem; }
  li.empty { padding: 2rem 1.25rem; color: #6e7781; text-align: center; }
  code { background: #eff1f3; padding: .1rem .35rem; border-radius: 4px; font-size: .85em; }
  footer { margin-top: 2rem; font-size: .8rem; color: #8b949e; text-align: center; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>pon 🫳</h1>
    <p class="desc">HTMLファイルを「ポン」と置くだけで社内URLを発行できる、社内HTMLホスティング環境です。</p>
    <p class="note">⏳ ページは${retentionDays}日で自動削除されます。</p>
  </header>
  <main>
    <ul class="pages">
${pages.length > 0 ? rows : empty}
    </ul>
  </main>
  <footer>全 ${pages.length} ページ</footer>
</div>
</body>
</html>`;
}

export interface AppOptions {
  /** 一覧UIに表示する自動削除までの日数(削除自体はGCSライフサイクル側で実施) */
  retentionDays?: number;
}

export function createApp(storage: Storage, options: AppOptions = {}): Hono {
  const retentionDays = options.retentionDays ?? 7;
  const app = new Hono();

  /* ---------------- healthz ---------------- */
  app.get("/healthz", (c) => c.json({ ok: true }));

  /* ---------------- アップロード ---------------- */
  app.post("/api/pages", async (c) => {
    let body: unknown;
    try {
      body = await c.req.json();
    } catch {
      return c.json({ error: "リクエストボディが不正なJSONです" }, 400);
    }
    const { title, html, slug: requestedSlug } = (body ?? {}) as {
      title?: unknown;
      html?: unknown;
      slug?: unknown;
    };

    if (typeof title !== "string" || title.trim() === "") {
      return c.json({ error: "title は必須の文字列です" }, 400);
    }
    if (typeof html !== "string" || html === "") {
      return c.json({ error: "html は必須の文字列です" }, 400);
    }
    let slug: string;
    if (requestedSlug === undefined || requestedSlug === null) {
      slug = generateSlug();
    } else if (typeof requestedSlug === "string" && isValidSlug(requestedSlug)) {
      slug = requestedSlug;
    } else {
      return c.json(
        { error: "slug は英小文字・数字・ハイフンのみ(100文字以内)で指定してください" },
        400,
      );
    }

    const uploader = uploaderFromRequest(c);
    await storage.put(`pages/${slug}/index.html`, Buffer.from(html, "utf8"), {
      title: title.trim(),
      uploader,
    });

    return c.json({ slug, url: pageUrl(c, slug), title: title.trim() }, 201);
  });

  /* ---------------- ページ一覧 (JSON) ---------------- */
  app.get("/api/pages", async (c) => {
    const entries = await storage.listPages();
    return c.json({
      pages: entries.map((p) => ({
        slug: p.slug,
        title: p.title,
        uploader: p.uploader,
        updatedAt: p.updatedAt,
        url: pageUrl(c, p.slug),
      })),
    });
  });

  /* ---------------- ページ一覧 (HTML) ---------------- */
  app.get("/", async (c) => {
    const entries = await storage.listPages();
    return c.html(listHtml(entries, retentionDays));
  });

  /* ---------------- ページ配信 ---------------- */
  // /p/:slug → /p/:slug/ にリダイレクト
  app.get("/p/:slug", (c) => {
    const slug = c.req.param("slug");
    return c.redirect(`/p/${slug}/`, 301);
  });

  // /p/:slug/ および /p/:slug/<subpath>
  app.get("/p/:slug/*", async (c) => {
    const slug = c.req.param("slug");
    if (!isValidSlug(slug)) {
      return c.html(notFoundHtml(), 404);
    }
    const prefix = `/p/${slug}/`;
    const rawPath = decodeURIComponent(c.req.path);
    let subpath = rawPath.startsWith(prefix)
      ? rawPath.slice(prefix.length)
      : "";
    if (subpath === "" || subpath.endsWith("/")) {
      subpath += "index.html";
    }
    // パストラバーサル防止
    if (subpath.split("/").some((seg) => seg === ".." || seg === "")) {
      return c.html(notFoundHtml(), 404);
    }

    const key = `pages/${slug}/${subpath}`;
    const stored = await storage.get(key);
    if (!stored) {
      return c.html(notFoundHtml(), 404);
    }
    return c.body(new Uint8Array(stored.body), 200, {
      "Content-Type": contentTypeFor(key),
      "Cache-Control": "private, no-cache",
    });
  });

  /* ---------------- 404 ---------------- */
  app.notFound((c) => c.html(notFoundHtml(), 404));

  return app;
}
