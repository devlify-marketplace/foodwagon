/* Small optional reveal enhancement; graceful fallback when GSAP is absent. */
(function () {
  var nodes = document.querySelectorAll('[data-reveal]');
  if (window.gsap && nodes.length) {
    window.gsap.from(nodes, { opacity: 0, y: 18, duration: 0.55, stagger: 0.08, ease: 'power2.out' });
  }
}());
