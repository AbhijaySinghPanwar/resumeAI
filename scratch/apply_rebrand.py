import os
import re

FRONTEND_DIR = r"c:\Users\Rajvi\OneDrive\Desktop\resumeai_fullstack\resumeai_app\frontend"
files = [
    "index.html",
    "login.html",
    "signup.html",
    "history.html",
    "reports.html",
    "ai_assistant.html",
    "interview_prep.html"
]

NEW_FOOTER = """
<!-- ── Modern Footer ───────────────────────────────────────────────────────── -->
<footer style="background: white; border-top: 1px solid var(--border); padding: 4rem 2rem 2rem; margin-top: 4rem; color: var(--text);">
  <div style="max-width: 1200px; margin: 0 auto;">
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 2rem; margin-bottom: 3rem;">
      <div style="grid-column: span 2;">
        <div style="font-weight: 800; font-size: 1.25rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="url(#footer-grad)" stroke-width="2.5"><defs><linearGradient id="footer-grad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="var(--primary)"/><stop offset="100%" stop-color="var(--secondary)"/></linearGradient></defs><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          TalentLens AI
        </div>
        <p style="color: var(--muted); font-size: 0.95rem; line-height: 1.6; max-width: 400px;">
          AI-Powered Resume Intelligence Platform. Helping students and professionals optimize resumes, improve ATS performance, prepare for interviews, and match job opportunities using AI.
        </p>
      </div>
      
      <div>
        <h4 style="font-size: 0.9rem; font-weight: 700; margin-bottom: 1.25rem; text-transform: uppercase; letter-spacing: 0.05em;">Features</h4>
        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
          <a href="#" style="color: var(--muted); text-decoration: none; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">Resume Parsing</a>
          <a href="#" style="color: var(--muted); text-decoration: none; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">ATS Analysis</a>
          <a href="#" style="color: var(--muted); text-decoration: none; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">JD Matching</a>
          <a href="ai_assistant.html" style="color: var(--muted); text-decoration: none; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">AI Resume Assistant</a>
          <a href="interview_prep.html" style="color: var(--muted); text-decoration: none; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">Interview Preparation</a>
          <a href="history.html" style="color: var(--muted); text-decoration: none; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">Resume History</a>
          <a href="reports.html" style="color: var(--muted); text-decoration: none; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">Saved Reports</a>
        </div>
      </div>
      
      <div>
        <h4 style="font-size: 0.9rem; font-weight: 700; margin-bottom: 1.25rem; text-transform: uppercase; letter-spacing: 0.05em;">Resources</h4>
        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
          <a href="https://github.com/AbhijaySinghPanwar/resumeAI" target="_blank" style="color: var(--muted); text-decoration: none; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">GitHub Repository</a>
          <a href="#" style="color: var(--muted); text-decoration: none; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">Documentation</a>
          <a href="#" style="color: var(--muted); text-decoration: none; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">Privacy Policy</a>
        </div>
      </div>
      
      <div>
        <h4 style="font-size: 0.9rem; font-weight: 700; margin-bottom: 1.25rem; text-transform: uppercase; letter-spacing: 0.05em;">Tech Stack</h4>
        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
          <span style="color: var(--muted); font-size: 0.95rem;">FastAPI</span>
          <span style="color: var(--muted); font-size: 0.95rem;">Python</span>
          <span style="color: var(--muted); font-size: 0.95rem;">Gemini AI</span>
          <span style="color: var(--muted); font-size: 0.95rem;">SQLAlchemy</span>
          <span style="color: var(--muted); font-size: 0.95rem;">SQLite / PostgreSQL</span>
        </div>
      </div>
    </div>
    
    <div style="border-top: 1px solid var(--border); padding-top: 2rem; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 1rem;">
      <div style="color: var(--muted); font-size: 0.9rem;">
        &copy; 2026 TalentLens AI. Built with ❤️ using FastAPI &bull; Python &bull; Gemini AI
      </div>
      <div style="display: flex; gap: 1.5rem;">
        <a href="https://github.com/AbhijaySinghPanwar/resumeAI" target="_blank" style="color: var(--muted); text-decoration: none; font-weight: 500; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">GitHub</a>
        <a href="#" style="color: var(--muted); text-decoration: none; font-weight: 500; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">LinkedIn</a>
        <a href="#" style="color: var(--muted); text-decoration: none; font-weight: 500; font-size: 0.95rem; transition: color 0.2s;" onmouseover="this.style.color='var(--primary)'" onmouseout="this.style.color='var(--muted)'">Email</a>
      </div>
    </div>
  </div>
</footer>
"""

