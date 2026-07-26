#!/usr/bin/env node
/**
 * pon-mcp — 社内HTMLホスティング環境「ぽん」用 MCP サーバー (stdio)。
 *
 * ツール:
 *   - pon_upload: HTML をぽんにアップロードして社内URLを得る
 *   - pon_list:   ぽんに置かれているページの一覧を得る
 */
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import {
  formatPageList,
  formatUploadResult,
  listPages,
  resolveConfig,
  uploadPage,
} from "./api.js";

const server = new McpServer({
  name: "pon-mcp",
  version: "0.1.0",
});

function errorResult(err: unknown) {
  const message = err instanceof Error ? err.message : String(err);
  return {
    content: [{ type: "text" as const, text: `エラー: ${message}` }],
    isError: true,
  };
}

server.registerTool(
  "pon_upload",
  {
    title: "ぽんにアップロード",
    description:
      "HTMLを社内HTMLホスティング環境「ぽん」にアップロードして社内URLを発行します。" +
      "html_file (ローカルのHTMLファイルパス) か html (HTML文字列) のどちらか一方を必ず指定してください。" +
      "slug を既存ページのものにすると上書き更新になります。",
    inputSchema: {
      title: z.string().describe("ページのタイトル"),
      html_file: z
        .string()
        .optional()
        .describe("アップロードするローカルHTMLファイルのパス (html と排他)"),
      html: z
        .string()
        .optional()
        .describe("アップロードするHTML文字列 (html_file と排他)"),
      slug: z
        .string()
        .optional()
        .describe(
          "URLのslug (省略時はサーバーが自動生成。既存slugを指定すると上書き更新)",
        ),
    },
  },
  async ({ title, html_file, html, slug }) => {
    try {
      if (!html_file && !html) {
        throw new Error("html_file か html のどちらか一方を指定してください");
      }
      if (html_file && html) {
        throw new Error(
          "html_file と html は同時に指定できません。どちらか一方にしてください",
        );
      }
      const htmlContent = html_file
        ? await readFile(resolve(html_file), "utf-8")
        : html!;
      const config = resolveConfig();
      const result = await uploadPage(config, { title, html: htmlContent, slug });
      return {
        content: [{ type: "text" as const, text: formatUploadResult(result) }],
      };
    } catch (err) {
      return errorResult(err);
    }
  },
);

server.registerTool(
  "pon_list",
  {
    title: "ぽんのページ一覧",
    description:
      "社内HTMLホスティング環境「ぽん」に置かれているページの一覧 (タイトル・URL・更新者・更新日時) を取得します。",
    inputSchema: {
      limit: z
        .number()
        .int()
        .positive()
        .optional()
        .describe("取得する最大件数 (省略時は全件)"),
    },
  },
  async ({ limit }) => {
    try {
      const config = resolveConfig();
      const pages = await listPages(config, limit);
      return {
        content: [{ type: "text" as const, text: formatPageList(pages) }],
      };
    } catch (err) {
      return errorResult(err);
    }
  },
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("pon-mcp server running on stdio");
}

main().catch((err) => {
  console.error("pon-mcp fatal error:", err);
  process.exit(1);
});
