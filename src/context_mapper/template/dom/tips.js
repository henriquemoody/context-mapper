// A small box that follows the cursor. Comments come from context-map.yml, so they go in as text, never as HTML.
const tip = document.createElement("div");
tip.id = "tip";
document.body.appendChild(tip);
export function showTip(note, ev) {
  if (!note.length) return hideTip();
  tip.replaceChildren(...note.map(n => {
    const p = document.createElement("p");
    if (n.kind === "attr") {
      // An attribute reads as a data row: a small field label, its value after
      // it — not a second name. The hairline above the first one is CSS.
      p.className = "attr";
      const label = document.createElement("span");
      label.className = "k";
      label.textContent = n.title;
      p.append(label, " ", n.text);
      return p;
    }
    if (n.kind) p.className = n.kind;
    const title = document.createElement("b");
    title.textContent = n.title;
    p.append(title, document.createElement("br"), n.text);
    return p;
  }));
  tip.style.display = "block";
  const x = Math.min(ev.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
  const y = ev.clientY + 18 + tip.offsetHeight > window.innerHeight ? ev.clientY - tip.offsetHeight - 12 : ev.clientY + 18;
  tip.style.left = Math.max(8, x) + "px";
  tip.style.top = Math.max(8, y) + "px";
}
export const hideTip = () => { tip.style.display = "none"; };
