<?php /** @var string $title */ ?>
<main class="mx-auto max-w-2xl p-8 space-y-6">
    <h1 class="text-2xl font-bold text-slate-900">
        <i class="ph ph-heartbeat text-rose-600"></i>
        VALENIA skeleton
    </h1>

    <!-- Alpine: client interactivity -->
    <section x-data="{ count: 0 }" class="rounded-lg border border-slate-200 bg-white p-4">
        <button
            @click="count++"
            class="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700">
            <i class="ph-bold ph-plus"></i> Klik
        </button>
        <span class="ml-2 text-sm">Count: <strong x-text="count"></strong></span>
    </section>

    <!-- htmx: server partial swap (endpoint arrives with the router task) -->
    <section class="rounded-lg border border-slate-200 bg-white p-4">
        <button
            hx-get="/greeting"
            hx-target="#greeting"
            hx-swap="innerHTML"
            class="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100">
            Muat salam (htmx)
        </button>
        <div id="greeting" class="mt-2 text-sm text-slate-600">—</div>
    </section>
</main>
