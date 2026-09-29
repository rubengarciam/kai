# Bundled assets

`chart.umd.js` is **Chart.js 4.4.0**, the official minified UMD build, unmodified. `garmin_chart.py` embeds it in every dashboard it writes, so a dashboard is a single self-contained HTML file that draws with no network access and no third-party CDN, and still works after you move, email or archive it.

| File | What it is |
| ---- | ---------- |
| `chart.umd.js` | Chart.js 4.4.0 `dist/chart.umd.js` from the npm package (MIT). It bundles `@kurkle/color` 0.3.2 (MIT) |
| `chart.umd.js.sha256` | Its SHA-256, checked by the tests so an accidental edit is caught |
| `LICENSE-chartjs.md` | Chart.js licence (MIT, Chart.js Contributors) |
| `LICENSE-kurkle-color.md` | `@kurkle/color` licence (MIT, Jukka Kurkela) |

Kai itself is GPL v3; these two MIT-licensed files keep their own licences and the copyright banner at the top of `chart.umd.js` must stay intact. When a dashboard is generated the only change is that the trailing `//# sourceMappingURL=` comment is dropped, since the map file isn't shipped.

## Updating Chart.js

Take the file from the npm package and check it against the registry's published integrity hash before committing it:

```bash
V=4.5.0                                            # the new version
curl -s https://registry.npmjs.org/chart.js/$V > meta.json
curl -s -o chart.tgz "$(python3 -c "import json;print(json.load(open('meta.json'))['dist']['tarball'])")"
python3 -c "import json,base64,hashlib as h; m=json.load(open('meta.json')); print('integrity ok:', 'sha512-'+base64.b64encode(h.sha512(open('chart.tgz','rb').read()).digest()).decode()==m['dist']['integrity'])"
tar -xzf chart.tgz
cp package/dist/chart.umd.js skills/garmin-health-analysis/assets/chart.umd.js
cp package/LICENSE.md skills/garmin-health-analysis/assets/LICENSE-chartjs.md
(cd skills/garmin-health-analysis/assets && sha256sum chart.umd.js > chart.umd.js.sha256)
```

Then update the version numbers in this file and in the CDN fallback URL in `garmin_chart.py`, check the bundled `@kurkle/color` version and licence, and render a dashboard with the network off. The tests refuse a build that contains a literal `</script`, which would break the inlining.
