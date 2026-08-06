/**
 * ぽん (pon) サーバーの API クライアント。
 *
 * MCP プロトコル層から分離してあり、node:test で単体テスト可能。
 */

export interface PonConfig {
  /** 例: https://pon.example.com (末尾スラッシュなしに正規化される) */
  baseUrl: string;
  /** PON_ID_TOKEN — 明示的に指定された IAP 用 ID トークン */
  idToken?: string;
  /** PON_IAP_AUDIENCE — google-auth-library で ID トークンを取得する audience */
  iapAudience?: string;
}

export interface UploadRequest {
  title: string;
  html: string;
  slug?: string;
}

export interface UploadResult {
  slug: string;
  url: string;
  title: string;
}

export interface PageInfo {
  slug: string;
  title: string;
  uploader: string;
  updatedAt: string;
  url: string;
}

/** 環境変数から設定を解決する。PON_BASE_URL が無ければ throw。 */
export function resolveConfig(
  env: Record<string, string | undefined> = process.env,
): PonConfig {
  const baseUrl = env.PON_BASE_URL;
  if (!baseUrl) {
    throw new Error(
      "環境変数 PON_BASE_URL が設定されていません (例: https://pon.example.com)",
    );
  }
  return {
    baseUrl: baseUrl.replace(/\/+$/, ""),
    idToken: env.PON_ID_TOKEN || undefined,
    iapAudience: env.PON_IAP_AUDIENCE || undefined,
  };
}

/**
 * IAP 越えのための Authorization ヘッダーを決定する。
 * 優先順: PON_ID_TOKEN → PON_IAP_AUDIENCE (ADC/サービスアカウント) → なし。
 */
export async function getAuthHeaders(
  config: PonConfig,
): Promise<Record<string, string>> {
  if (config.idToken) {
    return { Authorization: `Bearer ${config.idToken}` };
  }
  if (config.iapAudience) {
    // google-auth-library は必要になったときだけ読み込む
    // (ローカル開発では ADC が無くても他の機能が動くように)
    const { GoogleAuth } = await import("google-auth-library");
    const auth = new GoogleAuth();
    const client = await auth.getIdTokenClient(config.iapAudience);
    // getRequestHeaders はバージョンにより plain object / Headers のどちらかを返す
    const headers = (await client.getRequestHeaders()) as unknown;
    const authHeader =
      headers instanceof Headers
        ? headers.get("Authorization")
        : (headers as Record<string, string | undefined>)["Authorization"];
    if (!authHeader) {
      throw new Error(
        "google-auth-library から Authorization ヘッダーを取得できませんでした",
      );
    }
    return { Authorization: authHeader };
  }
  return {};
}

async function readErrorBody(res: Response): Promise<string> {
  try {
    const text = await res.text();
    return text.slice(0, 500);
  } catch {
    return "";
  }
}

/** POST /api/pages — HTML をアップロードして URL を得る。 */
export async function uploadPage(
  config: PonConfig,
  req: UploadRequest,
): Promise<UploadResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(await getAuthHeaders(config)),
  };
  const body: Record<string, string> = { title: req.title, html: req.html };
  if (req.slug) body.slug = req.slug;

  const res = await fetch(`${config.baseUrl}/api/pages`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(
      `アップロードに失敗しました: HTTP ${res.status} ${await readErrorBody(res)}`,
    );
  }
  const data = (await res.json()) as UploadResult;
  if (!data.url || !data.slug) {
    throw new Error(
      `サーバーの応答が不正です: ${JSON.stringify(data).slice(0, 500)}`,
    );
  }
  return data;
}

/** GET /api/pages — ページ一覧を取得する。 */
export async function listPages(
  config: PonConfig,
  limit?: number,
): Promise<PageInfo[]> {
  const headers = await getAuthHeaders(config);
  const res = await fetch(`${config.baseUrl}/api/pages`, { headers });
  if (!res.ok) {
    throw new Error(
      `一覧の取得に失敗しました: HTTP ${res.status} ${await readErrorBody(res)}`,
    );
  }
  const data = (await res.json()) as { pages?: PageInfo[] };
  const pages = Array.isArray(data.pages) ? data.pages : [];
  return typeof limit === "number" && limit > 0 ? pages.slice(0, limit) : pages;
}

/** pon_upload の結果テキストを組み立てる。 */
export function formatUploadResult(result: UploadResult): string {
  return `ぽん🫳 ${result.url} に置きました\n\nタイトル: ${result.title}\nslug: ${result.slug}\nURL: ${result.url}`;
}

/** pon_list の結果テキストを組み立てる。 */
export function formatPageList(pages: PageInfo[]): string {
  if (pages.length === 0) {
    return "まだページがありません。pon_upload で最初のページを置いてみましょう🫳";
  }
  const lines = pages.map(
    (p) =>
      `- ${p.title} (${p.slug})\n  ${p.url}\n  更新: ${p.updatedAt} / ${p.uploader}`,
  );
  return `ぽんに置かれているページ (${pages.length}件):\n\n${lines.join("\n")}`;
}
