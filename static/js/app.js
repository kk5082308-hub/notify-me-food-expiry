// PWA Service Worker Registration & PWA Installation Prompt

// Service worker registration
let swRegistration = null;

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((registration) => {
        console.log('ServiceWorker registration successful with scope: ', registration.scope);
        swRegistration = registration;
      })
      .catch((err) => {
        console.error('ServiceWorker registration failed: ', err);
      });
  });
}

// ----------------------------------------------------
// PWA Add to Home Screen Installer Prompt
// ----------------------------------------------------
let deferredPrompt = null;
const installBtn = document.getElementById('pwa-install-btn');

window.addEventListener('beforeinstallprompt', (e) => {
  // Prevent Chrome 67 and earlier from automatically showing the prompt
  e.preventDefault();
  // Stash the event so it can be triggered later.
  deferredPrompt = e;
  // Update UI notify the user they can install the PWA
  if (installBtn) {
    installBtn.style.display = 'block';
  }
});

if (installBtn) {
  installBtn.addEventListener('click', () => {
    if (!deferredPrompt) return;
    // Show the prompt
    deferredPrompt.prompt();
    // Wait for the user to respond to the prompt
    deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        console.log('User accepted the install prompt');
      } else {
        console.log('User dismissed the install prompt');
      }
      deferredPrompt = null;
      installBtn.style.display = 'none';
    });
  });
}

// Hide install button when app is launched as PWA standalone
window.addEventListener('appinstalled', () => {
  console.log('Notify-Me PWA was installed successfully');
  if (installBtn) {
    installBtn.style.display = 'none';
  }
});

// ----------------------------------------------------
// Dark Mode Toggle Management
// ----------------------------------------------------
const themeToggle = document.getElementById('theme-toggle-btn');
const themeIcon = document.getElementById('theme-icon');

function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'light';
  applyTheme(savedTheme);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-bs-theme', theme);
  localStorage.setItem('theme', theme);
  
  if (themeIcon) {
    if (theme === 'dark') {
      themeIcon.className = 'bi bi-sun';
    } else {
      themeIcon.className = 'bi bi-moon-stars';
    }
  }
}

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-bs-theme') || 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
  });
}

// Run theme check immediately
initTheme();
