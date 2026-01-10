import { Session } from "$lib/server/redis";
import { describe, expect, it } from "vitest";

describe("redis schema test", () => {
    it("works", () => {
        const result = Session.safeParse({
            accessToken: "1",
            // refreshToken: 2,
            idToken: "3",
            expiresAt: "2025-01-01T00:00:00Z"
        });
        expect(result.success).toBe(true);
    });
});