NAV_JS = """
// ── Navbar ──────────────────────────────────────────────────────────────────
const API = 'http://localhost:8000';

function getToken() { return localStorage.getItem('auth_token'); }
function getUser()  {
  const u = localStorage.getItem('auth_user');
  return u ? JSON.parse(u) : null;
}
function doLogout() {
  const token = getToken();
  if (token) {
    fetch(`${API}/auth/logout`, {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + token }
    }).catch(() => {});
  }
  localStorage.removeItem('auth_token');
  localStorage.removeItem('auth_user');
  window.location.href = 'login.html';
}

function renderNav() {
  const user = getUser();
  const navRight = document.getElementById('navRight');
  if (!navRight) return;
  
  const currentPath = window.location.pathname.split('/').pop() || 'index.html';
  const isActive = (path) => currentPath === path ? 'active' : '';

  if (user) {
    navRight.innerHTML = `
      <div class="nav-links">
        <a href="index.html" class="nav-link ${isActive('index.html')}">Dashboard</a>
        <a href="history.html" class="nav-link ${isActive('history.html')}">History</a>
        <a href="reports.html" class="nav-link ${isActive('reports.html')}">Reports</a>
        <a href="ai_assistant.html" class="nav-link ${isActive('ai_assistant.html')}">AI Assistant</a>
        <a href="interview_prep.html" class="nav-link ${isActive('interview_prep.html')}">Interview Prep</a>
      </div>
      <div class="profile-dropdown">
        <button class="nav-badge profile-btn">
          <span>${user.name.split(' ')[0]} ▼</span>
        </button>
        <div class="profile-menu">
          <div class="profile-header">
            <strong>${user.name}</strong>
            <small>${user.email}</small>
          </div>
          <a href="#" class="profile-item">My Account</a>
          <button class="profile-item logout-btn" onclick="doLogout()">Logout</button>
        </div>
      </div>
    `;
  } else {
    navRight.innerHTML = `
      <div class="nav-links">
        <a href="index.html" class="nav-link ${isActive('index.html')}">Features</a>
        <a href="ai_assistant.html" class="nav-link ${isActive('ai_assistant.html')}">AI Assistant</a>
        <a href="interview_prep.html" class="nav-link ${isActive('interview_prep.html')}">Interview Prep</a>
        <a href="https://github.com/AbhijaySinghPanwar/resumeAI" target="_blank" class="nav-link">GitHub</a>
      </div>
      <div class="auth-buttons">
        <a href="login.html" class="nav-link login-link">Login</a>
        <button class="btn-nav signup-btn" onclick="window.location.href='signup.html'">Sign Up</button>
      </div>
    `;
  }
}
renderNav();

window.addEventListener('scroll', () => {
  const nav = document.querySelector('.navbar');
  if (nav && window.scrollY > 10) {
    nav.classList.add('scrolled');
  } else if(nav) {
    nav.classList.remove('scrolled');
  }
});
"""

NEW_NAV_CSS = """
    /* Modern Navbar CSS */
    .navbar {
      position: sticky; top: 0; z-index: 1000;
      background: rgba(255, 255, 255, 0.85);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid transparent;
      transition: all 0.3s ease;
      padding: 1rem 0;
    }
    .navbar.scrolled {
      background: rgba(255, 255, 255, 0.95);
      border-bottom: 1px solid var(--border);
      box-shadow: 0 4px 20px rgba(0,0,0,0.03);
      padding: 0.75rem 0;
    }
    .nav-inner {
      display: flex; justify-content: space-between; align-items: center;
      max-width: 1200px; margin: 0 auto; padding: 0 1.5rem;
    }
    .logo {
      font-size: 1.25rem; font-weight: 800; color: var(--text); text-decoration: none;
      display: flex; align-items: center; gap: 0.5rem;
    }
    .logo span {
      background: linear-gradient(135deg, var(--primary), var(--secondary));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .nav-right { display: flex; align-items: center; gap: 2rem; }
    .nav-links { display: flex; align-items: center; gap: 1.5rem; }
    
    .nav-link {
      color: var(--muted);
      text-decoration: none;
      font-size: 0.95rem;
      font-weight: 500;
      position: relative;
      padding: 0.5rem 0;
      transition: color 0.2s ease;
    }
    .nav-link:hover { color: var(--text); }
    .nav-link::after {
      content: ''; position: absolute; bottom: 0; left: 0; width: 0%; height: 2px;
      background: var(--primary); transition: width 0.2s ease; border-radius: 2px;
    }
    .nav-link:hover::after, .nav-link.active::after { width: 100%; }
    .nav-link.active { color: var(--text); font-weight: 600; }
    
    .auth-buttons { display: flex; align-items: center; gap: 1rem; }
    .login-link { padding: 0.5rem 1rem; border-radius: 8px; transition: background 0.2s; }
    .login-link:hover { background: rgba(0,0,0,0.04); color: var(--text); }
    .signup-btn {
      background: linear-gradient(135deg, var(--primary), var(--secondary));
      color: white; border: none; padding: 0.6rem 1.25rem; border-radius: 8px;
      font-weight: 600; font-size: 0.95rem; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;
    }
    .signup-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(79,70,229,0.3); }

    /* Profile Dropdown */
    .profile-dropdown { position: relative; }
    .profile-btn {
      background: rgba(79,70,229,0.08); color: var(--primary);
      border: none; padding: 0.5rem 1rem; border-radius: 20px;
      font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 0.5rem;
      transition: background 0.2s;
    }
    .profile-btn:hover { background: rgba(79,70,229,0.15); }
    .profile-menu {
      position: absolute; top: calc(100% + 0.5rem); right: 0;
      background: white; border: 1px solid var(--border); border-radius: 12px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.05); width: 220px;
      opacity: 0; visibility: hidden; transform: translateY(-10px);
      transition: all 0.2s; z-index: 1000;
    }
    .profile-dropdown:hover .profile-menu { opacity: 1; visibility: visible; transform: translateY(0); }
    .profile-header { padding: 1rem; border-bottom: 1px solid var(--border); }
    .profile-header strong { display: block; color: var(--text); font-size: 0.95rem; }
    .profile-header small { color: var(--muted); font-size: 0.8rem; }
    .profile-item {
      display: block; width: 100%; text-align: left; padding: 0.75rem 1rem;
      color: var(--text); text-decoration: none; font-size: 0.95rem; border: none; background: none;
      cursor: pointer; transition: background 0.2s;
    }
    .profile-item:hover { background: var(--bg); }
    .logout-btn { color: #EF4444; border-top: 1px solid var(--border); border-radius: 0 0 12px 12px; }

    /* Responsive Navbar */
    .mobile-menu-btn { display: none; background: none; border: none; color: var(--text); cursor: pointer; }
    @media (max-width: 768px) {
      .nav-links, .auth-buttons, .profile-dropdown { display: none; }
      .nav-right { flex-direction: column; width: 100%; position: absolute; top: 100%; left: 0; background: white; border-bottom: 1px solid var(--border); padding: 1rem; gap: 1rem; display: none; }
      .nav-right.show { display: flex; }
      .mobile-menu-btn { display: block; }
    }
"""

