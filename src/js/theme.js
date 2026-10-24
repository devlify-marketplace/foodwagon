import { docReady } from './utils';
import navbarInit from './bootstrap-navbar';
import detectorInit from './detector';
import scrollToTop from './scroll-to-top';

// /* -------------------------------------------------------------------------- */
// /*                            Theme Initialization                            */
// /* -------------------------------------------------------------------------- */

docReady(navbarInit);
docReady(detectorInit);
docReady(scrollToTop);

function initFoodwagonMotion() {
  const motion = window.gsap;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (motion && !reducedMotion) {
    const timeline = motion.timeline({ defaults: { ease: 'power3.out' } });
    if (window.matchMedia('(max-width: 575.98px)').matches) {
      timeline
        .from('[data-hero-image]', { y: -120, rotation: -10, scale: 0.9, autoAlpha: 0, duration: 0.85, ease: 'bounce.out' })
        .to('[data-hero-image]', { rotation: 360, duration: 1.15, ease: 'power2.inOut', transformOrigin: '50% 50%' }, '+=0.08')
        .call(() => motion.to('[data-hero-image]', { y: -5, duration: 2.6, repeat: -1, yoyo: true, ease: 'sine.inOut' }))
        .from('[data-dish-card]', { y: 13, autoAlpha: 0, duration: 0.42 }, '-=0.35')
        .from('.food-hero__copy h1', { y: 18, autoAlpha: 0, duration: 0.58 }, '-=0.08')
        .from('.food-hero__intro', { y: 12, autoAlpha: 0, duration: 0.42 }, '-=0.26')
        .from('.food-hero__actions .btn', { y: 9, autoAlpha: 0, duration: 0.38, stagger: 0.08 }, '-=0.18')
        .from('.food-category-card', { y: 10, autoAlpha: 0, duration: 0.34, stagger: 0.09 }, '-=0.18');
    } else {
      timeline
        .from('.food-hero__copy h1', { y: 18, autoAlpha: 0, duration: 0.58 })
        .from('.food-hero__intro', { y: 12, autoAlpha: 0, duration: 0.42 }, '-=0.26')
        .from('.food-hero__actions .btn', { y: 9, autoAlpha: 0, duration: 0.38, stagger: 0.08 }, '-=0.18')
        .from('[data-hero-image]', { y: -120, rotation: -10, scale: 0.9, autoAlpha: 0, duration: 0.85, ease: 'bounce.out' }, '-=0.48')
        .to('[data-hero-image]', { rotation: 360, duration: 1.15, ease: 'power2.inOut', transformOrigin: '50% 50%' }, '+=0.08')
        .call(() => motion.to('[data-hero-image]', { y: -5, duration: 2.6, repeat: -1, yoyo: true, ease: 'sine.inOut' }))
        .from('[data-dish-card]', { y: 13, autoAlpha: 0, duration: 0.42 }, '-=0.35')
        .from('.food-category-card', { y: 10, autoAlpha: 0, duration: 0.34, stagger: 0.09 }, '-=0.18');
    }
    const revealItems = document.querySelectorAll('[data-reveal]');
    const reveal = (element) => motion.fromTo(element, { y: 20, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.58, ease: 'power2.out', clearProps: 'transform,opacity,visibility' });
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries, activeObserver) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          reveal(entry.target);
          activeObserver.unobserve(entry.target);
        });
      }, { threshold: 0.14 });
      revealItems.forEach((item) => observer.observe(item));
    } else {
      revealItems.forEach(reveal);
    }
  }

  const categoryTrack = document.querySelector('.food-category-track');
  document.querySelectorAll('[data-category-scroll]').forEach((button) => {
    button.addEventListener('click', () => {
      if (!categoryTrack) return;
      categoryTrack.scrollBy({ left: Number(button.getAttribute('data-category-scroll')) * 150, behavior: reducedMotion ? 'auto' : 'smooth' });
    });
  });
}

docReady(initFoodwagonMotion);
