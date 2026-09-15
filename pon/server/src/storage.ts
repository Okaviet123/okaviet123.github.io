import { promises as fs } from "node:fs";
import path from "node:path";

/** ページオブジェクトのカスタムメタデータ */
export interface PageMetadata {
  title?: string;
  uploader?: string;
}

/** 保存されたオブジェクトの取得結果 */
export interface StoredObject {
  body: Buffer;
  metadata: PageMetadata;
}

/** 一覧用のページ情報 */
export interface PageEntry {
  slug: string;
  title: string;
  uploader: string;
  updatedAt: string; // ISO 8601
}

/**
 * ストレージ抽象化レイヤー。
 * GCS 実装 (GcsStorage) とローカルFS実装 (LocalStorage) の2つを提供する。
 * オブジェクトキーは "pages/<slug>/index.html" のような相対パス。
 */
export interface Storage {
  /** オブジェクトを保存する(既存キーは上書き) */
  put(key: string, body: Buffer, metadata: PageMetadata): Promise<void>;
  /** オブジェクトを取得する。存在しなければ null */
  get(key: string): Promise<StoredObject | null>;
  /** pages/<slug>/index.html を列挙してページ一覧を返す(更新日時降順) */
  listPages(): Promise<PageEntry[]>;
}

const PAGES_PREFIX = "pages/";
const INDEX_SUFFIX = "/index.html";

/** "pages/<slug>/index.html" から slug を取り出す。該当しなければ null */
function slugFromKey(key: string): string | null {
  if (!key.startsWith(PAGES_PREFIX) || !key.endsWith(INDEX_SUFFIX)) return null;
  const slug = key.slice(PAGES_PREFIX.length, key.length - INDEX_SUFFIX.length);
  if (!slug || slug.includes("/")) return null;
  return slug;
}

/* ------------------------------------------------------------------ */
/* Google Cloud Storage 実装                                           */
/* ------------------------------------------------------------------ */

export class GcsStorage implements Storage {
  private bucketName: string;
  // @google-cloud/storage は必要になるまで遅延ロードする(ローカル開発時に不要)
  private bucketPromise: Promise<import("@google-cloud/storage").Bucket> | null =
    null;

  constructor(bucketName: string) {
    this.bucketName = bucketName;
  }

  private async bucket() {
    if (!this.bucketPromise) {
      this.bucketPromise = import("@google-cloud/storage").then(
        ({ Storage: GcsClient }) => new GcsClient().bucket(this.bucketName),
      );
    }
    return this.bucketPromise;
  }

  async put(key: string, body: Buffer, metadata: PageMetadata): Promise<void> {
    const bucket = await this.bucket();
    const file = bucket.file(key);
    await file.save(body, {
      resumable: false,
      contentType: contentTypeFor(key),
      metadata: {
        metadata: {
          title: metadata.title ?? "",
          uploader: metadata.uploader ?? "",
        },
      },
    });
  }

  async get(key: string): Promise<StoredObject | null> {
    const bucket = await this.bucket();
    const file = bucket.file(key);
    try {
      const [body] = await file.download();
      const [meta] = await file.getMetadata();
      const custom = (meta.metadata ?? {}) as Record<string, unknown>;
      return {
        body,
        metadata: {
          title: typeof custom.title === "string" ? custom.title : undefined,
          uploader:
            typeof custom.uploader === "string" ? custom.uploader : undefined,
        },
      };
    } catch (err: unknown) {
      if ((err as { code?: number }).code === 404) return null;
      throw err;
    }
  }

  async listPages(): Promise<PageEntry[]> {
    const bucket = await this.bucket();
    const [files] = await bucket.getFiles({ prefix: PAGES_PREFIX });
    const entries: PageEntry[] = [];
    for (const file of files) {
      const slug = slugFromKey(file.name);
      if (!slug) continue;
      const custom = (file.metadata.metadata ?? {}) as Record<string, unknown>;
      entries.push({
        slug,
        title:
          typeof custom.title === "string" && custom.title !== ""
            ? custom.title
            : slug,
        uploader:
          typeof custom.uploader === "string" && custom.uploader !== ""
            ? custom.uploader
            : "anonymous",
        updatedAt: new Date(
          (file.metadata.updated as string | undefined) ?? Date.now(),
        ).toISOString(),
      });
    }
    entries.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    return entries;
  }
}

