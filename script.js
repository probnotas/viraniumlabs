(function () {
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* expose scrollbar width so gutter figures centre against the visible page */
  function scrollbarVar() {
    var sbw = window.innerWidth - document.documentElement.clientWidth;
    document.documentElement.style.setProperty('--sbw', sbw + 'px');
  }
  scrollbarVar();
  window.addEventListener('resize', scrollbarVar);

  /* nav darkens once the page is scrolled */
  var nav = document.querySelector('.nav');
  function navState() {
    if (nav) nav.classList.toggle('scrolled', window.scrollY > 40);
  }
  navState();
  window.addEventListener('scroll', navState, { passive: true });

  /* hero video: browsers block autoplay in several situations (iOS low power
     mode, data saver, a cold tab), and the fallback is a tap-to-play overlay.
     Keep asking politely instead, and let the poster carry the frame until it
     takes -- the slow zoom runs on the poster too, so a blocked video still
     reads as intentional rather than broken. */
  var vid = document.querySelector('.bgvid');
  if (vid) {
    /* Safari honours the muted property, not just the attribute, and refuses
       inline autoplay unless both are set before the first play() */
    vid.muted = true;
    vid.defaultMuted = true;
    vid.playsInline = true;
    vid.setAttribute('muted', '');

    var lastTry = 0;
    function playHero() {
      if (!vid.paused && !vid.ended) return;
      var now = Date.now();
      if (now - lastTry < 400) return;      // don't spin if play() keeps failing
      lastTry = now;
      var p = vid.play();
      if (p && p.catch) p.catch(function () { /* still blocked; wait it out */ });
    }

    ['loadedmetadata', 'loadeddata', 'canplay', 'canplaythrough'].forEach(function (ev) {
      vid.addEventListener(ev, playHero);
    });

    /* a pause we did not ask for: backgrounding on iOS, or a blocked start */
    vid.addEventListener('pause', function () {
      if (!document.hidden) playHero();
    });

    /* any gesture anywhere unblocks playback, so the first one is enough */
    var gestures = ['pointerdown', 'touchstart', 'touchend', 'click', 'keydown', 'scroll'];
    function onGesture() {
      playHero();
      if (!vid.paused) {
        gestures.forEach(function (ev) {
          document.removeEventListener(ev, onGesture, gestureOpts);
        });
      }
    }
    var gestureOpts = { passive: true, capture: true };
    gestures.forEach(function (ev) {
      document.addEventListener(ev, onGesture, gestureOpts);
    });

    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) playHero();
    });
    window.addEventListener('pageshow', playHero);   // bfcache restore

    playHero();
  }

  /* footer band: animated halftone wave that reacts to the cursor */
  var band = document.querySelector('.band');
  var canvas = document.querySelector('.band-canvas');
  if (band && canvas && canvas.getContext) {
    var ctx = canvas.getContext('2d');
    var W = 0, H = 0, dpr = 1;
    var GAP = 8;
    var mx = 0, my = 0, mAmt = 0, mTarget = 0;

    function sizeCanvas() {
      var r = band.getBoundingClientRect();
      W = r.width; H = r.height;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    sizeCanvas();
    window.addEventListener('resize', sizeCanvas);

    band.addEventListener('mousemove', function (e) {
      var r = canvas.getBoundingClientRect();
      mx = e.clientX - r.left;
      my = e.clientY - r.top;
      mTarget = 1;
    });
    band.addEventListener('mouseleave', function () { mTarget = 0; });

    function crest(x, t) {
      return H * 0.80
        + Math.sin(x * 0.0060 + t * 0.42) * H * 0.075
        + Math.sin(x * 0.0131 - t * 0.31) * H * 0.035
        + Math.sin(x * 0.0027 + t * 0.67) * H * 0.028
        - (x / W) * H * 0.060;         // sweeps upward toward the right
    }

    function render(t) {
      mAmt += (mTarget - mAmt) * 0.08;
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = '#D2D4CD';
      ctx.beginPath();
      var maxR = GAP * 0.52;
      var fade = 46;                       // halftone transition depth
      for (var x = GAP * 0.5; x < W; x += GAP) {
        var cy = crest(x, t);
        if (mAmt > 0.01) {                 // cursor lifts the wave toward it
          var dx = x - mx;
          cy -= Math.exp(-(dx * dx) / 16200) * 26 * mAmt;
        }
        for (var y = GAP * 0.5; y < H; y += GAP) {
          var f = (y - cy) / fade;
          f = f < 0 ? 0 : (f > 1 ? 1 : f);
          f = f * f * (3 - 2 * f);
          if (mAmt > 0.01) {               // dots swell around the pointer
            var ax = x - mx, ay = y - my;
            var d = Math.sqrt(ax * ax + ay * ay);
            if (d < 130) f += (1 - d / 130) * 0.55 * mAmt;
          }
          if (f <= 0.02) continue;
          var rr = maxR * (f > 1 ? 1 : f);
          ctx.moveTo(x + rr, y);
          ctx.arc(x, y, rr, 0, 6.283185);
        }
      }
      ctx.fill();
    }

    if (reduced) {
      render(0);
    } else {
      var running = false;
      var loop = function (now) {
        if (running) { render(now / 1000); requestAnimationFrame(loop); }
      };
      // only animate while the band is on screen
      if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (es) {
          es.forEach(function (e) {
            if (e.isIntersecting && !running) { running = true; requestAnimationFrame(loop); }
            else if (!e.isIntersecting) { running = false; }
          });
        }, { threshold: 0 }).observe(band);
      } else {
        running = true; requestAnimationFrame(loop);
      }
      render(0);
    }
  }

  /* reveal-on-scroll for content */
  var targets = document.querySelectorAll('main > *');
  targets.forEach(function (el) { el.classList.add('reveal'); });

  if (reduced || !('IntersectionObserver' in window)) {
    targets.forEach(function (el) { el.classList.add('in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    targets.forEach(function (el) { io.observe(el); });
  }

  /* slow inertial scrolling: wheel input is damped so the page drifts */
  if (!reduced) {
    var target = window.scrollY;
    var current = window.scrollY;
    var animating = false;
    function maxScroll() {
      return document.documentElement.scrollHeight - window.innerHeight;
    }
    function step() {
      current += (target - current) * 0.05;
      if (Math.abs(target - current) < 0.5) {
        current = target;
        animating = false;
      }
      window.scrollTo({ top: current, behavior: 'instant' });
      if (animating) requestAnimationFrame(step);
    }
    window.addEventListener('wheel', function (e) {
      if (e.ctrlKey) return;                                // leave pinch-zoom alone
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;  // and horizontal gestures
      e.preventDefault();
      target = Math.max(0, Math.min(maxScroll(), target + e.deltaY));
      if (!animating) {
        animating = true;
        requestAnimationFrame(step);
      }
    }, { passive: false });
    window.addEventListener('scroll', function () {
      if (!animating && Math.abs(window.scrollY - current) > 1.5) {
        current = target = window.scrollY;
      }
    }, { passive: true });
  }

})();
