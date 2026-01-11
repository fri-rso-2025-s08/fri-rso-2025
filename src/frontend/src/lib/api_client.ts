import { z } from "zod";

// --- Schemas & Types ---

const UuidSchema = z.string().uuid();
const DateTimeSchema = z.coerce.date();

const VehicleConfigTestSchema = z.object({
    lat: z.number(),
    lon: z.number(),
    std: z.number()
});

const VehicleBaseSchema = z.object({
    name: z.string().max(64),
    vtype: z.literal("test"),
    vconfig: VehicleConfigTestSchema
});

export const VehicleCreateSchema = VehicleBaseSchema;
export const VehicleUpdateSchema = z.object({
    name: z.string().max(64).nullable().optional(),
    immobilized: z.boolean().nullable().optional()
});

export const VehicleReadSchema = VehicleBaseSchema.extend({
    id: UuidSchema,
    active: z.boolean(),
    immobilized: z.boolean(),
    lat: z.number().nullable(),
    lon: z.number().nullable()
});

const GeofenceBaseSchema = z.object({
    name: z.string().max(64),
    data: z.record(z.string(), z.any()),
    immobilize_enter: z.boolean(),
    immobilize_leave: z.boolean()
});

export const GeofenceCreateSchema = GeofenceBaseSchema;
export const GeofenceUpdateSchema = z.object({
    name: z.string().max(64).nullable().optional(),
    immobilize_enter: z.boolean().nullable().optional(),
    immobilize_leave: z.boolean().nullable().optional()
});

export const GeofenceReadSchema = GeofenceBaseSchema.extend({
    id: UuidSchema,
    active: z.boolean()
});

const BaseEventReadSchema = z.object({
    ts: DateTimeSchema
});

export const PosReadSchema = BaseEventReadSchema.extend({
    lat: z.number(),
    lon: z.number()
});

const BaseUserEventReadSchema = BaseEventReadSchema.extend({
    user_id: z.string()
});

const CreatedEventReadSchema = BaseUserEventReadSchema.extend({
    type: z.literal("created")
});

const ModifiedEventReadSchema = BaseUserEventReadSchema.extend({
    type: z.literal("modified")
});

const DeletedEventReadSchema = BaseUserEventReadSchema.extend({
    type: z.literal("deleted")
});

const ImmobilizedEventReadSchema = BaseEventReadSchema.extend({
    type: z.literal("immobilized"),
    vehicle_id: UuidSchema.nullable(),
    user_id: z.string().nullable(),
    geofence_id: UuidSchema.nullable(),
    immobilized: z.boolean()
});

const GeofenceEventReadSchema = BaseEventReadSchema.extend({
    type: z.literal("geofence"),
    geofence_id: UuidSchema.nullable(),
    entered: z.boolean()
});

export const EventTypesSchema = z.discriminatedUnion("type", [
    CreatedEventReadSchema,
    ModifiedEventReadSchema,
    DeletedEventReadSchema,
    ImmobilizedEventReadSchema,
    GeofenceEventReadSchema
]);

export type VehicleCreate = z.infer<typeof VehicleCreateSchema>;
export type VehicleUpdate = z.infer<typeof VehicleUpdateSchema>;
export type VehicleRead = z.infer<typeof VehicleReadSchema>;
export type GeofenceCreate = z.infer<typeof GeofenceCreateSchema>;
export type GeofenceUpdate = z.infer<typeof GeofenceUpdateSchema>;
export type GeofenceRead = z.infer<typeof GeofenceReadSchema>;
export type PosRead = z.infer<typeof PosReadSchema>;
export type VehicleEvent = z.infer<typeof EventTypesSchema>;

type FetchImpl = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

// --- Client Class ---

export class VehicleClient {
    private fetch: FetchImpl;
    private baseUrl: string;

    constructor(customFetch?: FetchImpl, baseUrl: string = "/api_proxy") {
        // In SvelteKit load functions, pass `event.fetch`.
        // In browser, pass nothing to use global `fetch`.
        this.fetch = customFetch || ((...args) => fetch(...args));
        this.baseUrl = baseUrl.replace(/\/$/, ""); // Strip trailing slash
    }

