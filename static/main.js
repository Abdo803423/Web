// ── SCROLL REVEAL ────────────────────────────────────────────
const observer = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('vis'); observer.unobserve(e.target); }
  });
}, { threshold: 0.08 });
document.querySelectorAll('.rv').forEach(el => observer.observe(el));

// ── NAVBAR SCROLL ─────────────────────────────────────────────
window.addEventListener('scroll', () => {
  document.getElementById('nav')?.classList.toggle('scrolled', scrollY > 20);
});

// ── MOBILE NAV ────────────────────────────────────────────────
function toggleNav() {
  document.getElementById('nl')?.classList.toggle('open');
}
document.addEventListener('click', e => {
  if (!e.target.closest('nav')) document.getElementById('nl')?.classList.remove('open');
});

// ── FILE DROP ─────────────────────────────────────────────────
function fsel(input) {
  const name = input.files[0]?.name;
  const el = document.getElementById('fName');
  if (el) el.textContent = name ? `📎 ${name}` : '';
}
function dov(e) { e.preventDefault(); document.getElementById('drop')?.classList.add('over'); }
function dlv() { document.getElementById('drop')?.classList.remove('over'); }
function dop(e) {
  e.preventDefault(); dlv();
  const file = e.dataTransfer.files[0];
  if (file) {
    const el = document.getElementById('fName');
    if (el) el.textContent = `📎 ${file.name}`;
    const dt = new DataTransfer();
    dt.items.add(file);
    const fi = document.getElementById('fi');
    if (fi) fi.files = dt.files;
  }
}

// ── FLASH AUTO-DISMISS ────────────────────────────────────────
setTimeout(() => {
  document.querySelectorAll('.flash').forEach(f => f.remove());
}, 5000);
