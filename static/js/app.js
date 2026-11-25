/* 全局交互脚本：滚动渐入、toast、视角切换 */
(function () {
  'use strict';

  function showToast(message, type) {
    let host = document.getElementById('toast-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'toast-host';
      host.className = 'fixed top-20 right-4 z-[70] flex w-[min(92vw,360px)] flex-col gap-2';
      document.body.appendChild(host);
    }
    const el = document.createElement('div');
    const tone = type === 'error' ? 'alert-error' : type === 'warning' ? 'alert-warning' : 'alert-success';
    el.className = 'alert ' + tone + ' shadow-lg text-sm reveal-up is-visible';
    el.textContent = message;
    host.appendChild(el);
    window.setTimeout(function () {
      el.style.transition = 'opacity .3s ease, transform .3s ease';
      el.style.opacity = '0';
      el.style.transform = 'translateY(-6px)';
      window.setTimeout(function () {
        el.remove();
      }, 320);
    }, 3200);
  }

  window.showToast = showToast;

  document.body.addEventListener('showToast', function (event) {
    const detail = event.detail || {};
    const message = detail.message || (detail.value && detail.value.message) || '操作成功';
    showToast(message, detail.type || 'success');
  });

  document.body.addEventListener('bookingCreated', function (event) {
    const detail = (event.detail && (event.detail.message || event.detail.value)) || {};
    const message = typeof detail === 'string' ? detail : (detail.message || '预约成功，请等待管家联系');
    const modal = document.getElementById('viewing-modal');
    if (modal && modal.open) modal.close();
    showToast(message, 'success');
    const wrap = document.getElementById('viewing-form-wrap');
    const form = wrap && wrap.querySelector('form');
    if (form) form.reset();
  });

  // 滚动渐入：只做一次
  function setupReveal() {
    const nodes = document.querySelectorAll('.reveal, .reveal-up, .reveal-zoom');
    if (!nodes.length) return;
    if (!('IntersectionObserver' in window)) {
      nodes.forEach(function (node) { node.classList.add('is-visible'); });
      return;
    }
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    nodes.forEach(function (node) { observer.observe(node); });
  }

  document.addEventListener('DOMContentLoaded', setupReveal);
  document.body.addEventListener('htmx:afterSwap', setupReveal);

})();
