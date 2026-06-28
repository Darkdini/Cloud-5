(() => {
  // Cinematic intro
  const cineIntro = document.getElementById('cineIntro');
  if (!cineIntro) return;

  document.body.style.overflow = 'hidden';

  const slideA = cineIntro.querySelector('.cine-slide--a');
  const slideB = cineIntro.querySelector('.cine-slide--b');
  const lines = Array.from(cineIntro.querySelectorAll('.cine-line, .cine-title'));
  const skipBtn = document.getElementById('cineSkip');
  const canvas = document.getElementById('cineParticles');

  const slidePhotos = [
    'photos/full/photo-001.jpg',
    'photos/full/photo-007.jpg',
    'photos/full/photo-016.jpg',
    'photos/full/photo-021.jpg',
    'photos/full/photo-038.jpg',
    'photos/full/photo-057.jpg',
  ];

  let slideIndex = 0;
  let onA = true;
  const timers = [];

  function setTimer(fn, delay) {
    timers.push(setTimeout(fn, delay));
  }

  function showSlide(index) {
    const layer = onA ? slideA : slideB;
    const other = onA ? slideB : slideA;
    layer.style.backgroundImage = `url('${slidePhotos[index]}')`;
    layer.classList.remove('is-on');
    // restart ken-burns animation
    void layer.offsetWidth;
    layer.classList.add('is-on');
    other.classList.remove('is-on');
    onA = !onA;
  }

  function showLine(n) {
    lines.forEach((el) => {
      el.classList.toggle('is-active', el.dataset.line === String(n));
    });
  }

  function finishIntro() {
    timers.forEach(clearTimeout);
    cineIntro.classList.add('is-leaving');
    document.body.style.overflow = '';
    setTimeout(() => cineIntro.classList.add('is-done'), 1300);
  }

  // Particle field — warm drifting embers
  let particlesRunning = true;
  if (canvas) {
    const ctx = canvas.getContext('2d');
    let w, h;
    function resize() {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    const particles = Array.from({ length: 50 }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 2 + 0.6,
      speed: Math.random() * 0.5 + 0.15,
      drift: (Math.random() - 0.5) * 0.3,
      phase: Math.random() * Math.PI * 2,
    }));

    function tick() {
      if (!particlesRunning) return;
      ctx.clearRect(0, 0, w, h);
      const time = Date.now() / 1000;
      particles.forEach((p) => {
        p.y -= p.speed;
        p.x += p.drift;
        if (p.y < -10) { p.y = h + 10; p.x = Math.random() * w; }
        const twinkle = 0.4 + Math.abs(Math.sin(time + p.phase)) * 0.6;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(227, 205, 163, ${twinkle})`;
        ctx.fill();
      });
      requestAnimationFrame(tick);
    }
    tick();
  }

  skipBtn.addEventListener('click', finishIntro);

  // Timeline
  showLine(1);
  setTimer(() => showSlide(slideIndex++), 200);
  setTimer(() => showLine(2), 2200);
  setTimer(() => showSlide(slideIndex++), 2400);
  setTimer(() => showLine(3), 4400);
  setTimer(() => showSlide(slideIndex++), 4800);
  setTimer(() => showSlide(slideIndex++), 7200);
  setTimer(() => showSlide(slideIndex++), 9600);
  setTimer(() => showSlide(slideIndex++), 12000);
  setTimer(finishIntro, 14200);
  setTimer(() => { particlesRunning = false; }, 15600);
})();

(() => {
  const items = Array.from(document.querySelectorAll('.grid-item'));

  // Fade-in on scroll
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  items.forEach((item) => revealObserver.observe(item));

  // Lightbox
  const lightbox = document.getElementById('lightbox');
  const lightboxImg = document.getElementById('lightboxImg');
  const lightboxCounter = document.getElementById('lightboxCounter');
  const closeBtn = document.getElementById('lightboxClose');
  const prevBtn = document.getElementById('lightboxPrev');
  const nextBtn = document.getElementById('lightboxNext');

  let currentIndex = 0;

  function showAt(index) {
    currentIndex = (index + items.length) % items.length;
    const item = items[currentIndex];
    lightboxImg.src = item.dataset.full;
    lightboxImg.alt = `Фото ${currentIndex + 1} из ${items.length}`;
    lightboxCounter.textContent = `${currentIndex + 1} / ${items.length}`;
  }

  function openLightbox(index) {
    showAt(index);
    lightbox.classList.add('is-open');
    document.body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    lightbox.classList.remove('is-open');
    document.body.style.overflow = '';
  }

  items.forEach((item, index) => {
    item.addEventListener('click', () => openLightbox(index));
  });

  closeBtn.addEventListener('click', closeLightbox);
  prevBtn.addEventListener('click', () => showAt(currentIndex - 1));
  nextBtn.addEventListener('click', () => showAt(currentIndex + 1));

  lightbox.addEventListener('click', (e) => {
    if (e.target === lightbox) closeLightbox();
  });

  document.addEventListener('keydown', (e) => {
    if (!lightbox.classList.contains('is-open')) return;
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowLeft') showAt(currentIndex - 1);
    if (e.key === 'ArrowRight') showAt(currentIndex + 1);
  });

  // Touch swipe support
  let touchStartX = 0;
  lightbox.addEventListener('touchstart', (e) => {
    touchStartX = e.changedTouches[0].screenX;
  });
  lightbox.addEventListener('touchend', (e) => {
    const delta = e.changedTouches[0].screenX - touchStartX;
    if (Math.abs(delta) > 50) {
      delta > 0 ? showAt(currentIndex - 1) : showAt(currentIndex + 1);
    }
  });
})();
