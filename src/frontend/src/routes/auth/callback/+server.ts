import { computeExpiresAt, getOAuthConfig } from "$lib/server/oauth";
import { getRedis, SessionJson } from "$lib/server/redis";
import { error, redirect } from "@sveltejs/kit";
import { authorizationCodeGrant } from "openid-client";

export async function GET({ url, cookies }) {
    const config = await getOAuthConfig();

    const storedVerifier = cookies.get("oauth_verifier");
    if (!storedVerifier) {
        throw error(400, "OAuth session cookies missing (verifier)");
    }

    const storedState = cookies.get("oauth_state");
    if (!storedState) {
        throw error(400, "OAuth session cookies missing (state)");
    }

    let tokenSet;
    try {
        tokenSet = await authorizationCodeGrant(config, url, {
            pkceCodeVerifier: storedVerifier,
            expectedState: storedState
        });
    } catch (e) {
        console.error("OAuth Exchange Failed:", e);
        throw error(400, "OAuth Grant failed");
    }

    const { access_token, refresh_token, id_token } = tokenSet;

    if (!access_token) throw error(500, "Provider did not return an access token");
    if (!id_token) throw error(500, "Provider did not return an id token");

    const sessionId = crypto.randomUUID();
    const expiresAt = computeExpiresAt(tokenSet.expiresIn());

    const redis = await getRedis();
    await redis.set(
        `session:${sessionId}`,
        SessionJson.encode({
            accessToken: access_token,
            refreshToken: refresh_token ?? undefined,
            idToken: id_token,
            expiresAt
        }),
        { expiration: { type: "EX", value: 60 * 60 * 24 * 30 } }
    );

    const targetUrl = cookies.get("oauth_target_url") ?? "/";

    cookies.delete("oauth_target_url", { path: "/" });
    cookies.delete("oauth_verifier", { path: "/" });
    cookies.delete("oauth_state", { path: "/" });

    cookies.set("session_id", sessionId, {
        path: "/",
        httpOnly: true,
        secure: import.meta.env.PROD,
        maxAge: 60 * 60 * 24 * 30
    });

    throw redirect(302, targetUrl);
}
