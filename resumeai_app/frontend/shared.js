/* ==========================================================================
   Shared JS Logic (Auth, Nav, Toasts, Footer)
   ========================================================================== */

const API = 'https://resumeai-production-0442.up.railway.app';

/* ── Authentication Helpers ────────────────────────────────────────────── */
function getToken() {
  return localStorage.getItem('auth_token');
}

function authHeaders() {
  const token = getToken();
  return token ? { 'Authorization': 'Bearer ' + token } : {};
}

function getUser() {
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

/* ── Toast Notifications ────────────────────────────────────────────────── */
function showToast(message, type = 'success') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let icon = '✅';
  if (type === 'error') icon = '❌';
  if (type === 'info') icon = 'ℹ️';
  
  toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.animation = 'toast-out 0.3s ease forwards';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/* ── Render Navigation ──────────────────────────────────────────────────── */
function renderNav() {
  const user = getUser();
  const navElement = document.getElementById('main-nav');
  
  if (!navElement) return; // Wait for element to exist or manual invocation
  
  const currentPath = window.location.pathname.split('/').pop() || 'index.html';
  const isActive = (path) => currentPath === path ? 'active' : '';

  let navHTML = `
    <div class="nav-inner">
      <div class="nav-left">
        <a href="index.html" class="logo">
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          TalentLens<span>AI</span>
        </a>
      </div>
      <button class="mobile-menu-btn" onclick="document.getElementById('navRight').classList.toggle('show')">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
      </button>
      <div class="nav-right" id="navRight">
  `;

  // Only render links if NOT on auth pages
  if (currentPath !== 'login.html' && currentPath !== 'signup.html') {
    if (user && getToken() && getToken() !== 'undefined') {
      navHTML += `
        <div class="nav-links">
          <a href="index.html" class="nav-link ${isActive('index.html')}">Dashboard</a>
          <a href="history.html" class="nav-link ${isActive('history.html')}">History</a>
          <a href="reports.html" class="nav-link ${isActive('reports.html')}">Reports</a>
          <a href="ai_assistant.html" class="nav-link ${isActive('ai_assistant.html')}">AI Assistant</a>
          <a href="interview_prep.html" class="nav-link ${isActive('interview_prep.html')}">Interview Prep</a>
        </div>
        <div class="profile-dropdown">
          <button class="profile-btn">
            <span>👤 ${user.name.split(' ')[0]} ▼</span>
          </button>
          <div class="profile-menu">
            <div class="profile-header">
              <strong>${user.name}</strong>
              <small>${user.email}</small>
            </div>
            <a href="index.html" class="profile-item">Dashboard</a>
            <a href="history.html" class="profile-item">History</a>
            <a href="reports.html" class="profile-item">Reports</a>
            <button class="profile-item logout-btn" onclick="doLogout()">Logout</button>
          </div>
        </div>
      `;
    } else {
      navHTML += `
        <div class="nav-links">
          <a href="index.html" class="nav-link ${isActive('index.html')}">Home</a>
          <a href="ai_assistant.html" class="nav-link ${isActive('ai_assistant.html')}">AI Assistant</a>
          <a href="interview_prep.html" class="nav-link ${isActive('interview_prep.html')}">Interview Prep</a>
          <a href="https://github.com/AbhijaySinghPanwar/resumeAI" target="_blank" class="nav-link">GitHub</a>
        </div>
        <div class="auth-buttons">
          <a href="login.html" class="login-link">Login</a>
          <button class="btn-primary" onclick="window.location.href='signup.html'">Sign Up</button>
        </div>
      `;
    }
  }

  navHTML += `
      </div>
    </div>
  `;
  
  navElement.innerHTML = navHTML;
}

/* ── Render Footer ──────────────────────────────────────────────────────── */
function renderFooter() {
  const footerElement = document.getElementById('main-footer');
  if (!footerElement) return;

  footerElement.innerHTML = `
    <div class="footer-inner">
      <div class="footer-grid">
        <div class="footer-brand">
          <div class="footer-logo">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path stroke="var(--primary)" d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline stroke="var(--primary)" points="14 2 14 8 20 8"/>
            </svg>
            TalentLens AI
          </div>
          <p class="footer-desc">
            AI-Powered Resume Intelligence Platform. Helping students and professionals optimize resumes, improve ATS performance, prepare for interviews, and match job opportunities using AI.
          </p>
        </div>
        
        <div>
          <h4 class="footer-heading">Features</h4>
          <div class="footer-links">
            <a href="index.html" class="footer-link">Resume Parsing</a>
            <a href="index.html" class="footer-link">ATS Analysis</a>
            <a href="index.html" class="footer-link">JD Matching</a>
            <a href="ai_assistant.html" class="footer-link">AI Resume Assistant</a>
            <a href="interview_prep.html" class="footer-link">Interview Preparation</a>
            <a href="history.html" class="footer-link">Resume History</a>
            <a href="reports.html" class="footer-link">Saved Reports</a>
          </div>
        </div>
        
        <div>
          <h4 class="footer-heading">Resources</h4>
          <div class="footer-links">
            <a href="https://github.com/AbhijaySinghPanwar/resumeAI" target="_blank" class="footer-link">GitHub Repository</a>
            <a href="#" class="footer-link">Documentation</a>
            <a href="#" class="footer-link">Privacy Policy</a>
          </div>
        </div>
        
        <div>
          <h4 class="footer-heading">Tech Stack</h4>
          <div class="footer-links">
            <span class="footer-link" style="color: var(--muted); cursor: default;">FastAPI</span>
            <span class="footer-link" style="color: var(--muted); cursor: default;">Python</span>
            <span class="footer-link" style="color: var(--muted); cursor: default;">Gemini AI</span>
            <span class="footer-link" style="color: var(--muted); cursor: default;">SQLAlchemy</span>
            <span class="footer-link" style="color: var(--muted); cursor: default;">SQLite / PostgreSQL</span>
          </div>
        </div>
      </div>
      
      <div class="footer-bottom">
        <div class="footer-copy">
          &copy; ${new Date().getFullYear()} TalentLens AI. Built with ❤️ using FastAPI &bull; Python &bull; Gemini AI
        </div>
        <div class="footer-social">
          <a href="https://github.com/AbhijaySinghPanwar/resumeAI" target="_blank" class="footer-link">GitHub</a>
          <a href="#" class="footer-link">LinkedIn</a>
          <a href="#" class="footer-link">Email</a>
        </div>
      </div>
    </div>
  `;
}

/* ── Global Scroll Listener ─────────────────────────────────────────────── */
window.addEventListener('scroll', () => {
  const nav = document.querySelector('.navbar');
  if (nav && window.scrollY > 10) {
    nav.classList.add('scrolled');
  } else if(nav) {
    nav.classList.remove('scrolled');
  }
});

/* ── Modals ─────────────────────────────────────────────────────────────── */
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('open');
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('open');
}

/* ── Init ───────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  renderNav();
  renderFooter();
});
