// Cart page interactions: update quantity, remove item, re-render from JSON.

(function () {
    const container = document.getElementById('cart-container');
    if (!container) return;
    const checkoutBtn = document.getElementById('checkout-btn');

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function renderCart(payload) {
        const cart = payload.cart;
        updateCartCount(cart.count);

        if (!cart.items.length) {
            container.innerHTML = '<p class="empty">Your cart is empty.</p>';
            if (checkoutBtn) checkoutBtn.style.display = 'none';
            return;
        }
        if (checkoutBtn) checkoutBtn.style.display = 'inline-block';

        let rows = '';
        cart.items.forEach(function (item) {
            rows += '' +
                '<tr data-item-id="' + item.id + '">' +
                    '<td><a href="' + item.url + '">' + escapeHtml(item.name) + '</a></td>' +
                    '<td>$' + escapeHtml(item.price) + '</td>' +
                    '<td><input type="number" class="qty-input" value="' + item.quantity + '" min="1" max="' + item.stock + '" data-item-id="' + item.id + '"></td>' +
                    '<td class="subtotal">$' + escapeHtml(item.subtotal) + '</td>' +
                    '<td><button type="button" class="btn btn-danger remove-item" data-item-id="' + item.id + '">Remove</button></td>' +
                '</tr>';
        });

        container.innerHTML = '' +
            '<table class="cart-table">' +
                '<thead><tr><th>Product</th><th>Price</th><th>Qty</th><th>Subtotal</th><th></th></tr></thead>' +
                '<tbody>' + rows + '</tbody>' +
                '<tfoot><tr><td colspan="3">Total</td><td id="cart-total">$' + escapeHtml(cart.total) + '</td><td></td></tr></tfoot>' +
            '</table>';
    }

    async function apiRequest(url, body) {
        const resp = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify(body),
        });
        return await resp.json();
    }

    container.addEventListener('change', async function (e) {
        if (!e.target.classList.contains('qty-input')) return;
        const itemId = e.target.dataset.itemId;
        const quantity = parseInt(e.target.value, 10);
        if (!quantity || quantity < 1) { e.target.value = 1; return; }
        const data = await apiRequest('/cart/api/update/', { item_id: itemId, quantity: quantity });
        if (data.success) renderCart(data);
        else showToast(data.error || 'Failed to update item.', 'error');
    });

    container.addEventListener('click', async function (e) {
        const btn = e.target.closest('.remove-item');
        if (!btn) return;
        const data = await apiRequest('/cart/api/remove/', { item_id: btn.dataset.itemId });
        if (data.success) renderCart(data);
        else showToast(data.error || 'Failed to remove item.', 'error');
    });
})();