    private async request<T>(
        method: string,
        path: string,
        schema: z.ZodType<T>,
        body?: unknown,
        params?: Record<string, any>
    ): Promise<T> {
        const q = new URLSearchParams();

        if (params) {
            Object.entries(params).forEach(([key, value]) => {
                if (value !== undefined && value !== null) {
                    if (value instanceof Date) {
                        q.append(key, value.toISOString());
                    } else {
                        q.append(key, String(value));
                    }
                }
            });
        }

        const queryString = q.toString();
        const url = `${this.baseUrl}${path}${queryString ? `?${queryString}` : ""}`;

        const headers: HeadersInit = {
            "Content-Type": "application/json"
        };

        const res = await this.fetch(url, {
            method,
            headers,
            body: body ? JSON.stringify(body) : undefined
        });

        if (!res.ok) {
            console.log(res);
            throw new Error(`API Error ${res.status}: ${await res.text()}`);
        }

        const text = await res.text();
        if (!text || text === "null") {
            // @ts-ignore
            return null;
        }

        const json = JSON.parse(text);
        return schema.parse(json);
    }

    // Vehicles
    async listVehicles(active: boolean = true) {
        return this.request("GET", "/vehicles", z.array(UuidSchema), undefined, { active });
    }

    async getVehicle(id: string) {
        return this.request("GET", `/vehicles/${id}`, VehicleReadSchema);
    }

    async createVehicle(payload: VehicleCreate) {
        return this.request("POST", "/vehicles", VehicleReadSchema, payload);
    }

    async updateVehicle(id: string, payload: VehicleUpdate) {
        return this.request("PUT", `/vehicles/${id}`, z.null(), payload);
    }

    async deleteVehicle(id: string) {
        return this.request("DELETE", `/vehicles/${id}`, z.null());
    }

    // Geofences
    async listGeofences(active: boolean = true) {
        return this.request("GET", "/geofences", z.array(UuidSchema), undefined, { active });
    }

    async getGeofence(id: string) {
        return this.request("GET", `/geofences/${id}`, GeofenceReadSchema);
    }

    async createGeofence(payload: GeofenceCreate) {
        return this.request("POST", "/geofences", GeofenceReadSchema, payload);
    }

    async updateGeofence(id: string, payload: GeofenceUpdate) {
        return this.request("PUT", `/geofences/${id}`, z.null(), payload);
    }

    async deleteGeofence(id: string) {
        return this.request("DELETE", `/geofences/${id}`, z.null());
    }

    // Associations
    async listVehiclesInGeofence(geofenceId: string) {
        return this.request("GET", `/geofence_vehicles/${geofenceId}`, z.array(UuidSchema));
    }

    async listGeofencesForVehicle(vehicleId: string) {
        return this.request("GET", `/vehicle_geofences/${vehicleId}`, z.array(UuidSchema));
    }

    async assignVehicleToGeofence(geofenceId: string, vehicleId: string) {
        return this.request("POST", `/geofence_vehicles/${geofenceId}/${vehicleId}`, z.null());
    }

    async removeVehicleFromGeofence(geofenceId: string, vehicleId: string) {
        return this.request("DELETE", `/geofence_vehicles/${geofenceId}/${vehicleId}`, z.null());
    }

    // Time Series / Events
    async getVehiclePositions(
        id: string,
        filters?: { start_date?: Date; end_date?: Date; limit?: number }
    ) {
        return this.request(
            "GET",
            `/vehicle_positions/${id}`,
            z.array(PosReadSchema),
            undefined,
            filters
        );
    }

    async getVehicleEvents(
        id: string,
        filters?: { start_date?: Date; end_date?: Date; limit?: number }
    ) {
        return this.request(
            "GET",
            `/vehicle_events/${id}`,
            z.array(EventTypesSchema),
            undefined,
            filters
        );
    }

    async getGeofenceEvents(
        id: string,
        filters?: { start_date?: Date; end_date?: Date; limit?: number }
    ) {
        return this.request(
            "GET",
            `/geofence_events/${id}`,
            z.array(EventTypesSchema),
            undefined,
            filters
        );
    }
}
