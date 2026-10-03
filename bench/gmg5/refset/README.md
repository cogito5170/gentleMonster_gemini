# GMG5 public reference set (CMD-GN1)

Design data for GMG5 S4: calibrating `pf_photos` / `pf_sort` thresholds and mood groups, and layout plans for G1/H4.
**Not evaluation data.** Nothing here comes from the BD-187 held-out questions or `gm-photos/heldout`, and no model is
fine-tuned on it (GMG5 S5). The set was collected by the `gmg-net` session, the only environment whose network allows
the sources (baseline BD-250). GMG owns the calibration (S4) and works from this branch.

| File | What |
|---|---|
| `manifest_photos.jsonl` | one line per stored photograph: Openverse id, group, query, title, creator, landing URL, licence + URL + attribution, stored file, sha256, size, quick measures |
| `photos/` | the photographs, shrunk to 800 px on the long edge (`<group>__<id8>.jpg`). Each file keeps its own licence (see the manifest) |
| `manifest_layouts.jsonl` | one line per layout reference: landing URL, licence / public-domain basis, a by-eye note and measured structure. **No page files** |
| `request_log.jsonl` | every HTTP attempt: time, host, path, status, bytes, Retry-After |
| `tools/` | `net.py` (polite HTTP), `search.py` (Openverse queries), `fetch.py` (downloads), `build_photos.py`, `build_layouts.py`, `layout.py` (structure from a scan), `licence_check.py` |

```
python3 tools/licence_check.py             # exit 1 on any stored file without a reuse licence
python3 tools/licence_check.py --selftest  # five deliberate breaks, each must be caught
```

## Counts (2026-10-03)

| Photographs (87, 9 MB) | n | | Layout references (40) | n |
|---|---|---|---|---|
| night_rain_street | 23 | | cover (magazine) | 16 |
| beach_dusk | 20 | | fashion_plate | 5 |
| still_object | 17 | | album_page | 5 |
| street_light_portrait | 14 | | catalogue_page | 4 |
| black_and_white | 13 | | editorial_page | 3 |
| | | | sketch_page · catalogue_cover · catalogue_spread | 2 · 2 · 2 |
| | | | album_cover | 1 |

Photo licences: CC BY 57, CC BY-SA 21, Public Domain Mark 6, CC0 3. Layout licences: CC BY 21, CC0 16, CC BY-SA 3.
By group (magazine / catalogue / photo book): 25 / 9 / 6.

Requests (`request_log.jsonl`, 350 attempts): Openverse 45 (all 200, within its anonymous limit of 200 a day),
live.staticflickr.com 241 (one 410 Gone), upload.wikimedia.org 62 (36 × 200, 26 × 429), archive.org 2 (one 200 and one
redirect refused). Wikimedia sent 429 at 1 request/s, again at one per 5 s, and once with Retry-After 600. The fetcher now
waits 15 s between Wikimedia requests and honours each Retry-After for the whole host. `commons.wikimedia.org` was not
used.

## Photographs

Licences allowed: CC0, Public Domain Mark, CC BY, CC BY-SA (Openverse `license=cc0,pdm,by,by-sa`). Only Flickr and
Wikimedia Commons sources, because their image hosts are the ones this environment can reach.

Groups are the photo_request types and moods of CMD-GMG5 S2 (questions 1–42): `night_rain_street`, `beach_dusk`,
`black_and_white`, `street_light_portrait`, `still_object`. Candidates came from two to six Openverse queries per group.
They were then **chosen by eye** from contact sheets (`tools/photo_selection.json`). The rules: on topic; a photograph
(not a painting or a render); no selfies; no close-ups of children; at most 3 per creator per group. The group is the
query's group, not a measurement. That keeps S4's calibration from being circular.

`quick_measures` come from ImageMagick and plain Python, because Pillow could not be installed: pypi is outside this
environment's network list. They are brightness, dark share, contrast, saturation, warmth and mono. They are a sanity
check only; S4 should run `gmg.photo.measure` on `photos/` itself.

People: some street and portrait photographs show identifiable adults. Their CC licences cover copyright, not
personality rights. Use them as design reference only, never in a published layout.

## Layout references

Magazines, catalogues and photo books, chosen by eye from Openverse (Wikimedia Commons and Flickr) results. Only
public-domain-age material (before 1929) or items with an open licence. Modern covers were left out even when the
uploader labelled them CC (the cover itself is a copyrighted work). Each line stores the URL and the derived structure
only: margins, columns, picture/text share, pictures per page, line height and type scale (`tools/layout.py`). A
by-eye note covers grid, masthead and the photo/word pattern, and `seen_counts` gives pictures and columns counted by
eye. Page images are not kept, even the public-domain ones.

**The measured numbers are coarse.** Against the by-eye counts, `measured.pictures` matches on 20 of 40 pages and
`measured.columns` on 27 of 40. Aged, tinted paper reads as mid-tone, which inflates `picture_share`. A scan photographed
on a background reads as zero margins. `type_scale` is unreliable on covers with drawn lettering. Use `seen` and
`seen_counts` first, and the measured values only as a rough second signal.

archive.org: its search and metadata APIs answer from `archive.org`. Page images and files redirect to data nodes
(`ia*.us.archive.org`, `dn*.archive.org`), which are outside the network list. `net.py` refuses such redirects instead
of routing around them, so archive.org gave no layout pages (see the request log).
