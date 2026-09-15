import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { createApp } from "../src/routes.js";
import { LocalStorage } from "../src/storage.js";

async function withApp(
  fn: (app: ReturnType<typeof createApp>) => Promise<void>,
) {
  const dir = await mkdtemp(path.join(tmpdir(), "pon-test-"));
  try {
    const app = createApp(new LocalStorage(dir), { retentionDays: 7 });
    await fn(app);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

test("GET /healthz returns ok", async () => {
  await withApp(async (app) => {
    const res = await app.request("/healthz");
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), { ok: true });
  });
});

test("POST -> GET -> list flow", async () => {
  await withApp(async (app) => {
    // 1. アップロード(slug指定なし)
    const postRes = await app.request("/api/pages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        host: "pon.example.com",
        "x-goog-authenticated-user-email":
          "accounts.google.com:taro@example.com",
      },
      body: JSON.stringify({
        title: "テストページ",
        html: "<h1>こんにちは</h1>",
      }),
    });
    assert.equal(postRes.status, 201);
    const created = (await postRes.json()) as {
      slug: string;
      url: string;
      title: string;
    };
    assert.match(created.slug, /^[a-z0-9][a-z0-9-]*$/);
    assert.equal(created.title, "テストページ");
    assert.equal(created.url, `https://pon.example.com/p/${created.slug}/`);

    // 2. 配信 (trailing slash)
    const getRes = await app.request(`/p/${created.slug}/`);
    assert.equal(getRes.status, 200);
    assert.match(getRes.headers.get("content-type") ?? "", /text\/html/);
    assert.equal(await getRes.text(), "<h1>こんにちは</h1>");

    // 3. /p/:slug はリダイレクト
    const redirectRes = await app.request(`/p/${created.slug}`);
    assert.equal(redirectRes.status, 301);
    assert.equal(
      redirectRes.headers.get("location"),
      `/p/${created.slug}/`,
    );

    // 4. JSON一覧
    const listRes = await app.request("/api/pages", {
      headers: { host: "pon.example.com" },
    });
    assert.equal(listRes.status, 200);
    const list = (await listRes.json()) as {
      pages: Array<{
        slug: string;
        title: string;
        uploader: string;
        updatedAt: string;
        url: string;
      }>;
    };
    assert.equal(list.pages.length, 1);
    const page = list.pages[0];
    assert.equal(page.slug, created.slug);
    assert.equal(page.title, "テストページ");
    assert.equal(page.uploader, "taro@example.com");
    assert.equal(page.url, created.url);
    assert.ok(!Number.isNaN(Date.parse(page.updatedAt)));

    // 5. HTML一覧
    const htmlRes = await app.request("/");
    assert.equal(htmlRes.status, 200);
    const html = await htmlRes.text();
    assert.ok(html.includes("pon"));
    assert.ok(html.includes("テストページ"));
    assert.ok(html.includes("taro@example.com"));
    assert.ok(html.includes("7日で自動削除"));
  });
});

test("explicit slug, overwrite, and subpath assets", async () => {
  await withApp(async (app) => {
    const post = (body: unknown) =>
      app.request("/api/pages", {
        method: "POST",
        headers: { "content-type": "application/json", host: "localhost" },
        body: JSON.stringify(body),
      });

    // slug 指定
    const res1 = await post({
      title: "レポート",
      html: "<p>v1</p>",
      slug: "weekly-report",
    });
    assert.equal(res1.status, 201);
    assert.equal(((await res1.json()) as { slug: string }).slug, "weekly-report");

    // 上書き
    const res2 = await post({
      title: "レポート v2",
      html: "<p>v2</p>",
      slug: "weekly-report",
    });
    assert.equal(res2.status, 201);
    const got = await app.request("/p/weekly-report/");
    assert.equal(await got.text(), "<p>v2</p>");

    // 一覧のタイトルも更新されている
    const list = (await (
      await app.request("/api/pages", { headers: { host: "localhost" } })
    ).json()) as { pages: Array<{ title: string }> };
    assert.equal(list.pages.length, 1);
    assert.equal(list.pages[0].title, "レポート v2");

    // uploader ヘッダー無しは anonymous
    const listFull = (await (
      await app.request("/api/pages", { headers: { host: "localhost" } })
    ).json()) as { pages: Array<{ uploader: string }> };
    assert.equal(listFull.pages[0].uploader, "anonymous");
  });
});

test("missing asset under an existing page returns 404", async () => {
  await withApp(async (app) => {
    await app.request("/api/pages", {
      method: "POST",
      headers: { "content-type": "application/json", host: "localhost" },
      body: JSON.stringify({
        title: "アセット付き",
        html: '<img src="logo.png">',
        slug: "with-assets",
      }),
    });
    const missing = await app.request("/p/with-assets/logo.png");
    assert.equal(missing.status, 404);
  });
});

test("validation and 404 behavior", async () => {
  await withApp(async (app) => {
    // title 欠落
    const bad1 = await app.request("/api/pages", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ html: "<p>x</p>" }),
    });
    assert.equal(bad1.status, 400);

    // 不正 slug
    const bad2 = await app.request("/api/pages", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ title: "x", html: "<p>x</p>", slug: "../etc" }),
    });
    assert.equal(bad2.status, 400);

    // 存在しないページは日本語404
    const nf = await app.request("/p/no-such-page/");
    assert.equal(nf.status, 404);
    const body = await nf.text();
    assert.ok(body.includes("見つかりませんでした"));

    // パストラバーサル
    const trav = await app.request("/p/foo/..%2f..%2fsecret");
    assert.equal(trav.status, 404);
  });
});

test("LocalStorage stores and serves subpath assets", async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "pon-test-"));
  try {
    const storage = new LocalStorage(dir);
    const app = createApp(storage);
    await storage.put(
      "pages/asset-page/index.html",
      Buffer.from("<img src='a.svg'>"),
      { title: "assets", uploader: "x@example.com" },
    );
    await storage.put(
      "pages/asset-page/a.svg",
      Buffer.from("<svg xmlns='http://www.w3.org/2000/svg'/>"),
      {},
    );
    const res = await app.request("/p/asset-page/a.svg");
    assert.equal(res.status, 200);
    assert.match(res.headers.get("content-type") ?? "", /image\/svg\+xml/);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
