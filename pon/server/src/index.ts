import { serve } from "@hono/node-server";
import { createApp } from "./routes.js";
import { createStorageFromEnv } from "./storage.js";

const storage = createStorageFromEnv(process.env);

const retentionDays = Number(process.env.PON_RETENTION_DAYS ?? "7");
const app = createApp(storage, {
  retentionDays: Number.isFinite(retentionDays) && retentionDays > 0 ? retentionDays : 7,
});

const port = Number(process.env.PORT ?? "8080");

serve({ fetch: app.fetch, port }, (info) => {
  console.log(`pon 🫳 server listening on http://localhost:${info.port}`);
  if (process.env.PON_LOCAL_DIR) {
    console.log(`storage: local filesystem (${process.env.PON_LOCAL_DIR})`);
  } else {
    console.log(`storage: GCS bucket "${process.env.PON_BUCKET}"`);
  }
});
