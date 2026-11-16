# oliviacpu fork

This is [sonicdm/ValheimModManager](https://github.com/sonicdm/ValheimModManager) with a few changes
for one home server. Nothing here is sent upstream.

## Changes

- **BepInExPack shows as installed.** The server image provides `denikson-BepInExPack_Valheim`, so
  the manager never tracks it. The Installed page now lists it first with its version and a `server`
  badge, and Discover and the package page mark it installed instead of offering Install.
- **Exports include BepInExPack.** `.r2z` files and share codes list it first, at the server's
  version, so Gale and r2modman install it for players. Imports and profile activation still skip it.
- The version comes from the pack's Thunderstore manifest as the server unpacked it. Mount the
  Valheim container's `/opt/valheim/dl/bepinex/extracted` read-only at `/valheim/server-pack`, or
  set `SERVER_PACK_MANIFEST` to the manifest's path. Without it, the newest Thunderstore version is used.
- **Exports leave out server-only mods.** The Installed page has a Players column: "Needed" or
  "Server only". It starts from the store's client/server categories (tagged server-side and not
  client-side means server only; untagged means needed) and you can click to change any mod.
  "Players: use store tags" in the row menu forgets your choice. Exports and share codes skip
  server-only mods; a kept mod's dependencies still install in Gale either way. Code:
  `backend/app/services/player_mods.py`, overrides in the `player_requirements` table.

The code is in `backend/app/services/server_pack.py`, with small hooks in `profiles.py`,
`api/routes.py` and the Installed and package pages.

- **Local mods aren't linked to store packages by name alone.** Upstream linked our own
  "Living World" to xSAUCEY_CREATIONSx-LivingWorld because the names match without spaces, then
  queued that mod as an "update". A name-only match now also needs the same author, if the manifest
  has an `author`, and the installed version must be one that package published. The next scan
  undoes wrong links made earlier and drops their queued updates. The code is `name_match_fits` in
  `packages.py`, plus `_wrong_name_link` in `scanner.py`.

## Builds

[`olivia-build.yml`](.github/workflows/olivia-build.yml) runs every day, on every push to main, and
when started by hand. It merges upstream's newest release into main inside the runner, runs the
backend tests, and publishes:

- `ghcr.io/oliviacpu/valheim-mod-manager:latest`
- `ghcr.io/oliviacpu/valheim-mod-manager:<upstream version>-olivia.<main commit>`

It only publishes when that tag doesn't exist yet. A new upstream release or a change to main
publishes; a day with neither does nothing. The merge is never pushed back to main, because a
`GITHUB_TOKEN` can't push upstream's changes to its own workflow files. Upstream's
`docker-publish.yml` is disabled in this fork's Actions settings.

If an upstream release doesn't merge cleanly, the build fails and opens an issue. Merge that tag
into main in a PR, and the next build publishes it. Until then the published image stays on the
previous release.
