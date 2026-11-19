// Finding an element by id: the one DOM helper the page still needs — the
// elements themselves are rendered by preact.
export const $ = (id) => document.getElementById(id);
