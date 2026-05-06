/* sparkrules reproduce page - copy buttons + active TOC highlighting */

document.addEventListener('DOMContentLoaded', () => {
  // Copy buttons
  document.querySelectorAll('.copy-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const targetId = btn.getAttribute('data-copy');
      const codeEl = document.getElementById(targetId);
      if (!codeEl) return;
      try {
        await navigator.clipboard.writeText(codeEl.textContent);
        const orig = btn.textContent;
        btn.textContent = 'Copied!';
        btn.style.background = 'rgba(16, 185, 129, 0.2)';
        btn.style.color = '#10b981';
        setTimeout(() => {
          btn.textContent = orig;
          btn.style.background = '';
          btn.style.color = '';
        }, 1500);
      } catch (err) {
        btn.textContent = 'Failed';
        setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
      }
    });
  });

  // Active TOC on scroll
  const navLinks = document.querySelectorAll('.step-nav a');
  const sections = Array.from(navLinks).map((link) => {
    const id = link.getAttribute('href').replace('#', '');
    return { id, link, el: document.getElementById(id) };
  }).filter((s) => s.el);

  function updateActive() {
    const scrollPos = window.scrollY + 150;
    let current = sections[0];
    for (const s of sections) {
      if (s.el.offsetTop <= scrollPos) current = s;
    }
    navLinks.forEach((l) => l.classList.remove('active'));
    if (current && current.link) current.link.classList.add('active');
  }
  window.addEventListener('scroll', updateActive, { passive: true });
  updateActive();
});
