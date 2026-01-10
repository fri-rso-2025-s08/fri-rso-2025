import { env } from "$env/dynamic/private";
import { createClient } from "redis";
import z from "zod";

let redisCached:
    | (ReturnType<ReturnType<typeof createClient>["connect"]> extends Promise<infer T> ? T : never)
    | null = null;

export async function getRedis() {
    if (redisCached == null) {
        if (!env.REDIS_URL) throw new Error("REDIS_URL is not set");
        const x = await createClient({ url: env.REDIS_URL }).connect();
        redisCached = x;
    }
    return redisCached;
}

async function gracefulShutdown() {
    if (redisCached != null) {
        await redisCached.quit();
    }
}

process.on("SIGINT", gracefulShutdown);
process.on("SIGTERM", gracefulShutdown);

export const Session = z.object({
    accessToken: z.string(),
    refreshToken: z.string().optional(),
    idToken: z.string(),
    expiresAt: z.coerce.date()
});

const jsonCodec = <T extends z.core.$ZodType>(schema: T) =>
    z.codec(z.string(), schema, {
        decode: (jsonString, ctx) => {
            try {
                return JSON.parse(jsonString);
            } catch (err: any) {
                ctx.issues.push({
                    code: "invalid_format",
                    format: "json",
                    input: jsonString,
                    message: err.message
                });
                return z.NEVER;
            }
        },
        encode: (value) => JSON.stringify(value)
    });

export const SessionJson = jsonCodec(Session);
