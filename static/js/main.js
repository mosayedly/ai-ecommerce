// Shared helpers for all pages.

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function showToast(message, type) {
    let container = document.querySelector('.messages');
    if (!container) {
        container = document.createElement('div');
        container.className = 'messages';
        const main = document.querySelector('main');
        if (main) main.prepend(container);
    }
    const el = document.createElement('div');
    el.className = 'alert alert-' + (type || 'success');
    el.textContent = message;
    container.appendChild(el);
    setTimeout(function () { el.remove(); }, 4000);
}

function updateCartCount(count) {
    const badge = document.getElementById('cart-count');
    if (badge) badge.textContent = count;
}

async function addToCart(productId, quantity) {
    const resp = await fetch('/cart/api/add/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify({ product_id: productId, quantity: quantity }),
    });
    const data = await resp.json();
    if (data.success) {
        updateCartCount(data.cart.count);
        showToast('Added to cart!');
    } else {
        showToast(data.error || 'Could not add to cart.', 'error');
    }
    return data;
}

document.addEventListener('DOMContentLoaded', function () {
    // Product card "Add to Cart" buttons (home + list pages).
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.add-to-cart');
        if (btn) {
            e.preventDefault();
            addToCart(btn.dataset.productId, 1);
        }
    });

    // Product detail add-to-cart form.
    document.addEventListener('submit', function (e) {
        const form = e.target.closest('.add-to-cart-form');
        if (form) {
            e.preventDefault();
            const qtyInput = form.querySelector('input[name="quantity"]');
            const qty = qtyInput ? parseInt(qtyInput.value, 10) : 1;
            addToCart(form.dataset.productId, qty || 1);
        }
    });

    // Log recommendation clicks (fire-and-forget) for authenticated users.
    document.addEventListener('click', function (e) {
        if (document.body.dataset.authenticated !== 'true') return;
        const link = e.target.closest('a');
        if (!link) return;
        const card = link.closest('.recommendation-card');
        if (!card) return;
        const productId = card.dataset.recProductId;
        if (!productId) return;
        fetch('/recommendations/click/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({ product_id: productId, source: card.dataset.recSource }),
            keepalive: true,
        }).catch(function () {});
    });

    // Auto-dismiss Django messages after a few seconds.
    document.querySelectorAll('.messages .alert').forEach(function (el) {
        setTimeout(function () { el.remove(); }, 5000);
    });
});
