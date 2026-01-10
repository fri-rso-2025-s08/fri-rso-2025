import { env } from "$env/dynamic/private";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

let dbCached: ReturnType<typeof drizzle> | null = null;

export function getDb() {
    if (dbCached != null) return dbCached;
    if (!env.DATABASE_URL) throw new Error("DATABASE_URL is not set!!");
    const client = postgres(env.DATABASE_URL);
    dbCached = drizzle(client, { schema });
    return dbCached;
}
