/**
 * Shared navigation drawer for phd-demographics.andy-barr.com
 *
 * Include this script on any page:
 *   <script src="/nav.js"></script>
 *
 * It injects a slide-out drawer on the left side that appears
 * when the user hovers near the left edge or clicks the menu button.
 */
(function() {
  const PAGES = [
    { section: 'Graduate Names' },
    { title: 'STEM Graduate Names', href: '/stem.html', desc: '107 universities, 334K records' },
    { title: 'Non-STEM Graduate Names', href: '/non_stem.html', desc: '136K records' },
    { title: 'Approximate Classifications', href: '/stem_dashboard.html', desc: 'Surname-based estimates' },
    { section: 'National Overview' },
    { title: 'National Overview', href: '/overview.html', desc: 'NSF SED trends, countries, funding' },
    { title: 'IPEDS PhD Dashboard', href: '/ipeds_dashboard.html', desc: 'Completions 1984\u20132024' },
    { section: 'Reference' },
    { title: 'Data Sources & Methodology', href: '/data_sources.html', desc: 'Government sources, methods' },
    { title: 'Data Catalog (JSON)', href: '/catalog.json', desc: 'Machine-readable API' },
    { title: 'WebMCP Integration', href: '/webmcp.html', desc: 'AI agent tools & API' },
    { section: '' },
    { title: 'Home', href: '/index.html', desc: '' },
    { title: 'About', href: 'https://andy-barr.com', desc: 'andy-barr.com', external: true },
  ];

  // Don't inject on stem.html/non_stem.html — they have their own sidebar
  const path = location.pathname;
  if (path.endsWith('/stem.html') || path.endsWith('/non_stem.html') || path.endsWith('/name_lists.html')) {
    return;
  }

  // Inject CSS
  const style = document.createElement('style');
  style.textContent = `
    .site-nav-trigger {
      position: fixed; left: 0; top: 0; bottom: 0; width: 12px; z-index: 998;
    }
    .site-nav-drawer {
      position: fixed; left: -280px; top: 0; bottom: 0; width: 280px;
      background: #1e293b; border-right: 1px solid #334155;
      z-index: 1000; transition: left 0.25s ease;
      overflow-y: auto; padding: 0;
      box-shadow: 4px 0 20px rgba(0,0,0,0.3);
    }
    .site-nav-drawer.open { left: 0; }
    .site-nav-overlay {
      display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4);
      z-index: 999;
    }
    .site-nav-drawer.open + .site-nav-overlay { display: block; }
    .site-nav-header {
      padding: 1.25rem 1.25rem 0.75rem; border-bottom: 1px solid #334155;
    }
    .site-nav-header h3 {
      font-size: 0.85rem; font-weight: 700; color: #e2e8f0; margin: 0;
    }
    .site-nav-header .site-nav-sub {
      font-size: 0.68rem; color: #94a3b8; margin-top: 2px;
    }
    .site-nav-section {
      font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em;
      color: #64748b; padding: 1rem 1.25rem 0.4rem; font-weight: 600;
    }
    .site-nav-link {
      display: block; padding: 0.6rem 1.25rem; text-decoration: none;
      color: #94a3b8; font-size: 0.82rem; transition: all 0.15s;
      border-left: 3px solid transparent;
    }
    .site-nav-link:hover {
      background: rgba(56,189,248,0.06); color: #e2e8f0;
      border-left-color: #38bdf8;
    }
    .site-nav-link.active {
      color: #38bdf8; background: rgba(56,189,248,0.08);
      border-left-color: #38bdf8; font-weight: 600;
    }
    .site-nav-link .nav-desc {
      font-size: 0.68rem; color: #64748b; margin-top: 1px;
    }
    .site-nav-btn {
      position: fixed; top: 12px; left: 12px; z-index: 997;
      background: #1e293b; border: 1px solid #334155; color: #94a3b8;
      width: 36px; height: 36px; border-radius: 8px; cursor: pointer;
      font-size: 1.1rem; display: flex; align-items: center; justify-content: center;
      transition: all 0.15s;
    }
    .site-nav-btn:hover { background: #334155; color: #e2e8f0; }
    /* Hide button on pages that already have nav */
    .has-own-nav .site-nav-btn { display: none; }
  `;
  document.head.appendChild(style);

  // Inject HTML
  const trigger = document.createElement('div');
  trigger.className = 'site-nav-trigger';

  const drawer = document.createElement('nav');
  drawer.className = 'site-nav-drawer';
  drawer.setAttribute('aria-label', 'Site navigation');

  const overlay = document.createElement('div');
  overlay.className = 'site-nav-overlay';

  const btn = document.createElement('button');
  btn.className = 'site-nav-btn';
  btn.setAttribute('aria-label', 'Open navigation');
  btn.innerHTML = '\u2630';

  // Build drawer content
  let html = `<div class="site-nav-header">
    <h3>PhD Demographics</h3>
    <div class="site-nav-sub">US Graduate Program Research</div>
  </div>`;

  const currentPath = location.pathname;
  for (const item of PAGES) {
    if (item.section) {
      html += `<div class="site-nav-section">${item.section}</div>`;
    } else {
      const isActive = currentPath.endsWith(item.href) ||
                       (item.href === '/index.html' && (currentPath === '/' || currentPath.endsWith('/')));
      const cls = isActive ? 'site-nav-link active' : 'site-nav-link';
      const target = item.external ? ' target="_blank"' : '';
      const ext = item.external ? ' &#8599;' : '';
      html += `<a class="${cls}" href="${item.href}"${target}>${item.title}${ext}`;
      if (item.desc) html += `<div class="nav-desc">${item.desc}</div>`;
      html += `</a>`;
    }
  }
  drawer.innerHTML = html;

  document.body.appendChild(trigger);
  document.body.appendChild(drawer);
  document.body.appendChild(overlay);
  document.body.appendChild(btn);

  // Behavior: open on hover near left edge or button click
  let hoverTimeout;
  trigger.addEventListener('mouseenter', () => {
    hoverTimeout = setTimeout(() => drawer.classList.add('open'), 150);
  });
  trigger.addEventListener('mouseleave', () => clearTimeout(hoverTimeout));

  drawer.addEventListener('mouseleave', (e) => {
    // Only close if mouse didn't go to the trigger
    if (e.relatedTarget !== trigger && !trigger.contains(e.relatedTarget)) {
      drawer.classList.remove('open');
    }
  });

  overlay.addEventListener('click', () => drawer.classList.remove('open'));

  btn.addEventListener('click', () => {
    drawer.classList.toggle('open');
  });

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') drawer.classList.remove('open');
  });
})();
