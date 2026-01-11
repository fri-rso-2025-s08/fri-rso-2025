import { VehicleClient } from "$lib/api_client";

export const load = async ({ fetch }) => {
    const client = new VehicleClient(fetch);
    // 1. Fetch list of active vehicle UUIDs
    const vehicleIds = await client.listVehicles(true);

    // 2. Fetch full details for each UUID in parallel
    // (In a production app, consider an endpoint that returns the full list to avoid N+1 fetches)
    const vehicles = await Promise.all(vehicleIds.map((id) => client.getVehicle(id)));

    return {
        vehicles
    };
};
