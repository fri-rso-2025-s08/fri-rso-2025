<script lang="ts">
    import { goto, invalidateAll } from "$app/navigation";
    import { page } from "$app/state";
    import { VehicleClient } from "$lib/api_client";
    import { Check, Lock, Pencil, Trash2, Unlock, X } from "@lucide/svelte";
    import { onMount } from "svelte";
    import {
        DefaultMarker,
        GeoJSON,
        LineLayer,
        MapLibre,
        NavigationControl,
        Popup,
        type Map
    } from "svelte-maplibre";
    import type { PageData } from "./$types";

    let { data }: { data: PageData } = $props();

    // Client for mutations only (defaults to browser fetch)
    const client = new VehicleClient();
    const vehicleId = page.params.id!;

    // svelte-ignore state_referenced_locally
    const initialCenter: [number, number] =
        data.vehicle.lat && data.vehicle.lon
            ? [data.vehicle.lon, data.vehicle.lat]
            : [14.4496982, 46.0663294];

    let map: Map | undefined = $state();
    let isRenaming = $state(false);
    let renameValue = $state("");

    // Reactive derivations from server data
    let positions = $derived(data.positions);
    let events = $derived(data.events);
    let vehicle = $derived(data.vehicle);

    let traceData = $derived({
        type: "Feature",
        geometry: {
            type: "LineString",
            coordinates: positions.map((p) => [p.lon, p.lat])
        }
    });

    let lastPosition = $derived(positions.length > 0 ? positions[positions.length - 1] : null);

    onMount(() => {
        const interval = setInterval(() => {
            // Re-runs the load function in +page.server.ts
            invalidateAll();
        }, 1000);

        return () => clearInterval(interval);
    });

    async function handleDelete() {
        if (!confirm("Permanently delete this vehicle?")) return;
        try {
            await client.deleteVehicle(vehicleId);
            goto("/vehicles");
        } catch (e) {
            alert("Failed to delete vehicle");
        }
    }

    async function toggleImmobilization() {
        if (!vehicle) return;
        const newState = !vehicle.immobilized;
        // API call
        await client.updateVehicle(vehicleId, { immobilized: newState });
        // Trigger immediate refresh
        invalidateAll();
    }

    function startRename() {
        if (!vehicle) return;
        renameValue = vehicle.name;
        isRenaming = true;
    }

    async function saveRename() {
        if (!vehicle) return;
        await client.updateVehicle(vehicleId, { name: renameValue });
        isRenaming = false;
        invalidateAll();
    }
</script>

<div class="flex h-full w-full overflow-hidden">
    <!-- Sidebar -->
    <aside class="flex w-80 flex-none flex-col border-r border-surface-200-800 bg-surface-50-950">
        <!-- Sticky Header -->
        <header class="z-10 flex-none border-b border-surface-200-800 p-4">
            <div class="flex flex-col gap-2">
                {#if isRenaming}
                    <div class="flex items-center gap-2">
                        <input class="input px-2 py-1" bind:value={renameValue} />
                        <button class="variant-filled-primary btn-icon size-8" onclick={saveRename}>
                            <Check size={16} />
                        </button>
                        <button
                            class="variant-soft btn-icon size-8"
                            onclick={() => (isRenaming = false)}
                        >
                            <X size={16} />
                        </button>
                    </div>
                {:else}
                    <div class="flex items-center justify-between">
                        <h2 class="truncate h4 font-bold">{vehicle.name}</h2>
                        <button
                            class="variant-soft-surface btn-icon size-8"
                            onclick={startRename}
                            title="Rename"
                        >
                            <Pencil size={16} />
                        </button>
                    </div>
                {/if}

                <div class="flex items-end justify-between">
                    <div class="font-mono text-xs opacity-70">{vehicleId.slice(0, 8)}...</div>
                    <div class="text-xs">
                        {#if vehicle.immobilized}
                            <span class="badge preset-filled-error-500 font-bold text-white"
                                >IMMOBILIZED</span
                            >
                        {:else}
                            <span class="badge preset-filled-success-500 text-white">ACTIVE</span>
                        {/if}
                    </div>
                </div>
            </div>
        </header>

        <!-- Events List -->
        <div class="flex-1 space-y-3 overflow-y-auto p-4">
            {#if events.length === 0}
                <div class="p-4 text-center text-sm opacity-50">No events in last hour</div>
            {/if}

            {#each events as event}
                <div class="card preset-filled-surface-100-900 p-3 text-sm">
                    <div class="flex justify-between font-bold opacity-80">
                        <span class="uppercase">{event.type}</span>
                        <span>{event.ts.toLocaleTimeString()}</span>
                    </div>
                    <div class="mt-1 text-xs opacity-60">
                        {#if event.type === "geofence"}
                            {event.entered ? "Entered" : "Left"} Geofence
                        {:else if event.type === "immobilized"}
                            State: {event.immobilized ? "LOCKED" : "UNLOCKED"}
                        {/if}
                    </div>
                </div>
            {/each}
        </div>

        <!-- Footer Actions -->
        <div class="z-10 flex-none space-y-2 border-t border-surface-200-800 p-4">
            <button
                class="btn w-full font-bold {vehicle.immobilized
                    ? 'preset-filled-success-500 text-white'
                    : 'preset-filled-warning-500 text-black'}"
                onclick={toggleImmobilization}
            >
                {#if vehicle.immobilized}
                    <Unlock class="mr-2 size-5" /> Mobilize
                {:else}
                    <Lock class="mr-2 size-5" /> Immobilize
                {/if}
            </button>

            <button
                class="btn w-full preset-filled-error-500 font-bold text-white"
                onclick={handleDelete}
            >
                <Trash2 class="mr-2 size-5" />
                Delete Vehicle
            </button>
        </div>
    </aside>

    <!-- Map -->
    <div class="relative h-full w-full bg-slate-100">
        <MapLibre
            bind:map
            style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
            class="h-full w-full"
            center={initialCenter}
            zoom={13}
        >
            <NavigationControl position="top-right" />

            <GeoJSON data={traceData as any}>
                <LineLayer
                    layout={{ "line-join": "round", "line-cap": "round" }}
                    paint={{ "line-color": "#3b82f6", "line-width": 4, "line-opacity": 0.8 }}
                />
            </GeoJSON>

            {#if lastPosition}
                <DefaultMarker lngLat={[lastPosition.lon, lastPosition.lat]}>
                    <Popup offset={[0, -10]}>
                        <div class="text-sm font-bold">Current Position</div>
                        <div class="text-xs">{lastPosition.ts.toLocaleTimeString()}</div>
                    </Popup>
                </DefaultMarker>
            {:else if vehicle.lat && vehicle.lon}
                <DefaultMarker lngLat={[vehicle.lon, vehicle.lat]} />
            {/if}
        </MapLibre>

        <div
            class="glass absolute top-4 left-4 z-20 card p-2 text-xs font-bold opacity-80 backdrop-blur-md"
        >
            Last 1h History
        </div>
    </div>
</div>
