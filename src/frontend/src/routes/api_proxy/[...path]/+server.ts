import { env } from "$env/dynamic/private";

export const fallback = async ({ request, params, url, locals, fetch }) => {
    const target = new URL(
        `${env.BACKEND_URL as any}/api/vehicle_manager/${locals.user.tenant_id}/${params.path}`
    );
    target.search = url.search;

    // console.log(`[PROXY TARGET] ${target.toString()}`); // TRACE 1: Verify URL/IDs

    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.delete("connection");
    headers.delete("content-encoding");
    headers.delete("content-length");
    headers.set("authorization", `Bearer ${locals.user.accessToken}`);
    headers.set("X-Fucking-Ugly-Hack", `Bearer ${locals.user.accessToken}`);

    const hasBody = request.method !== "GET" && request.method !== "HEAD";
    let bodyPayload = undefined;

    // TRACE 2: Buffer and log the outgoing body
    // If this fails, the request stream is malformed
    if (hasBody) {
        try {
            bodyPayload = await request.text();
            // console.log(`[PROXY PAYLOAD]`, bodyPayload);
        } catch (e) {
            // console.error(`[PROXY BODY ERROR] Could not read request body`, e);
            throw e;
        }
    }

    try {
        const ret = await fetch(target, {
            method: request.method,
            headers,
            body: bodyPayload
            // duplex not needed for string bodies, removed for stability during debug
        });

        // TRACE 3: Catch upstream errors
        if (!ret.ok) {
            const errText = await ret.text();
            // console.error(`[UPSTREAM ERROR] ${ret.status} from Backend:`, errText);

            // Return the detailed error to the client instead of a generic 500
            return new Response(errText, {
                status: ret.status,
                headers: ret.headers
            });
        }

        return ret;
    } catch (e) {
        // console.error(`[FETCH FAILURE] Network/DNS error:`, e);
        return new Response(JSON.stringify({ error: (e as any).message }), { status: 500 });
    }
};

export const trailingSlash = "ignore";
