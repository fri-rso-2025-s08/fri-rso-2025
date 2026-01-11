<script lang="ts">
    import { invalidateAll } from "$app/navigation";
    import { VehicleClient, type VehicleRead } from "$lib/api_client";
    import { PlusIcon } from "@lucide/svelte";
    import { Popover, Portal } from "@skeletonlabs/skeleton-svelte";
    import { onMount } from "svelte";
    import { DefaultMarker, MapLibre, NavigationControl, Popup, type Map } from "svelte-maplibre";
    import type { PageData } from "./$types";

    // Svelte 5 props
    let { data }: { data: PageData } = $props();
    let map: Map | undefined = $state();

    function handleCardEvent(vehicle: VehicleRead) {
        if (vehicle.lat != null && vehicle.lon != null)
            map?.flyTo({ center: [vehicle.lon, vehicle.lat], duration: 1000 });
    }

    onMount(() => {
        const interval = setInterval(() => {
            invalidateAll();
        }, 1000);

        return () => {
            clearInterval(interval);
        };
    });

    let popupOpen = $state(false);
    let popupName = $state("Test vehicle");
    let popupLat = $state(46.0663294);
    let popupLon = $state(14.4496982);
    let popupStd = $state(0.001);

    async function popupSubmit() {
        await new VehicleClient().createVehicle({
            name: popupName,
            vtype: "test",
            vconfig: { lat: popupLat, lon: popupLon, std: popupStd }
        });
        popupOpen = false;
    }

    let sortedVehicles = $derived(
        data.vehicles.toSorted((a, b) => {
            if (a.id < b.id) return -1;
            if (a.id > b.id) return 1;
            return 0;
        })
    );
</script>

<div class="flex h-full w-full overflow-hidden">
    <!-- Sidebar -->
    <aside class="flex w-80 flex-none flex-col border-r border-surface-200-800">
        <!-- Sticky Subtitle -->
        <header
            class="z-10 flex-none border-b border-surface-200-800 bg-surface-50-950 p-4 backdrop-blur-sm"
        >
            <h2 class="h4">Tracked vehicles</h2>
        </header>

        <!-- Sidebar Content (Scrollable) -->
        <div class="flex-1 space-y-4 overflow-y-auto p-4">
            {#each sortedVehicles as vehicle (vehicle.id)}
                <div
                    class="flex cursor-pointer items-center justify-between card preset-filled-surface-100-900 p-4 transition-all hover:brightness-90"
                    onclick={() => handleCardEvent(vehicle)}
                    role="button"
                    tabindex="0"
                    onkeydown={(e) => e.key === "Enter" && handleCardEvent(vehicle)}
                >
                    <div class="space-y-1">
                        <h3 class="font-semibold">{vehicle.name}</h3>
                        <div class="flex items-center gap-2 text-xs opacity-80">
                            <!-- Helper: capitalize or format vtype if needed -->
                            <span class="uppercase">{vehicle.vtype}</span>
                            {#if vehicle.immobilized}
                                <span class="badge preset-filled-error-500 font-bold text-white"
                                    >IMMOBILIZED</span
                                >
                            {/if}
                            {#if vehicle.lat == null && vehicle.lon == null}
                                <span class="badge preset-filled-error-500 font-bold text-white"
                                    >?</span
                                >
                            {/if}
                        </div>
                    </div>

                    <!-- Pop out button: Direct link to details page -->
                    <a
                        href="/vehicles/{vehicle.id}"
                        class="variant-soft-primary btn-icon"
                        title="Pop out"
                        onclick={(e) => e.stopPropagation()}
                    >
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="20"
                            height="20"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            ><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"
                            ></path><polyline points="15 3 21 3 21 9"></polyline><line
                                x1="10"
                                y1="14"
                                x2="21"
                                y2="3"
                            ></line></svg
                        >
                    </a>
                </div>
            {/each}
        </div>

        <!-- Sticky Footer (Reserved Space) -->
        <div class="z-10 flex-none border-t border-surface-200-800 bg-surface-50-950 p-4">
            <Popover>
                <Popover.Trigger class="btn w-full preset-filled font-bold"
                    ><svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        class="mr-2"
                        ><line x1="12" y1="5" x2="12" y2="19"></line><line
                            x1="5"
                            y1="12"
                            x2="19"
                            y2="12"
                        ></line></svg
                    >
                    Add Unit</Popover.Trigger
                >
                <Portal>
                    <Popover.Positioner>
                        <Popover.Content
                            class="z-50 w-80 space-y-4 card bg-surface-50 p-4 shadow-xl"
                        >
                            <!-- Name Field -->
                            <label class="label">
                                <span class="label-text">Name</span>
                                <input
                                    class="input"
                                    type="text"
                                    bind:value={popupName}
                                    placeholder="Entry Name"
                                />
                            </label>

                            <!-- Fieldset Group -->
                            <fieldset
                                class="space-y-3 rounded-container border border-surface-200-800 p-4"
                            >
                                <legend class="px-2 text-sm font-bold opacity-60"
                                    >Test connector settings</legend
                                >

                                <label class="label">
                                    <span class="label-text">Latitude</span>
                                    <input
                                        class="input"
                                        type="number"
                                        step="any"
                                        bind:value={popupLat}
                                    />
                                </label>

                                <label class="label">
                                    <span class="label-text">Longitude</span>
                                    <input
                                        class="input"
                                        type="number"
                                        step="any"
                                        bind:value={popupLon}
                                    />
                                </label>

                                <label class="label">
                                    <span class="label-text">Standard Deviation</span>
                                    <input
                                        class="input"
                                        type="number"
                                        step="any"
                                        bind:value={popupStd}
                                    />
                                </label>
                            </fieldset>

                            <!-- Big Plus Button -->
                            <Popover.CloseTrigger
                                type="button"
                                class="btn w-full preset-filled"
                                onclick={popupSubmit}
                            >
                                <PlusIcon class="size-6" />
                                <span>Confirm</span>
                            </Popover.CloseTrigger>

                            <!-- Arrow -->
                            <Popover.Arrow
                                class="[--arrow-background:var(--color-surface-100-900)] [--arrow-size:--spacing(2)]"
                            >
                                <Popover.ArrowTip />
                            </Popover.Arrow>
                        </Popover.Content>
                    </Popover.Positioner>
                </Portal>
            </Popover>
        </div>
    </aside>

    <div class="grid h-full w-full bg-red-50">
        <MapLibre
            bind:map
            style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
            class="relative h-full w-full"
            center={[14.4496982, 46.0663294]}
            zoom={9}
        >
            <NavigationControl position="top-right" />
            <!-- <Marker latLng={[-74.5, 40]} /> -->
            {#each sortedVehicles as { lat, lon, name }}
                {#if lat != null && lon != null}
                    <DefaultMarker lngLat={[lon, lat]}>
                        <Popup offset={[0, -10]}>
                            <div class="text-lg font-bold">{name}</div>
                        </Popup>
                    </DefaultMarker>
                {/if}
            {/each}
        </MapLibre>
    </div>
</div>
