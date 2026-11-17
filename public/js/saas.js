/**
 * AquaPredict SaaS Marketing Website Engine
 * Manages hero canvas visualization, product preview interactivity,
 * billing switcher, FAQ accordion, and client-side secure auth.
 */

(function () {
  'use strict';

  // --- 1. Sticky Navigation & Mobile Menu ---
  const header = document.querySelector('.saas-header');
  if (header) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 20) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }
    }, { passive: true });
  }

  const mobileToggle = document.querySelector('.mobile-toggle');
  const navLinks = document.querySelector('.nav-links');
  if (mobileToggle && navLinks) {
    mobileToggle.addEventListener('click', () => {
      navLinks.classList.toggle('mobile-open');
    });
  }

  // --- 2. Hero Interactive Geospatial Canvas ---
  const canvas = document.getElementById('heroCanvas');
  if (canvas) {
    const ctx = canvas.getContext('2d');
    let width, height;
    let animationFrameId;
    let mouseX = 0, mouseY = 0;
    let targetX = 0, targetY = 0;

    function resizeCanvas() {
      const parent = canvas.parentElement;
      width = canvas.width = parent.clientWidth * window.devicePixelRatio;
      height = canvas.height = parent.clientHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    }
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    window.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) {
        targetX = (e.clientX - rect.left - rect.width / 2) * 0.05;
        targetY = (e.clientY - rect.top - rect.height / 2) * 0.05;
      }
    });

    let time = 0;
    const gridRows = 16;
    const gridCols = 20;

    // Simulated Critical Infrastructure Markers
    const criticalNodes = [
      { r: 4, c: 6, label: "CHRISTUS Hospital", color: "#ef4444" },
      { r: 9, c: 14, label: "Good Neighbor Clinic", color: "#ef4444" },
      { r: 7, c: 10, label: "Pierce Underpass", color: "#f59e0b" },
      { r: 12, c: 8, label: "Main Gravity Outfall", color: "#38bdf8" }
    ];

    function drawHeroScene() {
      const displayW = canvas.width / window.devicePixelRatio;
      const displayH = canvas.height / window.devicePixelRatio;
      ctx.clearRect(0, 0, displayW, displayH);

      mouseX += (targetX - mouseX) * 0.05;
      mouseY += (targetY - mouseY) * 0.05;

      time += 0.02;

      const originX = displayW / 2 + mouseX;
      const originY = displayH * 0.28 + mouseY;
      const cellW = displayW / (gridCols * 1.3);
      const cellH = (displayH * 0.55) / gridRows;

      // Draw Isometric / Perspective Terrain Grid
      ctx.lineWidth = 1;
      for (let r = 0; r <= gridRows; r++) {
        ctx.beginPath();
        for (let c = 0; c <= gridCols; c++) {
          const isoX = originX + (c - gridCols / 2) * cellW * 1.5;
          const isoY = originY + r * cellH + (c - gridCols / 2) * 3;
          
          // Synthetic elevation / flood wave
          const wave = Math.sin(c * 0.4 + time) * Math.cos(r * 0.3 + time * 0.8) * 12;
          const ptY = isoY + wave;

          if (c === 0) ctx.moveTo(isoX, ptY);
          else ctx.lineTo(isoX, ptY);
        }
        ctx.strokeStyle = `rgba(56, 189, 248, ${0.12 + (r / gridRows) * 0.18})`;
        ctx.stroke();
      }

      for (let c = 0; c <= gridCols; c++) {
        ctx.beginPath();
        for (let r = 0; r <= gridRows; r++) {
          const isoX = originX + (c - gridCols / 2) * cellW * 1.5;
          const isoY = originY + r * cellH + (c - gridCols / 2) * 3;
          const wave = Math.sin(c * 0.4 + time) * Math.cos(r * 0.3 + time * 0.8) * 12;
          const ptY = isoY + wave;

          if (r === 0) ctx.moveTo(isoX, ptY);
          else ctx.lineTo(isoX, ptY);
        }
        ctx.strokeStyle = 'rgba(37, 99, 235, 0.18)';
        ctx.stroke();
      }

      // Draw Inundation Flow Corridor (Bayou / Depression)
      ctx.beginPath();
      for (let c = 0; c <= gridCols; c++) {
        const r = Math.floor(gridRows * 0.55 + Math.sin(c * 0.5) * 2);
        const isoX = originX + (c - gridCols / 2) * cellW * 1.5;
        const isoY = originY + r * cellH + (c - gridCols / 2) * 3;
        const wave = Math.sin(c * 0.4 + time) * Math.cos(r * 0.3 + time * 0.8) * 12;
        if (c === 0) ctx.moveTo(isoX, isoY + wave);
        else ctx.lineTo(isoX, isoY + wave);
      }
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.85)';
      ctx.lineWidth = 3.5;
      ctx.shadowColor = '#38bdf8';
      ctx.shadowBlur = 14;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Draw Critical Infrastructure Nodes with Pulsing Radar
      criticalNodes.forEach(node => {
        const isoX = originX + (node.c - gridCols / 2) * cellW * 1.5;
        const isoY = originY + node.r * cellH + (node.c - gridCols / 2) * 3;
        const wave = Math.sin(node.c * 0.4 + time) * Math.cos(node.r * 0.3 + time * 0.8) * 12;
        const ptY = isoY + wave;

        // Radar ripple
        const pulse = (time * 1.8) % 3;
        ctx.beginPath();
        ctx.arc(isoX, ptY, 4 + pulse * 7, 0, Math.PI * 2);
        ctx.strokeStyle = node.color;
        ctx.lineWidth = 1.2;
        ctx.stroke();

        // Core marker
        ctx.beginPath();
        ctx.arc(isoX, ptY, 4.5, 0, Math.PI * 2);
        ctx.fillStyle = node.color;
        ctx.fill();

        // Label
        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.fillStyle = '#ffffff';
        ctx.fillText(node.label, isoX + 8, ptY - 4);
      });

      animationFrameId = requestAnimationFrame(drawHeroScene);
    }
    drawHeroScene();
  }

  // --- 3. Interactive Product Preview Switcher ---
  const previewPills = document.querySelectorAll('.preview-pill');
  const metricVal1 = document.getElementById('metricVal1');
  const metricVal2 = document.getElementById('metricVal2');
  const metricVal3 = document.getElementById('metricVal3');
  const previewTitle = document.getElementById('previewTitle');
  const previewDesc = document.getElementById('previewDesc');
  const previewBadge = document.getElementById('previewBadge');

  const previewData = {
    flood: {
      title: "M5 Physical Scenario Simulation",
      badge: "M5 Dynamic Raster",
      m1: "1.50 m",
      m2: "0.095 km²",
      m3: "100 mm/hr",
      desc: "Precomputed physics-guided rainfall runoffs over 36 five-minute timesteps with high-resolution DEM depression ponding."
    },
    rescue: {
      title: "Rescue Priority Predictor",
      badge: "M4 Risk Ranking",
      m1: "Priority 1",
      m2: "2 / 2 Hospitals",
      m3: "Corridor Inundated",
      desc: "Deterministic accessibility analysis assessing critical connecting routes for hospitals, societies, and communities."
    },
    routing: {
      title: "Safest Route Decision Support",
      badge: "M7 Lexicographic Dijkstra",
      m1: "+180 m (Safe)",
      m2: "0 Impassable",
      m3: "Clearance: >0.30m",
      desc: "Multi-profile flood-avoidance routing prioritizing emergency vehicle and pedestrian survivability over raw distance."
    },
    terrain: {
      title: "M8 3D Hardware-Accelerated Terrain",
      badge: "Three.js WebGL Engine",
      m1: "256 × 256 DEM",
      m2: "0.97 km² Pilot",
      m3: "60 FPS Render",
      desc: "Interactive 3D elevation mesh with dynamic water level planes, vertical exaggeration, and orbit navigation."
    }
  };

  if (previewPills.length > 0) {
    previewPills.forEach(pill => {
      pill.addEventListener('click', () => {
        previewPills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');

        const mode = pill.getAttribute('data-preview');
        const data = previewData[mode];
        if (data) {
          if (previewTitle) previewTitle.textContent = data.title;
          if (previewBadge) previewBadge.textContent = data.badge;
          if (previewDesc) previewDesc.textContent = data.desc;
          if (metricVal1) metricVal1.textContent = data.m1;
          if (metricVal2) metricVal2.textContent = data.m2;
          if (metricVal3) metricVal3.textContent = data.m3;
        }
      });
    });
  }

  // --- 4. Pricing Monthly / Annual Toggle ---
  const billingSwitch = document.getElementById('billingSwitch');
  const proPrice = document.getElementById('proPrice');
  const teamPrice = document.getElementById('teamPrice');
  const planPeriods = document.querySelectorAll('.plan-period');
  const labelMonthly = document.getElementById('labelMonthly');
  const labelAnnual = document.getElementById('labelAnnual');

  if (billingSwitch) {
    billingSwitch.addEventListener('click', () => {
      const isAnnual = billingSwitch.classList.toggle('annual');
      if (labelMonthly) labelMonthly.classList.toggle('active', !isAnnual);
      if (labelAnnual) labelAnnual.classList.toggle('active', isAnnual);

      if (isAnnual) {
        if (proPrice) proPrice.textContent = '$119';
        if (teamPrice) teamPrice.textContent = '$399';
        planPeriods.forEach(p => p.textContent = '/ month (billed annually)');
      } else {
        if (proPrice) proPrice.textContent = '$149';
        if (teamPrice) teamPrice.textContent = '$499';
        planPeriods.forEach(p => p.textContent = '/ month');
      }
    });
  }

  // --- 5. FAQ Accordion ---
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    if (question) {
      question.addEventListener('click', () => {
        const isOpen = item.classList.contains('open');
        faqItems.forEach(i => i.classList.remove('open'));
        if (!isOpen) {
          item.classList.add('open');
        }
      });
    }
  });

  // --- 6. Client-Side Secure Authentication Suite ---
  window.AquaPredictAuth = {
    // SHA-256 password hash via Web Crypto API (no plaintext storage)
    async hashPassword(password) {
      const encoder = new TextEncoder();
      const data = encoder.encode(password + "_aquapredict_salt_2026");
      const hashBuffer = await crypto.subtle.digest('SHA-256', data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    },

    // Initialize default seed accounts if none exist in localStorage
    async initSeedAccounts() {
      if (!localStorage.getItem('aquapredict_users')) {
        const defaultHash = await this.hashPassword("AquaPredict2026!");
        const seedUsers = [
          {
            email: "analyst@aquapredict.io",
            name: "Dr. Elena Vance (Lead Hydrologist)",
            role: "Analyst",
            hash: defaultHash,
            createdAt: new Date().toISOString()
          }
        ];
        localStorage.setItem('aquapredict_users', JSON.stringify(seedUsers));
      }
    },

    getUsers() {
      try {
        return JSON.parse(localStorage.getItem('aquapredict_users') || '[]');
      } catch (e) {
        return [];
      }
    },

    saveUsers(users) {
      localStorage.setItem('aquapredict_users', JSON.stringify(users));
    },

    getCurrentSession() {
      try {
        const sess = sessionStorage.getItem('aquapredict_session');
        return sess ? JSON.parse(sess) : null;
      } catch (e) {
        return null;
      }
    },

    setSession(user) {
      const sessionData = {
        token: "aqp_" + Math.random().toString(36).substring(2) + Date.now().toString(36),
        email: user.email,
        name: user.name || user.email.split('@')[0],
        role: user.role || "Explorer",
        loginTime: new Date().toISOString()
      };
      sessionStorage.setItem('aquapredict_session', JSON.stringify(sessionData));
      return sessionData;
    },

    logout() {
      sessionStorage.removeItem('aquapredict_session');
      window.location.href = '/';
    },

    async signIn(email, password) {
      await this.initSeedAccounts();
      const users = this.getUsers();
      const cleanEmail = email.trim().toLowerCase();
      const user = users.find(u => u.email.toLowerCase() === cleanEmail);

      if (!user) {
        throw new Error("No account found with this email address. Please sign up.");
      }

      const inputHash = await this.hashPassword(password);
      if (user.hash !== inputHash) {
        throw new Error("Invalid password credentials. Please try again.");
      }

      return this.setSession(user);
    },

    async signUp(name, email, password) {
      await this.initSeedAccounts();
      const cleanEmail = email.trim().toLowerCase();

      // Form validation
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(cleanEmail)) {
        throw new Error("Please enter a valid email address.");
      }

      if (password.length < 8) {
        throw new Error("Password must be at least 8 characters long.");
      }

      const users = this.getUsers();
      if (users.some(u => u.email.toLowerCase() === cleanEmail)) {
        throw new Error("An account with this email already exists. Please sign in.");
      }

      const hash = await this.hashPassword(password);
      const newUser = {
        name: name.trim() || cleanEmail.split('@')[0],
        email: cleanEmail,
        role: "Pro Analyst",
        hash: hash,
        createdAt: new Date().toISOString()
      };

      users.push(newUser);
      this.saveUsers(users);
      return this.setSession(newUser);
    },

    async resetPassword(email, newPassword) {
      await this.initSeedAccounts();
      const cleanEmail = email.trim().toLowerCase();
      const users = this.getUsers();
      const userIdx = users.findIndex(u => u.email.toLowerCase() === cleanEmail);

      if (userIdx === -1) {
        throw new Error("No account found with this email address.");
      }

      if (newPassword.length < 8) {
        throw new Error("New password must be at least 8 characters long.");
      }

      users[userIdx].hash = await this.hashPassword(newPassword);
      this.saveUsers(users);
      return true;
    }
  };

  // Auto-init seed accounts
  window.AquaPredictAuth.initSeedAccounts();

  // If user is logged in, update navbar user state if present
  document.addEventListener('DOMContentLoaded', () => {
    const session = window.AquaPredictAuth.getCurrentSession();
    const navAuthContainer = document.getElementById('navAuthContainer');
    if (navAuthContainer && session) {
      navAuthContainer.innerHTML = `
        <span style="font-size:13px; color:var(--text-muted); font-family:var(--font-mono);">${session.name}</span>
        <a href="app.html" class="btn btn-primary btn-sm">Launch Platform</a>
        <button id="authLogoutBtn" class="btn btn-secondary btn-sm" style="padding:5px 10px; font-size:12px;">Logout</button>
      `;
      const logoutBtn = document.getElementById('authLogoutBtn');
      if (logoutBtn) {
        logoutBtn.addEventListener('click', () => window.AquaPredictAuth.logout());
      }
    }
  });

})();
