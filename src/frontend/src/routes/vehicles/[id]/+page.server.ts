import { VehicleClient } from "$lib/api_client";
import { error } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ params, fetch }) => {
    // Pass the standard fetch to the client to ensure server-side requests work
    const client = new VehicleClient(fetch);
    const id = params.id;

    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
    const filters = { start_date: oneHourAgo, limit: 1000 };

    try {
        const [vehicle, events, positions] = await Promise.all([
            client.getVehicle(id),
            client.getVehicleEvents(id, filters),
            client.getVehiclePositions(id, filters)
        ]);

        return {
            vehicle,
            // Sort server-side to reduce client processing
            events: events.sort((a, b) => b.ts.getTime() - a.ts.getTime()),
            positions: positions.sort((a, b) => a.ts.getTime() - b.ts.getTime())
        };
    } catch (e) {
        console.error(`Error loading vehicle ${id}:`, e);
        error(404, "Vehicle not found");
    }
};
