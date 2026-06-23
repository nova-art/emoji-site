/**
 * emoji-site — Client-side interactivity
 * Search, copy-to-clipboard, skin tone picker, scroll animations
 */

(function () {
  'use strict';

  // --- Toast Notification ---
  const toast = document.getElementById('toast');
  let toastTimeout;

  function showToast(message) {
    if (!toast) return;
    toast.textContent = '✓ ' + message;
    toast.classList.add('show');
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
      toast.classList.remove('show');
    }, 2000);
  }

  // --- Copy to Clipboard ---
  function copyEmoji(emoji, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    navigator.clipboard.writeText(emoji).then(() => {
      showToast(emoji + ' copied!');

      // Show copied indicator on card if clicked from grid
      if (event) {
        const card = event.currentTarget;
        const indicator = card.querySelector('.emoji-card__copied');
        if (indicator) {
          indicator.classList.add('show');
          setTimeout(() => indicator.classList.remove('show'), 800);
        }
      }
    }).catch(() => {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = emoji;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand('copy');
        showToast(emoji + ' copied!');
      } catch (e) {
        showToast('Failed to copy');
      }
      document.body.removeChild(textarea);
    });
  }

  // Expose globally for inline onclick
  window.copyEmoji = copyEmoji;

  // --- Copy Button (detail page) ---
  const copyButton = document.getElementById('copy-button');
  if (copyButton) {
    copyButton.addEventListener('click', () => {
      const emoji = copyButton.dataset.emoji;
      navigator.clipboard.writeText(emoji).then(() => {
        copyButton.classList.add('copied');
        copyButton.querySelector('.copy-button__text').textContent = 'Copied!';
        showToast(emoji + ' copied!');
        setTimeout(() => {
          copyButton.classList.remove('copied');
          copyButton.querySelector('.copy-button__text').textContent = 'Copy Emoji';
        }, 2000);
      });
    });
  }

  // --- Skin Tone Picker ---
  const skinToneBtns = document.querySelectorAll('.skin-tone-btn');
  const emojiDisplay = document.getElementById('emoji-display');

  skinToneBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      skinToneBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      if (emojiDisplay) {
        emojiDisplay.textContent = btn.dataset.emoji;
      }

      // Update copy button data
      if (copyButton) {
        copyButton.dataset.emoji = btn.dataset.emoji;
      }
    });
  });

  // --- Search (Index page) ---
  const searchInput = document.getElementById('search-input');
  const searchCount = document.getElementById('search-count');
  const emojiGrid = document.getElementById('emoji-grid');
  const noResults = document.getElementById('no-results');
  const categorySections = document.querySelectorAll('.group-section');
  const categoryPills = document.querySelectorAll('.category-pill');

  let searchIndex = null;
  let allCards = null;
  let debounceTimer;

  // Load search index
  if (searchInput) {
    fetch('search-index.json')
      .then(res => res.json())
      .then(data => {
        searchIndex = data;
      })
      .catch(() => {
        console.warn('Could not load search index');
      });

    allCards = document.querySelectorAll('.emoji-card');

    searchInput.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => performSearch(searchInput.value), 100);
    });

    // Keyboard shortcut: "/" to focus search
    document.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement !== searchInput) {
        e.preventDefault();
        searchInput.focus();
      }
      if (e.key === 'Escape' && document.activeElement === searchInput) {
        searchInput.value = '';
        performSearch('');
        searchInput.blur();
      }
    });
  }

  function performSearch(query) {
    query = query.trim().toLowerCase();

    // Reset active category
    categoryPills.forEach(p => p.classList.remove('active'));
    const allPill = document.querySelector('[data-group="all"]');
    if (allPill) allPill.classList.add('active');

    if (!query) {
      // Show all
      if (allCards) allCards.forEach(card => card.style.display = '');
      categorySections.forEach(section => section.style.display = '');
      if (noResults) noResults.classList.remove('show');
      if (searchCount) searchCount.classList.remove('visible');
      return;
    }

    let matchCount = 0;
    const matchingSlugs = new Set();

    if (searchIndex) {
      searchIndex.forEach(entry => {
        const nameMatch = entry.name.toLowerCase().includes(query);
        const keywordMatch = entry.keywords && entry.keywords.some(k => k.toLowerCase().includes(query));
        if (nameMatch || keywordMatch) {
          matchingSlugs.add(entry.slug);
        }
      });
    }

    // Hide non-matching cards, show matching ones
    if (allCards) {
      allCards.forEach(card => {
        const slug = card.dataset.slug;
        const name = (card.dataset.name || '').toLowerCase();
        const char = card.dataset.char || '';

        const match = matchingSlugs.has(slug) || name.includes(query) || char === query;
        card.style.display = match ? '' : 'none';
        if (match) matchCount++;
      });
    }

    // Show group sections that have at least one visible card, hide the rest
    categorySections.forEach(section => {
      const hasVisibleCard = section.querySelector('.emoji-card:not([style*="display: none"])');
      section.style.display = hasVisibleCard ? '' : 'none';
    });

    // Show/hide no results
    if (noResults) {
      noResults.classList.toggle('show', matchCount === 0);
    }

    // Update count
    if (searchCount) {
      searchCount.textContent = matchCount + ' found';
      searchCount.classList.toggle('visible', matchCount > 0 || query.length > 0);
    }
  }

  // --- Category Filtering ---
  categoryPills.forEach(pill => {
    pill.addEventListener('click', () => {
      categoryPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');

      const group = pill.dataset.group;

      // Clear search
      if (searchInput) searchInput.value = '';
      if (searchCount) searchCount.classList.remove('visible');
      if (noResults) noResults.classList.remove('show');

      if (group === 'all') {
        categorySections.forEach(section => section.style.display = '');
        if (allCards) allCards.forEach(card => card.style.display = '');
      } else {
        categorySections.forEach(section => {
          section.style.display = section.dataset.group === group ? '' : 'none';
        });
        if (allCards) allCards.forEach(card => card.style.display = '');
      }

      // Scroll to top of grid
      if (emojiGrid) {
        emojiGrid.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // --- Scroll Animations (Intersection Observer) ---
  const fadeElements = document.querySelectorAll('.fade-in');
  if (fadeElements.length > 0 && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    );

    fadeElements.forEach(el => observer.observe(el));
  }

})();
