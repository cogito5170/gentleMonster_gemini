"""Search Openverse for candidates (CMD-GN1 S2/S3). Writes raw results to a work directory; nothing is chosen here.

    python3 tools/search.py <workdir>

Only the licences the directive allows (CC0, public domain mark, CC BY, CC BY-SA) and only sources whose image hosts
this environment can reach (Flickr -> live.staticflickr.com, Wikimedia -> upload.wikimedia.org).
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import net  # noqa: E402

LICENCES = "cc0,pdm,by,by-sa"

# photo groups: the photo_request types and moods of CMD-GMG5 S2 (questions 1-42)
PHOTO_QUERIES = {
    "night_rain_street": ["rainy night street", "wet street neon reflection night", "rain night city", "umbrella rain night"],
    "beach_dusk": ["beach dusk", "beach twilight sea"],
    "black_and_white": ["black and white street photography", "black and white portrait"],
    "street_light_portrait": ["portrait street light night", "night portrait neon light", "night portrait city lights", "streetlight portrait", "portrait at night", "night street portrait woman"],
    "still_object": ["still life objects", "sunglasses still life", "still life photography", "eyeglasses on table"],
}
# layout references: scans of magazines, catalogues and photo books (Wikimedia hosts public-domain scans)
LAYOUT_QUERIES = {
    "magazine": ["magazine cover 1920", "Vogue cover", "Harper's Bazar cover", "magazine spread illustrated"],
    "catalogue": ["Sears catalog page", "mail order catalogue page", "fashion catalogue page", "trade catalog page illustrated"],
    "photo_book": ["photo book page", "photographic album page", "photogravure plate book page"],
}


def search(q: str, source: str, extra: str = "") -> list:
    url = (f"https://api.openverse.org/v1/images/?q={urllib.parse.quote(q)}&license={LICENCES}&source={source}"
           f"&page_size=20&mature=false{extra}")
    return net.get_json(url)["results"]


def main(work: str):
    out = Path(work)
    out.mkdir(parents=True, exist_ok=True)
    for kind, table, source, extra in (("photo", PHOTO_QUERIES, "flickr,wikimedia", "&category=photograph"),
                                       ("layout", LAYOUT_QUERIES, "wikimedia", "")):
        rows = []
        for group, qs in table.items():
            for q in qs:
                for r in search(q, source, extra):
                    rows.append({"group": group, "query": q, **r})
                print(kind, group, q, len(rows), flush=True)
        (out / f"{kind}_candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
