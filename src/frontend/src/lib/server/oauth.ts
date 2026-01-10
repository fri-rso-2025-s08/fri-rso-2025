import { env } from "$env/dynamic/private";
import { discovery, type Configuration } from "openid-client";

const ISSUER_URL = env.OAUTH_ISSUER_URL;
const CLIENT_ID = env.OAUTH_CLIENT_ID;
const CLIENT_SECRET = env.OAUTH_CLIENT_SECRET;
export const OAUTH_REDIRECT_URI = `${env.OAUTH_ORIGIN}/auth/callback`;

let oAuthConfig: Configuration | null = null;

export async function getOAuthConfig() {
    if (oAuthConfig == null) {
        oAuthConfig = await discovery(new URL(ISSUER_URL), CLIENT_ID, CLIENT_SECRET);
    }
    return oAuthConfig;
}
