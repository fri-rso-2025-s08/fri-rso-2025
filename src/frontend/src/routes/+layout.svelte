<script lang="ts">
    import "./layout.css";

    const appName = "VehicleTrack";
</script>

<div class="flex min-h-screen flex-col">
    <header class="flex h-16 shrink-0 items-center border-b border-surface-200-800 px-4">
        <a class="h3 leading-none" href="/">
            {appName}
        </a>

        <div class="ml-auto">
            <a href="/auth/logout" class="btn preset-filled"> Log out </a>
        </div>
    </header>

    <main class="grid min-h-0 flex-1 overflow-auto">
        <slot />
    </main>
</div>
