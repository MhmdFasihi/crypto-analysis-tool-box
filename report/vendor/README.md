# Vendored third-party assets

`reveal/` contains the three files from [reveal.js](https://revealjs.com) 5.2.1 that the
report inlines at build time — `dist/reset.css`, `dist/reveal.css` and `dist/reveal.js` —
plus its MIT licence. Vendoring keeps the generated deck self-contained: no CDN request,
so it renders offline and on a host with no outbound network access.

To upgrade: `npm pack reveal.js@<version>`, extract, and copy those three files here.