for fname in files:
    path = os.path.join(FRONTEND_DIR, fname)
    if not os.path.exists(path):
        continue
    
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # Rebrand text
    html = re.sub(r'ResumeAI(?!\.db)', 'TalentLens AI', html, flags=re.IGNORECASE)
    html = re.sub(r'Resume AI(?!\.db)', 'TalentLens AI', html, flags=re.IGNORECASE)
    
    # Specific fix for TalentLens AIAI
    html = html.replace('TalentLens AIAI', 'TalentLens AI')

    # Hero section update (index.html)
    if fname == "index.html":
        # Replace hero heading
        html = re.sub(r'<h1[^>]*>.*?Parse resumes that actually work in production.*?</h1>', 
                      '<h1 class="hero-title" style="font-size: clamp(2.5rem, 6vw, 4rem); font-weight: 800; line-height: 1.1; margin-bottom: 1rem; color: var(--text);">Build Smarter Resumes.<br><span style="background: linear-gradient(135deg, var(--primary), var(--secondary)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Get More Interviews.</span></h1>', 
                      html, flags=re.DOTALL)
        # Replace subtitle
        html = re.sub(r'<p class="hero-subtitle">.*?</p>', 
                      '<p class="hero-subtitle" style="font-size: 1.1rem; color: var(--muted); max-width: 600px; margin: 0 auto 2rem; line-height: 1.6;">Analyze resumes, improve ATS scores, match job descriptions, and prepare for interviews using AI-powered resume intelligence.</p>', 
                      html, flags=re.DOTALL)

    # Footer replacement
    html = re.sub(r'<footer.*?</footer>', NEW_FOOTER, html, flags=re.DOTALL)
    if '<footer' not in html:
        # If no footer, append right before </body> or at the end
        if '</body>' in html:
            html = html.replace('</body>', f'{NEW_FOOTER}\n</body>')
        else:
            html += f'\n{NEW_FOOTER}'

    # Navbar styling
    # First, let's remove any old nav CSS. We can inject our new CSS right before </style> or inside <head>.
    if '</style>' in html:
        # Clean up existing navbar CSS if possible, but it's safer to just override it.
        html = html.replace('</style>', f'\n{NEW_NAV_CSS}\n</style>')

    # Update actual navbar HTML wrapper
    new_nav_html = """<nav class="navbar">
  <div class="nav-inner">
    <a href="index.html" class="logo">
      <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      TalentLens<span>AI</span>
    </a>
    <button class="mobile-menu-btn" onclick="document.getElementById('navRight').classList.toggle('show')">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
    </button>
    <div class="nav-right" id="navRight"></div>
  </div>
</nav>"""
    html = re.sub(r'<nav[^>]*>.*?</nav>', new_nav_html, html, flags=re.DOTALL)

    # JS update - replace renderNav function
    html = re.sub(r'function renderNav\(\) \{.*?\}\s*renderNav\(\);', NAV_JS, html, flags=re.DOTALL)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

print("Rebrand to TalentLens AI complete.")
