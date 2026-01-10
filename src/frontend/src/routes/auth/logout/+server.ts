import { getOAuthConfig } from "$lib/server/oauth.js";
import { redirect } from "@sveltejs/kit";
import { buildEndSessionUrl } from "openid-client";

export async function GET({ cookies, locals }) {
    cookies.delete("session_id", { path: "/" });
    throw redirect(
        302,
        buildEndSessionUrl(await getOAuthConfig(), { id_token_hint: locals.user.idToken })
    );
}
