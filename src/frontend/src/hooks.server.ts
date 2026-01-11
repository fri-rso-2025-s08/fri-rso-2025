import { computeExpiresAt, getOAuthConfig, OAUTH_REDIRECT_URI } from "$lib/server/oauth";
import { getRedis, SessionJson } from "$lib/server/redis";
import { redirect, type RequestEvent } from "@sveltejs/kit";
import { decodeJwt } from "jose";
import {
    buildAuthorizationUrl,
    calculatePKCECodeChallenge,
    randomPKCECodeVerifier,
    randomState,
    refreshTokenGrant
} from "openid-client";

async function startAuthFlow(event: RequestEvent) {
    const config = await getOAuthConfig();

    const code_verifier = randomPKCECodeVerifier();
    const code_challenge = await calculatePKCECodeChallenge(code_verifier);
    const state = randomState();

    const cookieOpts = {
        path: "/",
        httpOnly: true,
        sameSite: "lax",
        secure: import.meta.env.PROD,
        maxAge: 600
    } as const;

    event.cookies.set("oauth_target_url", event.url.pathname + event.url.search, cookieOpts);
    event.cookies.set("oauth_verifier", code_verifier, cookieOpts);
    event.cookies.set("oauth_state", state, cookieOpts);

    const url = buildAuthorizationUrl(config, {
        redirect_uri: OAUTH_REDIRECT_URI,
        scope: "openid profile email offline_access tenant",
        prompt: "select_account",
        code_challenge,
        code_challenge_method: "S256",
        state
    });

    return redirect(302, url.href);
}

export const handle = async ({ event, resolve }) => {
    if (event.url.pathname === "/auth/callback") {
        return resolve(event);
    }

    const sessionId = event.cookies.get("session_id");

    if (!sessionId) {
        throw await startAuthFlow(event);
    }

    const redis = await getRedis();
    const rawSession = SessionJson.safeParse(await redis.get(`session:${sessionId}`));

    if (!rawSession.success) {
        event.cookies.delete("session_id", { path: "/" });
        throw await startAuthFlow(event);
    }

    const session = rawSession.data;

    if (new Date() > session.expiresAt) {
        if (!session.refreshToken) {
            await redis.del(`session:${sessionId}`);
            event.cookies.delete("session_id", { path: "/" });
            throw await startAuthFlow(event);
        }

        try {
            const config = await getOAuthConfig();
            const response = await refreshTokenGrant(config, session.refreshToken);

            await redis.set(
                `session:${sessionId}`,
                SessionJson.encode({
                    accessToken: response.access_token,
                    refreshToken: response.refresh_token ?? session.refreshToken,
                    idToken: response.id_token ?? session.idToken,
                    expiresAt: computeExpiresAt(response.expiresIn())
                }),
                { expiration: { type: "EX", value: 60 * 60 * 24 * 30 } }
            );
        } catch (error) {
            await redis.del(`session:${sessionId}`);
            event.cookies.delete("session_id", { path: "/" });
            throw await startAuthFlow(event);
        }
    }

    const claims = decodeJwt(session.idToken);
    event.locals.user = {
        accessToken: session.accessToken,
        idToken: session.idToken,
        tenant_id: claims.tenant_id as string
    };

    return resolve(event);
};
