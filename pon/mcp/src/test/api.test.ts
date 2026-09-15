/**
 * api.ts の単体テスト。
 * ローカルにモックHTTPサーバーを立てて、リクエスト/レスポンス処理を検証する。
 * 実行: npm test
 */
import assert from "node:assert/strict";
import { createServer, type Server, type IncomingMessage } from "node:http";
import { after, before, describe, it } from "node:test";
import {
  formatPageList,
  formatUploadResult,
  getAuthHeaders,
  listPages,
  resolveConfig,
  uploadPage,
  type PageInfo,
  type PonConfig,
} from "../api.js";

interface RecordedRequest {
  method: string;
  url: string;
  headers: IncomingMessage["headers"];
  body: string;
}

let server: Server;
let baseUrl: string;
const requests: RecordedRequest[] = [];

/** 次のレスポンスをテストごとに差し替えるためのハンドラ */
let nextResponse: { status: number; body: unknown } = { status: 200, body: {} };

before(async () => {
  server = createServer((req, res) => {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      requests.push({
        method: req.method ?? "",
        url: req.url ?? "",
        headers: req.headers,
        body,
      });
      res.writeHead(nextResponse.status, {
        "Content-Type": "application/json",
      });
      res.end(JSON.stringify(nextResponse.body));
    });
  });
  await new Promise<void>((resolveStart) =>
    server.listen(0, "127.0.0.1", resolveStart),
  );
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("unexpected server address");
  }
  baseUrl = `http://127.0.0.1:${address.port}`;
});

after(() => {
  server.close();
});

function config(overrides: Partial<PonConfig> = {}): PonConfig {
  return { baseUrl, ...overrides };
}

describe("resolveConfig", () => {
  it("PON_BASE_URL が無いと throw する", () => {
    assert.throws(() => resolveConfig({}), /PON_BASE_URL/);
  });

  it("末尾スラッシュを除去して設定を返す", () => {
    const c = resolveConfig({ PON_BASE_URL: "https://pon.example.com/" });
    assert.equal(c.baseUrl, "https://pon.example.com");
    assert.equal(c.idToken, undefined);
    assert.equal(c.iapAudience, undefined);
  });

  it("PON_ID_TOKEN / PON_IAP_AUDIENCE を読み取る", () => {
    const c = resolveConfig({
      PON_BASE_URL: "https://pon.example.com",
      PON_ID_TOKEN: "tok",
      PON_IAP_AUDIENCE: "aud",
    });
    assert.equal(c.idToken, "tok");
    assert.equal(c.iapAudience, "aud");
  });
});

describe("getAuthHeaders", () => {
  it("PON_ID_TOKEN があれば Bearer ヘッダーを付ける", async () => {
    const headers = await getAuthHeaders(config({ idToken: "my-token" }));
    assert.deepEqual(headers, { Authorization: "Bearer my-token" });
  });

  it("idToken は iapAudience より優先される", async () => {
    // iapAudience も設定されているが、google-auth-library には触らず idToken を使う
    const headers = await getAuthHeaders(
      config({ idToken: "my-token", iapAudience: "https://aud.example.com" }),
    );
    assert.deepEqual(headers, { Authorization: "Bearer my-token" });
  });

  it("どちらも無ければヘッダーなし (ローカル開発用)", async () => {
    const headers = await getAuthHeaders(config());
    assert.deepEqual(headers, {});
  });
});

