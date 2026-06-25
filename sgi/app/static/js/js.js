document.addEventListener('DOMContentLoaded', function () {
    const productoSelect = document.querySelector('select[name="producto"]');
    const stockInfoDiv = document.getElementById('stock-info');

    if (productoSelect && stockInfoDiv) {
        productoSelect.addEventListener('change', function () {
            const productId = this.value;
            if (!productId) {
                stockInfoDiv.textContent = '';
                return;
            }
            fetch(`/api/producto/${productId}/stock/`)
                .then(response => response.json())
                .then(data => {
                    stockInfoDiv.textContent = `Stock actual: ${data.stock_actual}`;
                })
                .catch(err => {
                    stockInfoDiv.textContent = 'Error al obtener stock.';
                });
        });
    }
});