/* ------------------------------------------------------------------ */
/* ローカルファイルシステム実装(開発・テスト用)                       */
/* ------------------------------------------------------------------ */

export class LocalStorage implements Storage {
  constructor(private baseDir: string) {}

  /** ベースディレクトリの外に出ないよう解決したパスを返す */
  private resolve(key: string): string {
    const abs = path.resolve(this.baseDir, key);
    const base = path.resolve(this.baseDir);
    if (abs !== base && !abs.startsWith(base + path.sep)) {
      throw new Error(`invalid key: ${key}`);
    }
    return abs;
  }

  private metaPath(key: string): string {
    return this.resolve(key) + ".meta.json";
  }

  async put(key: string, body: Buffer, metadata: PageMetadata): Promise<void> {
    const filePath = this.resolve(key);
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    await fs.writeFile(filePath, body);
    await fs.writeFile(
      this.metaPath(key),
      JSON.stringify({
        title: metadata.title ?? "",
        uploader: metadata.uploader ?? "",
      }),
    );
  }

  async get(key: string): Promise<StoredObject | null> {
    let body: Buffer;
    try {
      body = await fs.readFile(this.resolve(key));
    } catch (err: unknown) {
      if ((err as { code?: string }).code === "ENOENT") return null;
      throw err;
    }
    let metadata: PageMetadata = {};
    try {
      const raw = await fs.readFile(this.metaPath(key), "utf8");
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      metadata = {
        title: typeof parsed.title === "string" ? parsed.title : undefined,
        uploader:
          typeof parsed.uploader === "string" ? parsed.uploader : undefined,
      };
    } catch {
      /* メタデータが無くても本体は返す */
    }
    return { body, metadata };
  }

  async listPages(): Promise<PageEntry[]> {
    const pagesDir = path.join(this.baseDir, "pages");
    let dirents;
    try {
      dirents = await fs.readdir(pagesDir, { withFileTypes: true });
    } catch (err: unknown) {
      if ((err as { code?: string }).code === "ENOENT") return [];
      throw err;
    }
    const entries: PageEntry[] = [];
    for (const dirent of dirents) {
      if (!dirent.isDirectory()) continue;
      const slug = dirent.name;
      const key = `${PAGES_PREFIX}${slug}/index.html`;
      const filePath = path.join(pagesDir, slug, "index.html");
      let stat;
      try {
        stat = await fs.stat(filePath);
      } catch {
        continue; // index.html が無いディレクトリは対象外
      }
      const stored = await this.get(key);
      entries.push({
        slug,
        title: stored?.metadata.title || slug,
        uploader: stored?.metadata.uploader || "anonymous",
        updatedAt: stat.mtime.toISOString(),
      });
    }
    entries.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    return entries;
  }
}

/* ------------------------------------------------------------------ */
/* Content-Type 判定                                                   */
/* ------------------------------------------------------------------ */

const MIME_TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".htm": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".xml": "application/xml; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".avif": "image/avif",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".otf": "font/otf",
  ".pdf": "application/pdf",
  ".mp4": "video/mp4",
  ".webm": "video/webm",
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
  ".wasm": "application/wasm",
  ".map": "application/json; charset=utf-8",
};

export function contentTypeFor(key: string): string {
  const ext = path.extname(key).toLowerCase();
  return MIME_TYPES[ext] ?? "application/octet-stream";
}

/* ------------------------------------------------------------------ */
/* ファクトリ                                                          */
/* ------------------------------------------------------------------ */

export function createStorageFromEnv(env: NodeJS.ProcessEnv): Storage {
  const localDir = env.PON_LOCAL_DIR;
  if (localDir) {
    return new LocalStorage(localDir);
  }
  const bucket = env.PON_BUCKET;
  if (!bucket) {
    throw new Error(
      "環境変数 PON_BUCKET(GCSバケット名)または PON_LOCAL_DIR(ローカル保存先)を設定してください",
    );
  }
  return new GcsStorage(bucket);
}