describe("uploadPage", () => {
  it("POST /api/pages に JSON を送り、結果を返す", async () => {
    nextResponse = {
      status: 201,
      body: {
        slug: "weekly-report",
        url: `${baseUrl}/p/weekly-report`,
        title: "週報",
      },
    };
    requests.length = 0;

    const result = await uploadPage(config({ idToken: "tok" }), {
      title: "週報",
      html: "<h1>週報</h1>",
      slug: "weekly-report",
    });

    assert.equal(requests.length, 1);
    const req = requests[0];
    assert.equal(req.method, "POST");
    assert.equal(req.url, "/api/pages");
    assert.equal(req.headers["content-type"], "application/json");
    assert.equal(req.headers["authorization"], "Bearer tok");
    assert.deepEqual(JSON.parse(req.body), {
      title: "週報",
      html: "<h1>週報</h1>",
      slug: "weekly-report",
    });

    assert.equal(result.slug, "weekly-report");
    assert.equal(result.url, `${baseUrl}/p/weekly-report`);
    assert.equal(result.title, "週報");
  });

  it("slug 省略時はリクエストボディに slug を含めない", async () => {
    nextResponse = {
      status: 201,
      body: { slug: "auto-123", url: `${baseUrl}/p/auto-123`, title: "t" },
    };
    requests.length = 0;

    await uploadPage(config(), { title: "t", html: "<p>x</p>" });

    const body = JSON.parse(requests[0].body);
    assert.deepEqual(body, { title: "t", html: "<p>x</p>" });
    assert.ok(!("slug" in body));
    // 認証なしのローカル開発モードでは Authorization ヘッダーを送らない
    assert.equal(requests[0].headers["authorization"], undefined);
  });

  it("エラーレスポンス (非2xx) で throw する", async () => {
    nextResponse = { status: 401, body: { error: "unauthorized" } };
    await assert.rejects(
      uploadPage(config(), { title: "t", html: "<p>x</p>" }),
      /HTTP 401/,
    );
  });

  it("url/slug を含まない不正な応答で throw する", async () => {
    nextResponse = { status: 201, body: { message: "ok?" } };
    await assert.rejects(
      uploadPage(config(), { title: "t", html: "<p>x</p>" }),
      /応答が不正/,
    );
  });
});

describe("listPages", () => {
  const samplePages: PageInfo[] = [
    {
      slug: "a",
      title: "ページA",
      uploader: "alice@example.com",
      updatedAt: "2026-07-25T10:00:00Z",
      url: "https://pon.example.com/p/a",
    },
    {
      slug: "b",
      title: "ページB",
      uploader: "bob@example.com",
      updatedAt: "2026-07-24T09:00:00Z",
      url: "https://pon.example.com/p/b",
    },
  ];

  it("GET /api/pages を呼び、pages 配列を返す", async () => {
    nextResponse = { status: 200, body: { pages: samplePages } };
    requests.length = 0;

    const pages = await listPages(config({ idToken: "tok" }));

    assert.equal(requests.length, 1);
    assert.equal(requests[0].method, "GET");
    assert.equal(requests[0].url, "/api/pages");
    assert.equal(requests[0].headers["authorization"], "Bearer tok");
    assert.equal(pages.length, 2);
    assert.equal(pages[0].slug, "a");
    assert.equal(pages[1].uploader, "bob@example.com");
  });

  it("limit で件数を絞れる", async () => {
    nextResponse = { status: 200, body: { pages: samplePages } };
    const pages = await listPages(config(), 1);
    assert.equal(pages.length, 1);
    assert.equal(pages[0].slug, "a");
  });

  it("pages が無い応答は空配列扱い", async () => {
    nextResponse = { status: 200, body: {} };
    const pages = await listPages(config());
    assert.deepEqual(pages, []);
  });

  it("エラーレスポンスで throw する", async () => {
    nextResponse = { status: 500, body: { error: "boom" } };
    await assert.rejects(listPages(config()), /HTTP 500/);
  });
});

describe("フォーマッタ", () => {
  it("formatUploadResult は「ぽん🫳 <url> に置きました」を含む", () => {
    const text = formatUploadResult({
      slug: "s",
      url: "https://pon.example.com/p/s",
      title: "タイトル",
    });
    assert.match(text, /^ぽん🫳 https:\/\/pon\.example\.com\/p\/s に置きました/);
    assert.match(text, /タイトル/);
    assert.match(text, /slug: s/);
  });

  it("formatPageList は各ページのタイトルとURLを含む", () => {
    const text = formatPageList([
      {
        slug: "a",
        title: "ページA",
        uploader: "alice@example.com",
        updatedAt: "2026-07-25T10:00:00Z",
        url: "https://pon.example.com/p/a",
      },
    ]);
    assert.match(text, /1件/);
    assert.match(text, /ページA/);
    assert.match(text, /https:\/\/pon\.example\.com\/p\/a/);
    assert.match(text, /alice@example\.com/);
  });

  it("formatPageList は空一覧に案内を返す", () => {
    assert.match(formatPageList([]), /まだページがありません/);
  });
});
