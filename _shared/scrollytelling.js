/**
 * Scrollytelling visual explainer engine for Systems Knowledge.
 * Handles stage progression, diagram reveals (via [data-min] and [data-max]),
 * IntersectionObserver scroll-spy, and declarative stage navigation.
 */

(function () {
  'use strict';

  let currentStage = 1;
  let activeCaptions = {};
  let isProgrammaticScroll = false;
  let scrollTimeout = null;

  /**
   * Transition diagram elements, captions, and navigation to stage `n`.
   * @param {number|string} stageNum - The target stage number.
   * @param {boolean} [scrollToSection=false] - Whether to scroll the prose into view.
   */
  function setStage(stageNum, scrollToSection = false) {
    const n = parseInt(stageNum, 10);
    if (isNaN(n)) return;
    currentStage = n;

    // 1. Update SVG diagram elements
    const minElements = document.querySelectorAll('[data-min]');
    minElements.forEach((el) => {
      const min = parseInt(el.getAttribute('data-min'), 10);
      if (min <= n) {
        el.classList.add('is-visible');
        if (min === n) {
          el.classList.add('is-current');
        } else {
          el.classList.remove('is-current');
        }
      } else {
        el.classList.remove('is-visible');
        el.classList.remove('is-current');
      }
    });

    // Support elements that retire after a certain stage
    const maxElements = document.querySelectorAll('[data-max]');
    maxElements.forEach((el) => {
      const max = parseInt(el.getAttribute('data-max'), 10);
      if (n > max) {
        el.classList.add('is-retired');
      } else {
        el.classList.remove('is-retired');
      }
    });

    // 2. Update Stage Nav Pills
    const navButtons = document.querySelectorAll('.stage-nav-btn');
    navButtons.forEach((btn) => {
      const btnStage = parseInt(btn.getAttribute('data-stage'), 10);
      if (btnStage === n) {
        btn.classList.add('active');
        btn.setAttribute('aria-current', 'step');
      } else {
        btn.classList.remove('active');
        btn.removeAttribute('aria-current');
      }
    });

    // 3. Update Dynamic Caption Card
    const captionEl = document.getElementById('stage-caption');
    const captionTagEl = document.getElementById('stage-caption-tag');
    if (captionEl && activeCaptions[n]) {
      const captionData = activeCaptions[n];
      if (typeof captionData === 'string') {
        captionEl.textContent = captionData;
      } else if (typeof captionData === 'object') {
        if (captionTagEl && captionData.tag) {
          captionTagEl.textContent = captionData.tag;
        }
        if (captionData.text) {
          captionEl.textContent = captionData.text;
        }
      }
    }

    // 4. Optionally scroll the prose section into view
    if (scrollToSection) {
      const targetSection = document.querySelector(`.prose-step[data-stage="${n}"]`);
      if (targetSection) {
        isProgrammaticScroll = true;
        clearTimeout(scrollTimeout);
        targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        scrollTimeout = setTimeout(() => {
          isProgrammaticScroll = false;
        }, 800);
      }
    }

    // 5. Dispatch stage change event
    window.dispatchEvent(
      new CustomEvent('stagechange', {
        detail: { stage: n }
      })
    );
  }

  /**
   * Set up IntersectionObserver to automatically trigger stage reveals during scroll.
   */
  function initScrollSpy() {
    const steps = document.querySelectorAll('.prose-step[data-stage]');
    if (!steps.length) return;

    const observerOptions = {
      root: null,
      rootMargin: '-20% 0px -45% 0px',
      threshold: [0, 0.25, 0.5, 0.75]
    };

    const observer = new IntersectionObserver((entries) => {
      if (isProgrammaticScroll) return;

      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const stage = parseInt(entry.target.getAttribute('data-stage'), 10);
          if (stage && stage !== currentStage) {
            setStage(stage, false);
          }
        }
      });
    }, observerOptions);

    steps.forEach((step) => observer.observe(step));
  }

  /**
   * Declaratively build stage navigation pills inside a container.
   * @param {HTMLElement|string} container - The DOM node or selector to render pills into.
   * @param {number|Array<number|string>} stages - Number of stages or array of stage names/numbers.
   * @param {Object} [captions] - Map of stage number to caption string or { tag, text } object.
   */
  function buildStageNav(container, stages, captions = {}) {
    const target = typeof container === 'string' ? document.querySelector(container) : container;
    if (!target) return;

    if (captions) {
      activeCaptions = captions;
    }

    target.innerHTML = '';
    const label = document.createElement('span');
    label.className = 'stage-nav-label';
    label.textContent = 'Stage';
    target.appendChild(label);

    let stageList = [];
    if (typeof stages === 'number') {
      for (let i = 1; i <= stages; i++) {
        stageList.push(i);
      }
    } else if (Array.isArray(stages)) {
      stageList = stages;
    }

    stageList.forEach((stageNum) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'stage-nav-btn' + (stageNum === 1 ? ' active' : '');
      btn.setAttribute('data-stage', stageNum);
      btn.setAttribute('title', `Jump to Stage ${stageNum}`);

      const dot = document.createElement('span');
      dot.className = 'stage-dot';

      const text = document.createTextNode(stageNum < 10 ? `0${stageNum}` : `${stageNum}`);

      btn.appendChild(dot);
      btn.appendChild(text);

      btn.addEventListener('click', () => {
        setStage(stageNum, true);
      });

      target.appendChild(btn);
    });

    // Initialize to stage 1
    if (stageList.length > 0) {
      setStage(1, false);
    }
  }

  // Expose API globally
  window.setStage = setStage;
  window.buildStageNav = buildStageNav;

  // Auto-initialize scroll spy when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initScrollSpy);
  } else {
    initScrollSpy();
  }
})();
