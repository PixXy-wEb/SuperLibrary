// Index.js - Home Page Interactions

document.addEventListener('DOMContentLoaded', function() {
  // Animate stats counting
  animateStats();
  
  // Initialize book stack animation
  initBookStack();
  
  // Initialize tool cards hover effects
  initToolCards();
  
  // Initialize floating buttons
  initFloatingButtons();
});

// Animate statistics counting
function animateStats() {
  const stats = [
    { id: 'total-books', target: 154, duration: 2000 },
    { id: 'pdf-books', target: 89, duration: 1500 },
    { id: 'epub-books', target: 67, duration: 1800 }
  ];
  
  stats.forEach(stat => {
    const element = document.getElementById(stat.id);
    if (!element) return;
    
    animateCount(element, 0, stat.target, stat.duration);
  });
}

function animateCount(element, start, end, duration) {
  let startTimestamp = null;
  const step = (timestamp) => {
    if (!startTimestamp) startTimestamp = timestamp;
    const progress = Math.min((timestamp - startTimestamp) / duration, 1);
    const current = Math.floor(progress * (end - start) + start);
    element.textContent = current;
    
    if (progress < 1) {
      window.requestAnimationFrame(step);
    }
  };
  
  window.requestAnimationFrame(step);
}

// Book stack interaction
function initBookStack() {
  const bookStack = document.querySelector('.book-stack');
  if (!bookStack) return;
  
  bookStack.addEventListener('mouseenter', () => {
    document.querySelectorAll('.book').forEach((book, index) => {
      book.style.transitionDelay = `${index * 100}ms`;
    });
  });
  
  bookStack.addEventListener('mouseleave', () => {
    document.querySelectorAll('.book').forEach(book => {
      book.style.transitionDelay = '0ms';
    });
  });
}

// Tool cards hover effects
function initToolCards() {
  const toolCards = document.querySelectorAll('.tool-card');
  
  toolCards.forEach(card => {
    const features = card.querySelectorAll('.feature');
    
    card.addEventListener('mouseenter', () => {
      features.forEach((feature, index) => {
        feature.style.transitionDelay = `${index * 100}ms`;
        feature.style.transform = 'translateY(-5px)';
      });
    });
    
    card.addEventListener('mouseleave', () => {
      features.forEach(feature => {
        feature.style.transitionDelay = '0ms';
        feature.style.transform = 'translateY(0)';
      });
    });
  });
}

// Floating buttons functionality
function initFloatingButtons() {
  const floatingBtns = document.querySelectorAll('.floating-btn');
  
  // Add click animation
  floatingBtns.forEach(btn => {
    btn.addEventListener('click', function(e) {
      // Create ripple effect
      const ripple = document.createElement('span');
      const rect = this.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const x = e.clientX - rect.left - size / 2;
      const y = e.clientY - rect.top - size / 2;
      
      ripple.style.cssText = `
        position: absolute;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.7);
        transform: scale(0);
        animation: ripple 0.6s linear;
        width: ${size}px;
        height: ${size}px;
        top: ${y}px;
        left: ${x}px;
        pointer-events: none;
      `;
      
      this.appendChild(ripple);
      
      setTimeout(() => {
        ripple.remove();
      }, 600);
    });
  });
  
  // Add ripple animation to CSS
  const style = document.createElement('style');
  style.textContent = `
    @keyframes ripple {
      to {
        transform: scale(4);
        opacity: 0;
      }
    }
  `;
  document.head.appendChild(style);
}

// Quick action card hover effect enhancement
document.querySelectorAll('.quick-action-card').forEach(card => {
  card.addEventListener('mouseenter', function() {
    const icon = this.querySelector('.action-icon');
    icon.style.transform = 'scale(1.1) rotate(5deg)';
  });
  
  card.addEventListener('mouseleave', function() {
    const icon = this.querySelector('.action-icon');
    icon.style.transform = 'scale(1) rotate(0deg)';
  });
});

// Theme-aware animations
function updateThemeAwareAnimations() {
  const isDark = document.body.classList.contains('dark-mode');
  const cards = document.querySelectorAll('.tool-card, .quick-action-card');
  
  cards.forEach(card => {
    if (isDark) {
      card.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.3)';
    } else {
      card.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.1)';
    }
  });
}

// Call on theme change
document.addEventListener('themeChanged', updateThemeAwareAnimations);

// Initialize on load
updateThemeAwareAnimations();