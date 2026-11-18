// Downloading the rendered diagram as an image. build.py splices this into
// app.js for the interactive page; mermaid.py splices it into the script of
// every static diagram page, so both offer the same export.

// The diagram as a standalone SVG: a text the file holds, and the size it
// opens at. What only makes sense on the page goes out — the wide
// transparent copies that catch hover on an arrow, the accent arrowheads
// hover lights up (a hovered arrow points at its copy, so point it back at
// the original before dropping it), and the links that navigate within the
// site. A file of its own has none of the page's CSS either: the size comes
// from the viewBox, in pixels, instead of the stylesheet's width rules.
function standaloneSvg(svg) {
  const clone = svg.cloneNode(true);
  clone.classList.remove("hovering");
  clone.querySelectorAll(".edge-hit").forEach(n => n.remove());
  clone.querySelectorAll("[id$='-on']").forEach(copy => {
    const original = copy.id.slice(0, -3);
    clone.querySelectorAll("[marker-end]").forEach(el => {
      if (el.getAttribute("marker-end").includes(copy.id))
        el.setAttribute("marker-end", `url(#${original})`);
    });
    copy.remove();
  });
  clone.querySelectorAll("a").forEach(a => {
    a.removeAttribute("href");
    a.removeAttributeNS("http://www.w3.org/1999/xlink", "href");
  });
  const parts = (clone.getAttribute("viewBox") || "").trim().split(/\s+/).map(Number);
  const width = parts.length === 4 ? parts[2] : svg.getBoundingClientRect().width;
  const height = parts.length === 4 ? parts[3] : svg.getBoundingClientRect().height;
  clone.setAttribute("width", Math.round(width));
  clone.setAttribute("height", Math.round(height));
  clone.removeAttribute("style");
  // The font the labels show on the page is the page's own — Mermaid writes
  // no font-family into the drawing — and the page's stylesheet doesn't
  // travel with the file. Bake in the family the live diagram computes, so
  // the download keeps what the screen shows.
  clone.style.fontFamily = getComputedStyle(svg).fontFamily;
  // The page paints the diagram's background; a file of its own needs one of
  // its own, the same color, or a dark slide or a dark-mode README turns it
  // into dark text on a dark page. The viewBox need not start at 0, so the
  // rect covers it, not the corner the axes cross at.
  const background = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  if (parts.length === 4) {
    background.setAttribute("x", parts[0]);
    background.setAttribute("y", parts[1]);
  }
  background.setAttribute("width", "100%");
  background.setAttribute("height", "100%");
  const pageBg = getComputedStyle(document.body).backgroundColor;
  background.setAttribute("fill", pageBg === "rgba(0, 0, 0, 0)" ? "#ffffff" : pageBg);
  clone.insertBefore(background, clone.firstChild);
  return { text: '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(clone),
           width: Math.round(width), height: Math.round(height) };
}

function saveBlob(blob, filename) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// `svg` is the rendered diagram, `format` "png" or "svg", `name` the file
// name without its extension. The PNG draws the SVG on a canvas at twice
// its size, on the page's own background, so the image looks like the
// diagram does on screen.
function downloadDiagram(svg, format, name) {
  const { text, width, height } = standaloneSvg(svg);
  if (format === "svg") {
    saveBlob(new Blob([text], { type: "image/svg+xml;charset=utf-8" }), name + ".svg");
    return;
  }
  const scale = Math.min(2, 16384 / Math.max(width, height));  // stay under the canvas limit
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const img = new Image();
  img.onload = () => {
    const ctx = canvas.getContext("2d");
    const bg = getComputedStyle(document.body).backgroundColor;
    ctx.fillStyle = bg === "rgba(0, 0, 0, 0)" ? "#ffffff" : bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob => blob && saveBlob(blob, name + ".png"), "image/png");
  };
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(text);
}
