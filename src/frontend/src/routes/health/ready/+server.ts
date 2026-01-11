// src/routes/health/ready/+server.ts
import { getRedis } from "$lib/server/redis"; // Import your singleton client
import { json } from "@sveltejs/kit";

export async function GET() {
    try {
        const redis = await getRedis();
        await redis.ping();

        return json({ status: "ready" });
    } catch (error) {
        console.error("Readiness probe failed:", error);
        return json({ status: "redis unavailable" }, { status: 503 });
    }
}
