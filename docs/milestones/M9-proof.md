# M9 — Euro-area macro versioned adapter

M9 retrieves one fixed Euro-area HICP annual-rate series through the qualified
ECB SDMX endpoint. The request explicitly asks for `includeHistory=true`; the
retained result records the raw payload hash, series metadata, UTC retrieval
time and observation status. This is a point-in-time research input, not a
trading signal or execution feature.
