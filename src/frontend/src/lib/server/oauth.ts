import { env } from "$env/dynamic/private";
import { discovery, type Configuration } from "openid-client";

const ISSUER_URL = env.OAUTH_ISSUER_URL as any;
const CLIENT_ID = env.OAUTH_CLIENT_ID as any;
const CLIENT_SECRET = env.OAUTH_CLIENT_SECRET as any;
export const OAUTH_REDIRECT_URI = `${env.OAUTH_ORIGIN as any}/auth/callback`;

let oAuthConfig: Configuration | null = null;

export async function getOAuthConfig() {
    if (oAuthConfig == null) {
        oAuthConfig = await discovery(new URL(ISSUER_URL), CLIENT_ID, CLIENT_SECRET);
    }
    return oAuthConfig;
}

export function computeExpiresAt(src: number = 60) {
    return new Date(Date.now() + (src / 2) * 1000);
}
